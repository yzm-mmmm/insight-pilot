"""
反思节点

在每次 SQL 执行后审视结果，判断下一步动作：
- done：所有子问题已回答完毕，结束
- retry_sql：结果有问题，带着反思结论回到 SQL 生成重试
- new_sub_question：结果正常但还有子问题，推进计划
- ask_user：缺少必要限定条件，向用户追问

同时把分析发现沉淀进 insights，并累加迭代计数，配合最大轮数上限防止死循环。
"""

import json

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, ReflectionState
from app.conf.app_config import app_config
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt

VALID_ACTIONS = ("done", "retry_sql", "new_sub_question", "ask_user")


async def reflect(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """审视执行结果并决定下一步动作"""

    writer = runtime.stream_writer
    step = "反思结果"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        executed_results = state["executed_results"]
        iteration_count = state["iteration_count"]
        max_loops = app_config.agent.max_analysis_loops

        # 最近一次执行结果作为反思对象，理论上 run_sql 之后必然存在
        current_result = (
            executed_results[-1] if executed_results else {"columns": [], "rows": []}
        )

        prompt = PromptTemplate(
            template=load_prompt("reflect"),
            input_variables=[
                "query",
                "intent",
                "plan",
                "current_question",
                "sql",
                "result",
                "insights",
                "iteration_count",
                "max_loops",
            ],
        )
        chain = prompt | llm | JsonOutputParser()

        result = await chain.ainvoke(
            {
                "query": state["query"],
                "intent": state["intent"],
                "plan": json.dumps(state["plan"], ensure_ascii=False),
                "current_question": state["current_question"],
                "sql": state["sql"],
                "result": json.dumps(current_result, ensure_ascii=False, default=str),
                "insights": json.dumps(state["insights"], ensure_ascii=False)
                if state["insights"]
                else "（暂无）",
                "iteration_count": iteration_count,
                "max_loops": max_loops,
            }
        )

        next_action = result.get("next_action", "done") if isinstance(result, dict) else "done"
        if next_action not in VALID_ACTIONS:
            next_action = "done"
        finding = str(result.get("finding", "")).strip() if isinstance(result, dict) else ""
        reason = str(result.get("reason", "")).strip() if isinstance(result, dict) else ""

        reflection = ReflectionState(next_action=next_action, finding=finding, reason=reason)

        # 迭代计数 +1，并在达到上限时强制收敛到 done
        new_iteration = iteration_count + 1
        if new_iteration >= max_loops:
            reflection["next_action"] = "done"

        writer({"type": "insight", "content": finding, "next_action": reflection["next_action"]})
        if reflection["next_action"] == "ask_user":
            writer({"type": "ask", "question": reason})

        logger.info(
            f"反思结论：next_action={reflection['next_action']} finding={finding}"
        )

        writer({"type": "progress", "step": step, "status": "success"})

        update: dict = {"reflection": reflection, "iteration_count": new_iteration}
        if finding:
            update["insights"] = [finding]
        return update

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
