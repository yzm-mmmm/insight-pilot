"""
评测（Evaluation）模块

为问数 Agent 提供系统化评测能力，围绕三个维度打分：
- SQL 正确率：生成 SQL 与金标准 SQL 的执行结果对拍是否一致；
- 召回命中率：金标准答案所需的关键字段/指标被召回链路命中的比例；
- 端到端通过率：链路是否正常走完并产出报告与结果。

入口脚本见 `app/scripts/evaluate.py`，金标准用例集见 `eval/cases.yaml`。
"""

from app.evaluation.cases import EvalCase, load_cases
from app.evaluation.runner import CaseResult, EvaluationRunner, summarize

__all__ = [
    "EvalCase",
    "CaseResult",
    "EvaluationRunner",
    "load_cases",
    "summarize",
]
