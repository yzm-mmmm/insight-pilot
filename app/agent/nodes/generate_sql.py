"""
SQL 生成节点

负责根据当前分析子问题和前面整理出的表结构 指标 日期 数据库环境生成候选 SQL。
本节点只生成 SQL，不做校验和执行。自主分析循环中的 retry_sql 也会回到这里，
此时会把历史 SQL 和反思结论注入提示词，让模型针对性地重新生成。
"""

import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import get_llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.core.sql_guard import normalize_sql
from app.prompt.prompt_loader import load_prompt


async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """基于已检索和过滤的上下文，为当前子问题生成 SQL"""

    writer = runtime.stream_writer
    step = "生成SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        date_info = state["date_info"]
        db_info = state["db_info"]
        query = state["query"]
        current_question = state["current_question"]
        plan = state["plan"]
        sql_history = state["sql_history"]
        reflection = state["reflection"]
        feedback_examples = state.get("feedback_examples", [])

        prompt = PromptTemplate(
            template=load_prompt("generate_sql"),
            input_variables=[
                "table_infos",
                "metric_infos",
                "date_info",
                "db_info",
                "query",
                "current_question",
                "plan",
                "sql_history",
                "reflection",
                "feedback_examples",
            ],
        )
        output_parser = StrOutputParser()
        chain = prompt | get_llm() | output_parser

        result = await chain.ainvoke(
            {
                "table_infos": yaml.dump(
                    table_infos, allow_unicode=True, sort_keys=False
                ),
                "metric_infos": yaml.dump(
                    metric_infos, allow_unicode=True, sort_keys=False
                ),
                "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
                "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
                "query": query,
                "current_question": current_question,
                "plan": yaml.dump(plan, allow_unicode=True, sort_keys=False),
                "sql_history": yaml.dump(sql_history, allow_unicode=True, sort_keys=False)
                if sql_history
                else "（暂无）",
                "reflection": reflection["reason"] if reflection else "（首次生成）",
                "feedback_examples": yaml.dump(
                    feedback_examples, allow_unicode=True, sort_keys=False
                )
                if feedback_examples
                else "（暂无）",
            }
        )

        sql = normalize_sql(result)
        logger.info(f"生成的SQL：{sql}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {"sql": sql, "sql_history": [sql], "sql_retry_count": 0}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
