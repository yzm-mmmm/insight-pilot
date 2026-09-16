"""
电商问数 Agent 图编排

使用 LangGraph 把自主数据分析的各个节点串成一条可观测的执行链路：
先理解规划，再做多路召回与上下文过滤，随后进入
「生成 SQL → 校验 → 执行 → 反思」的自主循环。

反思节点根据执行结果决定重试、推进下一个子问题或结束；
SQL 校验修正和反思迭代都受配置上限约束，保证流程不会死循环。
"""

import asyncio

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from app.agent.context import AuthContext, DataAgentContext
from app.agent.nodes.add_extra_context import add_extra_context
from app.agent.nodes.correct_sql import correct_sql
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.filter_metric import filter_metric
from app.agent.nodes.filter_table import filter_table
from app.agent.nodes.generate_charts import generate_charts
from app.agent.nodes.generate_report import generate_report
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.give_up import give_up
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_metric import recall_metric
from app.agent.nodes.recall_value import recall_value
from app.agent.nodes.reflect import reflect
from app.agent.nodes.run_sql import run_sql
from app.agent.nodes.select_next_step import select_next_step
from app.agent.nodes.understand_plan import understand_plan
from app.agent.nodes.validate_sql import validate_sql
from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.conf.app_config import app_config
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

# StateGraph 声明整张图使用的状态结构和运行时上下文结构
graph_builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)

# 注册节点：理解规划与检索链路 + 自主分析循环
graph_builder.add_node("understand_plan", understand_plan)
graph_builder.add_node("extract_keywords", extract_keywords)
graph_builder.add_node("recall_column", recall_column)
graph_builder.add_node("recall_value", recall_value)
graph_builder.add_node("recall_metric", recall_metric)
graph_builder.add_node("merge_retrieved_info", merge_retrieved_info)
graph_builder.add_node("filter_metric", filter_metric)
graph_builder.add_node("filter_table", filter_table)
graph_builder.add_node("add_extra_context", add_extra_context)
graph_builder.add_node("select_next_step", select_next_step)
graph_builder.add_node("generate_sql", generate_sql)
graph_builder.add_node("validate_sql", validate_sql)
graph_builder.add_node("correct_sql", correct_sql)
graph_builder.add_node("run_sql", run_sql)
graph_builder.add_node("reflect", reflect)
graph_builder.add_node("give_up", give_up)
graph_builder.add_node("generate_charts", generate_charts)
graph_builder.add_node("generate_report", generate_report)

# 入口：先理解并规划，再抽取关键词
graph_builder.add_edge(START, "understand_plan")
graph_builder.add_edge("understand_plan", "extract_keywords")

# 关键词抽取后并行进入三类召回
graph_builder.add_edge("extract_keywords", "recall_column")
graph_builder.add_edge("extract_keywords", "recall_value")
graph_builder.add_edge("extract_keywords", "recall_metric")

# 三路召回合并，再并行做表过滤和指标过滤
graph_builder.add_edge("recall_column", "merge_retrieved_info")
graph_builder.add_edge("recall_value", "merge_retrieved_info")
graph_builder.add_edge("recall_metric", "merge_retrieved_info")
graph_builder.add_edge("merge_retrieved_info", "filter_table")
graph_builder.add_edge("merge_retrieved_info", "filter_metric")

# 过滤完成后补齐日期/数据库环境上下文，再进入自主分析循环
graph_builder.add_edge("filter_table", "add_extra_context")
graph_builder.add_edge("filter_metric", "add_extra_context")
graph_builder.add_edge("add_extra_context", "select_next_step")
graph_builder.add_edge("select_next_step", "generate_sql")
graph_builder.add_edge("generate_sql", "validate_sql")


def after_validate(state: DataAgentState) -> str:
    """校验通过去执行；失败且未超限去修正；超限则兜底结束"""
    error = state["error"]
    if error is None:
        return "run_sql"
    # 表级权限错误无法靠 SQL 修正解决，直接兜底结束并提示用户申请
    if error.startswith("无权访问表"):
        return "give_up"
    if state["sql_retry_count"] >= app_config.agent.max_sql_retries:
        return "give_up"
    return "correct_sql"


graph_builder.add_conditional_edges(source="validate_sql", path=after_validate)
graph_builder.add_edge("correct_sql", "validate_sql")
graph_builder.add_edge("give_up", END)
graph_builder.add_edge("run_sql", "reflect")


def after_reflect(state: DataAgentState) -> str:
    """反思结论决定：重试 SQL、推进下一个子问题、追问用户，还是收尾画图写报告"""
    action = state["reflection"]["next_action"] if state.get("reflection") else "done"
    if action == "retry_sql":
        return "generate_sql"
    if action == "new_sub_question":
        return "select_next_step"
    if action == "ask_user":
        return END
    # done / 其他兜底都进入收尾阶段：先画图再写报告
    return "generate_charts"


graph_builder.add_conditional_edges(source="reflect", path=after_reflect)
graph_builder.add_edge("generate_charts", "generate_report")
graph_builder.add_edge("generate_report", END)

# 编译后的 graph 是对外使用的 Agent 执行入口
graph = graph_builder.compile()

# print(graph.get_graph().draw_mermaid())

if __name__ == "__main__":

    async def test():
        """本地调试理解规划 + 多路召回 + 自主分析循环链路"""

        qdrant_client_manager.init()
        embedding_client_manager.init()
        es_client_manager.init()
        meta_mysql_client_manager.init()
        dw_mysql_client_manager.init()

        async with (
            meta_mysql_client_manager.session_factory() as meta_session,
            dw_mysql_client_manager.session_factory() as dw_session,
        ):
            meta_mysql_repository = MetaMySQLRepository(meta_session)
            dw_mysql_repository = DWMySQLRepository(dw_session)

            column_qdrant_repository = ColumnQdrantRepository(
                qdrant_client_manager.client
            )
            metric_qdrant_repository = MetricQdrantRepository(
                qdrant_client_manager.client
            )
            value_es_repository = ValueESRepository(es_client_manager.client)

            # 与 query_service 保持一致，累积型字段统一初始化为空
            state = DataAgentState(
                query="统计华北地区的销售总额",
                user_id=0,
                role="admin",
                scope=None,
                granted_tables=set(),
                intent="",
                plan=[],
                plan_cursor=-1,
                current_question="",
                iteration_count=0,
                sql_retry_count=0,
                reflection=None,
                keywords=[],
                retrieved_column_infos=[],
                retrieved_metric_infos=[],
                retrieved_value_infos=[],
                table_infos=[],
                metric_infos=[],
                date_info=None,
                db_info=None,
                sql="",
                error=None,
                sql_history=[],
                executed_results=[],
                insights=[],
                chart_specs=[],
                conversation_history=[],
                feedback_examples=[],
                report_markdown="",
            )
            context = DataAgentContext(
                column_qdrant_repository=column_qdrant_repository,
                embedding_client=embedding_client_manager.client,
                metric_qdrant_repository=metric_qdrant_repository,
                value_es_repository=value_es_repository,
                meta_mysql_repository=meta_mysql_repository,
                dw_mysql_repository=dw_mysql_repository,
                auth_context=AuthContext(user_id=0, role="admin", scope=None),
            )

            async for chunk in graph.astream(
                input=state, context=context, stream_mode="custom"
            ):
                print(chunk)

        await qdrant_client_manager.close()
        await es_client_manager.close()
        await meta_mysql_client_manager.close()
        await dw_mysql_client_manager.close()

    asyncio.run(test())
