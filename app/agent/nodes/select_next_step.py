"""
推进分析计划节点

纯游标节点，不调用大模型。反思节点判定“还有子问题未回答”后进入本节点，
把 plan_cursor 前移一位并更新当前子问题，随后回到 SQL 生成环节。
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def select_next_step(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """把当前子问题推进到规划中的下一个"""

    writer = runtime.stream_writer
    step = "推进分析计划"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        plan = state["plan"]
        cursor = state["plan_cursor"] + 1

        # 越界兜底：正常流程不会走到这里，反思节点会在没有剩余时直接 done
        if cursor >= len(plan):
            cursor = len(plan) - 1

        current_question = plan[cursor]["question"]
        logger.info(f"推进到第 {cursor + 1}/{len(plan)} 个子问题：{current_question}")

        writer({"type": "progress", "step": step, "status": "success"})
        return {"plan_cursor": cursor, "current_question": current_question}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
