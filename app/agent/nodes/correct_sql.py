"""
SQL 修正节点

负责在 SQL 校验失败后，结合原问题 当前子问题 原 SQL 数据库错误和完整上下文
做最小必要修正。只有 validate_sql 写入错误信息时，LangGraph 才会进入这个分支。
每次修正都会累加 sql_retry_count，供图上的条件边判断是否超过最大修正次数。
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


async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """根据校验错误修正 SQL，并累加修正计数"""

    writer = runtime.stream_writer
    step = "校正SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        date_info = state["date_info"]
        db_info = state["db_info"]
        query = state["query"]
        current_question = state["current_question"]
        sql = state["sql"]
        error = state["error"]
        sql_history = state["sql_history"]
        sql_retry_count = state["sql_retry_count"]
        feedback_examples = state.get("feedback_examples", [])

        prompt = PromptTemplate(
            template=load_prompt("correct_sql"),
            input_variables=[
                "table_infos",
                "metric_infos",
                "date_info",
                "db_info",
                "query",
                "current_question",
                "sql",
                "error",
                "sql_history",
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
                "sql": sql,
                "error": error,
                "sql_history": yaml.dump(
                    sql_history, allow_unicode=True, sort_keys=False
                )
                if sql_history
                else "（暂无）",
                "feedback_examples": yaml.dump(
                    feedback_examples, allow_unicode=True, sort_keys=False
                )
                if feedback_examples
                else "（暂无）",
            }
        )

        sql = normalize_sql(result)
        logger.info(f"校正后的SQL：{sql}")
        writer({"type": "progress", "step": step, "status": "success"})
        return {
            "sql": sql,
            "sql_history": [sql],
            "sql_retry_count": sql_retry_count + 1,
        }

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
