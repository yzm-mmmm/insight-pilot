"""
SQL 修正失败兜底节点

当同一条 SQL 在校验-修正循环里反复失败、超过最大修正次数时进入本节点，
把最终错误通过 SSE 告知用户后结束流程，避免无限循环。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def give_up(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """在 SQL 多次修正仍失败时兜底结束并反馈错误"""

    writer = runtime.stream_writer
    error = state["error"]
    logger.info(f"SQL 多次修正后仍失败，结束流程：{error}")

    # 表级权限错误无法靠 SQL 修正解决，单独提示用户申请相关表权限
    if error and error.startswith("无权访问表"):
        message = f"本次查询未执行：{error}"
    else:
        message = f"SQL 多次修正后仍无法通过校验：{error}"
    writer({"type": "error", "message": message})
    return {}
