"""
评测打分逻辑

围绕「SQL 正确率、召回命中率」提供纯函数打分：
- SQL 正确率：执行结果对拍，比较生成 SQL 与金标准 SQL 的查询结果是否一致，
  结果比较与列名、列顺序无关，并对浮点误差做四舍五入规整；
- 召回命中率：金标准答案所需的关键字段/指标中，被召回链路命中的比例。
"""

from decimal import Decimal


def normalize_cell(value):
    """把单元格值规整成可比较的稳定形式，重点消除浮点与 Decimal 误差"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return round(float(value), 2)
    if isinstance(value, float):
        return round(value, 2)
    return value


def _row_values(row: dict) -> tuple:
    """把一行数据规整成与列名、列顺序都无关的可比较元组"""
    return tuple(sorted(str(normalize_cell(v)) for v in row.values()))


def compare_result(got_rows: list[dict], expected_rows: list[dict]) -> tuple[bool, str]:
    """比较两份查询结果是否一致（行数、列数、数值三重校验）

    采用「执行结果对拍」而非 SQL 文本比对，容忍列别名、列顺序等差异；
    代价是若生成 SQL 与金标准返回了不同列集合，会直接判为不一致。
    """

    if len(got_rows) != len(expected_rows):
        return False, f"行数不一致：生成 {len(got_rows)} 行，期望 {len(expected_rows)} 行"
    got_cols = len(got_rows[0]) if got_rows else 0
    expected_cols = len(expected_rows[0]) if expected_rows else 0
    if got_cols != expected_cols:
        return False, f"列数不一致：生成 {got_cols} 列，期望 {expected_cols} 列"
    got_set = frozenset(_row_values(row) for row in got_rows)
    expected_set = frozenset(_row_values(row) for row in expected_rows)
    if got_set != expected_set:
        return False, "结果数值不一致"
    return True, "一致"


def column_recall_hit(retrieved_column_infos, expect_columns: list[str]) -> float | None:
    """计算关键字段的召回命中率；无期望字段时返回 None 表示不适用"""
    if not expect_columns:
        return None
    retrieved_ids = {column.id for column in retrieved_column_infos}
    hit = len(retrieved_ids & set(expect_columns))
    return hit / len(expect_columns)


def metric_recall_hit(retrieved_metric_infos, expect_metrics: list[str]) -> float | None:
    """计算指标的召回命中率；无期望指标时返回 None 表示不适用"""
    if not expect_metrics:
        return None
    retrieved_names = {metric.name for metric in retrieved_metric_infos}
    hit = len(retrieved_names & set(expect_metrics))
    return hit / len(expect_metrics)
