"""
可观测性（Observability）模块

提供自建轻量链路追踪：通过 LangChain callback 捕获每次 LLM 调用的 token 消耗与
耗时，配合进度事件统计每个节点的执行耗时，最终把「节点时间线 + LLM 明细 + SQL 历史
+ 重试次数」汇总成结构化 trace 并落盘到 `logs/traces.jsonl`。
"""

from app.observability.trace_store import append_trace, list_traces
from app.observability.tracer import LLMUsageCallbackHandler, TraceCollector

__all__ = [
    "LLMUsageCallbackHandler",
    "TraceCollector",
    "append_trace",
    "list_traces",
]
