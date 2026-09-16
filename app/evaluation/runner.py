"""
评测执行器

把一条条评测用例跑过真实 Agent 图：以管理员身份构建 State 与 Runtime Context，
用 `graph.astream(stream_mode="values")` 拿到最终 State，再与金标准 SQL 的执行结果
对拍，产出单条用例的分项得分与诊断信息。

与 QueryService 的 SSE 链路不同，这里不落库、不建会话，只关心最终 State 里
累积出的 SQL 历史、执行结果、召回内容与报告。
"""

from dataclasses import dataclass, field

from app.agent.context import AuthContext, DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.core.log import logger
from app.evaluation.cases import EvalCase
from app.evaluation.scorer import (
    column_recall_hit,
    compare_result,
    metric_recall_hit,
)


@dataclass
class CaseResult:
    """单条用例的评测结果与诊断信息"""

    case_id: str
    question: str
    sql_correct: bool
    sql_detail: str
    column_recall: float | None
    metric_recall: float | None
    e2e_pass: bool
    generated_sql: str | None = None
    error: str | None = None
    diagnostics: dict = field(default_factory=dict)


class EvaluationRunner:
    """对评测集执行一次全量评测"""

    def __init__(
        self,
        meta_mysql_repository,
        dw_mysql_repository,
        column_qdrant_repository,
        metric_qdrant_repository,
        value_es_repository,
        embedding_client,
    ):
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository
        self.embedding_client = embedding_client

    def _build_state(self, case: EvalCase) -> DataAgentState:
        """构造管理员身份的空 State，累积型字段统一初始化为空"""
        return DataAgentState(
            query=case.question,
            user_id=0,
            role="admin",
            scope=None,
            granted_tables=set(),
            intent="",
            plan=[],
            plan_cursor=-1,
            current_question=case.question,
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

    def _build_context(self) -> DataAgentContext:
        return DataAgentContext(
            column_qdrant_repository=self.column_qdrant_repository,
            embedding_client=self.embedding_client,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
            auth_context=AuthContext(user_id=0, role="admin", scope=None),
        )

    async def run_case(self, case: EvalCase) -> CaseResult:
        result = CaseResult(
            case_id=case.id,
            question=case.question,
            sql_correct=False,
            sql_detail="",
            column_recall=None,
            metric_recall=None,
            e2e_pass=False,
        )

        try:
            state = self._build_state(case)
            context = self._build_context()

            # 用 values 模式流式遍历，最后一帧即最终 State（含所有累积字段）
            final_state = None
            async for chunk in graph.astream(
                input=state, context=context, stream_mode="values"
            ):
                final_state = chunk

            # 金标准 SQL 对拍结果
            expected = await self.dw_mysql_repository.run(case.golden_sql)

            executed = final_state.get("executed_results") or []
            result.column_recall = column_recall_hit(
                final_state.get("retrieved_column_infos", []), case.expect_columns
            )
            result.metric_recall = metric_recall_hit(
                final_state.get("retrieved_metric_infos", []), case.expect_metrics
            )

            if executed:
                last = executed[-1]
                result.generated_sql = last.get("sql")
                result.sql_correct, result.sql_detail = compare_result(
                    last.get("rows") or [], expected.get("rows") or []
                )
            else:
                result.generated_sql = final_state.get("sql")
                result.sql_detail = "未执行出任何结果（校验失败或反思提前结束）"

            report = final_state.get("report_markdown") or ""
            result.e2e_pass = bool(report) and bool(executed)

            result.diagnostics = {
                "sql_attempts": len(final_state.get("sql_history", [])),
                "executed_count": len(executed),
                "next_action": (final_state.get("reflection") or {}).get("next_action"),
                "chart_count": len(final_state.get("chart_specs", [])),
                "retrieved_column_count": len(
                    final_state.get("retrieved_column_infos", [])
                ),
                "retrieved_metric_count": len(
                    final_state.get("retrieved_metric_infos", [])
                ),
            }
        except Exception as e:
            result.error = str(e)
            result.sql_detail = f"执行异常：{e}"
            logger.error(f"用例 {case.id} 评测失败：{e}")

        logger.info(
            f"用例 {case.id}：SQL正确={result.sql_correct} "
            f"端到端={result.e2e_pass} 字段召回={result.column_recall} "
            f"指标召回={result.metric_recall}"
        )
        return result


def summarize(results: list[CaseResult]) -> dict:
    """汇总整个评测集的分项得分"""
    total = len(results)
    sql_pass = sum(1 for r in results if r.sql_correct)
    e2e_pass = sum(1 for r in results if r.e2e_pass)
    column_values = [r.column_recall for r in results if r.column_recall is not None]
    metric_values = [r.metric_recall for r in results if r.metric_recall is not None]

    return {
        "total": total,
        "sql_correct": sql_pass,
        "sql_accuracy": round(sql_pass / total, 4) if total else 0.0,
        "e2e_pass": e2e_pass,
        "e2e_accuracy": round(e2e_pass / total, 4) if total else 0.0,
        "column_recall_avg": round(sum(column_values) / len(column_values), 4)
        if column_values
        else None,
        "metric_recall_avg": round(sum(metric_values) / len(metric_values), 4)
        if metric_values
        else None,
    }
