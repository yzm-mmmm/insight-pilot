"""
问数查询服务

负责把 API 层传入的自然语言问题转换成一次 LangGraph 工作流执行：
创建初始 State、组装 Runtime Context、消费 graph.astream 的流式输出，
并统一包装成 SSE 文本返回给路由层。

State 里的累积型字段（operator.add reducer）必须在这里统一初始化为空，
否则图首次写入时 reducer 会因缺失初始值而报错。
同时负责多轮会话的建立与消息持久化：空 thread_id 开启新会话，
非空则恢复历史上下文并在结束时写回本轮消息。
"""

import json

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.agent.context import AuthContext, DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.core.log import logger
from app.core.runtime_model import runtime_model
from app.entities.user import User
from app.observability.model_price import price_cache
from app.observability.trace_store import append_trace
from app.observability.tracer import LLMUsageCallbackHandler, TraceCollector
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.chat_repository import ChatRepository
from app.repositories.mysql.meta.feedback_repository import FeedbackRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.mysql.meta.permission_repository import PermissionRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

# 追问时最多注入的历史消息条数，避免上下文过长
MAX_HISTORY_MESSAGES = 6


class QueryService:
    """封装一次问数查询所需的业务编排逻辑"""

    def __init__(
        self,
        meta_mysql_repository: MetaMySQLRepository,
        embedding_client: HuggingFaceEndpointEmbeddings,
        dw_mysql_repository: DWMySQLRepository,
        column_qdrant_repository: ColumnQdrantRepository,
        metric_qdrant_repository: MetricQdrantRepository,
        value_es_repository: ValueESRepository,
    ):
        # MySQL 仓储分别负责元数据补全和真实数仓环境信息读取
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository

        # 召回链路依赖的向量检索、Embedding 和全文检索能力由依赖层注入
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository

    async def query(
        self, query: str, user: User | None = None, thread_id: int | None = None
    ):
        """执行一次问数工作流，并逐段产出 SSE 消息；同时完成多轮会话持久化"""

        # 复用元数据仓储的 Session 做会话读写，避免为聊天再开一条连接
        chat_repository = ChatRepository(self.meta_mysql_repository.session)
        feedback_repository = FeedbackRepository(self.meta_mysql_repository.session)
        user_id = user.id if user else 0
        conversation_history: list[dict] = []

        # 表级权限：管理员不受限；普通用户先查出已授权表，空权限直接短路返回
        is_admin = (user.role if user else "user") == "admin"
        granted_tables: set[str] = set()
        if user and not is_admin:
            permission_repository = PermissionRepository(
                self.meta_mysql_repository.session
            )
            granted_tables = await permission_repository.list_approved_tables(user_id)
            if not granted_tables:
                available = await self.dw_mysql_repository.list_tables()
                tables = "、".join(available) or "（暂无）"
                message = (
                    "当前账号暂无任何表的查询权限，请点击右上角盾牌图标申请后再查询。"
                    f"可申请的表：{tables}"
                )
                yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False, default=str)}\n\n"
                return

        # 会话建立：无 thread_id 时新建会话，并把会话编号作为首个 SSE 事件告知前端
        if thread_id is None:
            session = await chat_repository.create_session(
                user_id, title=query[:20] or "新会话"
            )
            thread_id = session.id
            yield f"data: {json.dumps({'type': 'session', 'id': thread_id, 'title': session.title}, ensure_ascii=False, default=str)}\n\n"
        else:
            # 追问：读取历史消息作为多轮上下文，供理解规划节点解析指代
            messages = await chat_repository.get_messages(thread_id)
            conversation_history = [
                {"role": m.role, "content": m.content}
                for m in messages
                if m.content
            ][-MAX_HISTORY_MESSAGES:]

        # 先把本轮用户问题落库，即使后续执行失败也能在历史里看到这轮提问
        await chat_repository.save_message(thread_id, "user", content=query)

        # 反馈闭环：读取最近若干条带正确 SQL 的纠错，作为 SQL 生成的 few-shot 示例
        # 表尚未建好时失败不阻断查询，退化为不使用 few-shot
        try:
            feedback_examples = await feedback_repository.list_correct_examples(limit=5)
        except Exception as e:
            logger.warning(f"读取反馈示例失败，本次不使用 few-shot：{e}")
            feedback_examples = []

        state = DataAgentState(
            query=query,
            user_id=user_id,
            role=user.role if user else "user",
            scope=user.scope if user else None,
            granted_tables=granted_tables,
            intent="",
            plan=[],
            plan_cursor=-1,
            current_question=query,
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
            conversation_history=conversation_history,
            feedback_examples=feedback_examples,
            report_markdown="",
        )

        context = DataAgentContext(
            column_qdrant_repository=self.column_qdrant_repository,
            embedding_client=self.embedding_client,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
            auth_context=AuthContext(
                user_id=user_id,
                role=user.role if user else "user",
                scope=user.scope if user else None,
            ),
        )

        report_markdown = ""
        result_rows: list = []
        chart_specs: list = []
        last_sql: str | None = None

        # 链路追踪：收集器累计节点时间线与 LLM 调用明细，callback 负责捕获 token/耗时
        # 提前解析本次调用的模型价格（懒加载 + 当天缓存），用于汇总本次总成本
        try:
            price = await price_cache.get_price(runtime_model.current())
        except Exception as e:
            logger.warning(f"获取模型价格失败，本次成本记为 0：{e}")
            price = None
        collector = TraceCollector(
            query=query, session_id=thread_id, user_id=user_id, price=price
        )
        llm_handler = LLMUsageCallbackHandler(collector)
        final_state: dict | None = None

        try:
            async for mode, chunk in graph.astream(
                input=state,
                config={"callbacks": [llm_handler]},
                context=context,
                stream_mode=["custom", "values"],
            ):
                if mode == "custom":
                    # SSE 要求每条消息以 data: 开头，并以两个换行符结束
                    yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
                    if isinstance(chunk, dict):
                        if chunk.get("type") == "report":
                            report_markdown = chunk.get("markdown") or ""
                        elif chunk.get("type") == "result":
                            data = chunk.get("data")
                            result_rows.append(data)
                            if isinstance(data, dict) and data.get("sql"):
                                last_sql = data.get("sql")
                        elif chunk.get("type") == "chart":
                            chart_specs.append(chunk.get("data"))
                        elif chunk.get("type") == "progress":
                            collector.on_progress(
                                chunk.get("step"), chunk.get("status")
                            )
                else:
                    # "values" 模式吐出的完整状态，最后一帧即最终 State
                    final_state = chunk
        except Exception as e:
            collector.status = "error"
            collector.error = str(e)
            # 流式接口已经开始返回后不能再改 HTTP 状态码，因此把异常也包装成一条 SSE 消息
            error = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error, ensure_ascii=False, default=str)}\n\n"

        # 结构化结果、图表与报告统一落库到 result_summary，便于历史会话完整回放；
        # content 仍保存报告正文，作为多轮追问的历史上下文与旧会话兜底展示
        payload = {
            "report": report_markdown or None,
            "results": result_rows,
            "charts": chart_specs,
        }
        result_summary = json.dumps(payload, ensure_ascii=False, default=str)
        if report_markdown:
            assistant_content = report_markdown
        elif result_rows:
            total = sum(
                len(row.get("rows", []))
                for row in result_rows
                if isinstance(row, dict)
            )
            assistant_content = f"查询完成，共 {total} 行结果。"
        else:
            assistant_content = "本次查询未返回结果。"
        assistant_message = None
        try:
            assistant_message = await chat_repository.save_message(
                thread_id,
                "assistant",
                content=assistant_content,
                query_sql=last_sql,
                result_summary=result_summary,
            )
            await chat_repository.touch_session(thread_id)
            # 回传助手消息的数据库主键，供前端对这条回答提交反馈
            yield f"data: {json.dumps({'type': 'message_saved', 'id': assistant_message.id}, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            logger.error(f"持久化会话消息失败：{e}")

        # 链路追踪落盘：即使消息持久化失败也不影响 trace 记录
        try:
            trace = collector.to_dict()
            trace["message_id"] = assistant_message.id if assistant_message else None
            if final_state:
                trace["sql_history"] = final_state.get("sql_history") or []
                trace["sql_retry_count"] = final_state.get("sql_retry_count") or 0
                trace["iteration_count"] = final_state.get("iteration_count") or 0
                reflection = final_state.get("reflection") or {}
                trace["next_action"] = reflection.get("next_action")
                trace["chart_count"] = len(final_state.get("chart_specs") or [])
            append_trace(trace)
            logger.info(
                f"链路追踪 {trace['trace_id']}：{trace['total_tokens']} tokens、"
                f"{trace['llm_call_count']} 次 LLM 调用、耗时 {trace['duration_ms']}ms、"
                f"成本 {trace['total_cost_cny']} 元"
            )
        except Exception as e:
            logger.error(f"链路追踪落盘失败：{e}")
