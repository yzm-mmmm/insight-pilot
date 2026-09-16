"""
评测用例定义与加载

一条评测用例由「自然语言问题 + 金标准 SQL + 召回期望」组成，是评测集的
原子单位。金标准 SQL 作为执行结果对拍的标准答案，期望字段/指标用于衡量
召回链路是否命中回答该问题所需的元数据。
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class EvalCase:
    """单条问数评测用例"""

    id: str
    question: str
    golden_sql: str
    # 回答该问题所需的关键字段，取值为「表名.字段名」形式（与 ColumnInfo.id 一致）
    expect_columns: list[str] = field(default_factory=list)
    # 回答该问题所依赖的指标名称，例如 GMV / AOV
    expect_metrics: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def load_cases(path: str | Path) -> list[EvalCase]:
    """从 YAML 文件加载评测用例集"""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cases: list[EvalCase] = []
    for item in raw.get("cases", []):
        cases.append(
            EvalCase(
                id=item["id"],
                question=item["question"],
                golden_sql=item["golden_sql"],
                expect_columns=item.get("expect_columns", []),
                expect_metrics=item.get("expect_metrics", []),
                tags=item.get("tags", []),
            )
        )
    return cases
