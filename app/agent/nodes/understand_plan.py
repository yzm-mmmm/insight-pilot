"""
理解与规划节点

作为自主分析链路的入口，把用户一句话拆解成一组按顺序执行的子问题，
并概括整体分析意图。拆解结果写回 state 的 plan / intent，供后续
select_next_step 逐个推进、generate_sql 按子问题生成 SQL、reflect 判断进度。
"""

import json

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, PlanItemState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def understand_plan(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """把用户问题拆解成子问题规划"""

    writer = runtime.stream_writer
    step = "理解并规划"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        query = state["query"]
        # 多轮追问时把历史对话一并注入，供模型解析“那华东呢”这类指代
        history = state["conversation_history"]
        history_text = (
            json.dumps(history, ensure_ascii=False) if history else "（无，这是第一轮）"
        )

        prompt = PromptTemplate(
            template=load_prompt("understand_plan"),
            input_variables=["query", "history"],
        )
        chain = prompt | llm | JsonOutputParser()

        result = await chain.ainvoke({"query": query, "history": history_text})
        intent = str(result.get("intent", "")).strip() if isinstance(result, dict) else ""
        plan_raw = result.get("plan", []) if isinstance(result, dict) else []

        # 模型输出可能缺字段或类型异常，这里逐项清洗，坏项直接丢弃
        plan: list[PlanItemState] = []
        for item in plan_raw:
            try:
                plan.append(
                    PlanItemState(
                        id=int(item["id"]),
                        question=str(item["question"]).strip(),
                        intent=str(item.get("intent", "")).strip(),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue

        # 兜底：拆解失败或为空时，把原问题作为唯一子问题，保证链路可继续
        if not plan:
            plan = [PlanItemState(id=1, question=query, intent=intent or "回答原问题")]

        logger.info(f"分析意图：{intent}；子问题：{[item['question'] for item in plan]}")

        writer({"type": "plan", "intent": intent, "plan": plan})
        writer({"type": "progress", "step": step, "status": "success"})
        # plan_cursor 置 -1，表示尚未开始处理任何子问题；首个子问题由
        # select_next_step 推进到下标 0，避免在理解阶段就跳过 plan[0]
        return {"intent": intent, "plan": plan, "plan_cursor": -1}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
