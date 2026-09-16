"""
链路追踪（Tracing）

自建轻量 Tracer 的两块核心：
- `TraceCollector`：一次问数查询的 trace 收集器，累积节点跨度、LLM 调用明细；
- `LLMUsageCallbackHandler`：LangChain callback，把每次 LLM 调用的 token 与耗时
  写入收集器，从而回答「每条链路消耗多少 token、花了多少钱、卡在哪个节点」。
"""

import time
import uuid
from dataclasses import asdict, dataclass

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

# deepseek-chat 官方定价（美元 / 1M token），仅用于成本估算，随版本可能调整
PRICE_INPUT_PER_1M = 0.27
PRICE_OUTPUT_PER_1M = 1.10


@dataclass
class NodeSpan:
    """一个节点的一次执行跨度"""

    step: str
    status: str
    started_at: float
    duration_ms: int


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    """按 token 数估算单次 LLM 调用成本（美元）"""
    return (
        prompt_tokens / 1_000_000 * PRICE_INPUT_PER_1M
        + completion_tokens / 1_000_000 * PRICE_OUTPUT_PER_1M
    )


class TraceCollector:
    """一次问数查询的 trace 收集器"""

    def __init__(self, query: str, session_id: int, user_id: int):
        self.trace_id = uuid.uuid4().hex
        self.query = query
        self.session_id = session_id
        self.user_id = user_id
        self.started_at = time.time()
        self.status = "success"
        self.error: str | None = None
        self.node_spans: list[NodeSpan] = []
        self.llm_calls: list[dict] = []
        # step -> started_at，用于把 running 与 success/error 配对成跨度
        self._running_steps: dict[str, float] = {}

    def on_progress(self, step: str, status: str) -> None:
        """根据进度事件记录一个节点的起止跨度"""
        now = time.time()
        if status == "running":
            self._running_steps[step] = now
        else:
            started = self._running_steps.pop(step, now)
            self.node_spans.append(
                NodeSpan(
                    step=step,
                    status=status,
                    started_at=started,
                    duration_ms=int((now - started) * 1000),
                )
            )

    def add_llm_call(self, model, tokens, duration_ms) -> None:
        """记录一次 LLM 调用的模型、token 与耗时"""
        call = {"model": model, "duration_ms": duration_ms}
        if tokens:
            call["prompt_tokens"] = tokens.get("prompt_tokens")
            call["completion_tokens"] = tokens.get("completion_tokens")
            call["total_tokens"] = tokens.get("total_tokens")
            prompt = tokens.get("prompt_tokens")
            completion = tokens.get("completion_tokens")
            if prompt is not None and completion is not None:
                call["cost_usd"] = round(estimate_cost_usd(prompt, completion), 6)
        self.llm_calls.append(call)

    def to_dict(self) -> dict:
        """汇总成可落盘的结构化 trace"""
        total_tokens = sum(call.get("total_tokens") or 0 for call in self.llm_calls)
        total_cost = sum(call.get("cost_usd") or 0 for call in self.llm_calls)
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at,
            "duration_ms": int((time.time() - self.started_at) * 1000),
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(total_cost, 6),
            "llm_call_count": len(self.llm_calls),
            "node_spans": [asdict(span) for span in self.node_spans],
            "llm_calls": self.llm_calls,
        }


class LLMUsageCallbackHandler(BaseCallbackHandler):
    """把 LLM 调用的 token 与耗时写入 TraceCollector"""

    def __init__(self, collector: TraceCollector):
        self.collector = collector
        self._start_times: dict[str, float] = {}

    def on_llm_start(self, serialized, prompts, **kwargs):
        run_id = kwargs.get("run_id")
        if run_id is not None:
            self._start_times[str(run_id)] = time.monotonic()

    def on_llm_end(self, response: LLMResult, **kwargs):
        run_id = str(kwargs.get("run_id", ""))
        started = self._start_times.pop(run_id, None)
        duration_ms = (
            int((time.monotonic() - started) * 1000) if started is not None else None
        )
        self.collector.add_llm_call(
            model=self._extract_model(response),
            tokens=self._extract_tokens(response),
            duration_ms=duration_ms,
        )

    def on_llm_error(self, error, **kwargs):
        run_id = str(kwargs.get("run_id", ""))
        self._start_times.pop(run_id, None)

    @staticmethod
    def _extract_model(response: LLMResult):
        if response.llm_output:
            return response.llm_output.get("model_name")
        return None

    @staticmethod
    def _extract_tokens(response: LLMResult):
        usage = response.llm_output.get("token_usage") if response.llm_output else None
        if usage:
            return {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        # 兜底：从 AIMessage 的 usage_metadata 里取
        for generation in response.generations:
            for chunk in generation:
                message = getattr(chunk, "message", None)
                metadata = getattr(message, "usage_metadata", None)
                if metadata:
                    return {
                        "prompt_tokens": metadata.get("input_tokens"),
                        "completion_tokens": metadata.get("output_tokens"),
                        "total_tokens": metadata.get("total_tokens"),
                    }
        return None
