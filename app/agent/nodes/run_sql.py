"""
SQL 执行节点

负责执行当前子问题的 SQL，并把富结果（问题、SQL、列名、数据行）写入
executed_results，供反思、画图和报告节点复用。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, ExecutionResultState
from app.core.log import logger


async def run_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """执行 SQL 并产出富结果"""

    writer = runtime.stream_writer
    step = "执行SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        sql = state["sql"]
        current_question = state["current_question"]
        dw_mysql_repository = runtime.context["dw_mysql_repository"]

        # 管理员不受表级限制；普通用户只允许访问已授权的表
        allowed_tables = None if state["role"] == "admin" else state["granted_tables"]

        # run 内部先做只读与表级白名单校验，再执行，返回 {columns, rows}
        result = await dw_mysql_repository.run(sql, allowed_tables=allowed_tables)
        columns = result["columns"]
        rows = result["rows"]

        execution = ExecutionResultState(
            question=current_question, sql=sql, columns=columns, rows=rows
        )
        logger.info(f"SQL执行结果行数：{len(rows)}")
        writer({"type": "progress", "step": step, "status": "success"})
        writer({"type": "result", "data": {"columns": columns, "rows": rows, "sql": sql}})
        return {"executed_results": [execution]}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
