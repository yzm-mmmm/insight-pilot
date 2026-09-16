"""
trace 持久化存储

把每次问数的结构化 trace 追加写入 `logs/traces.jsonl`（一行一条），并提供按会话
读取的能力。选用 JSONL 而非数据库，是为了避免额外的表结构迁移，且方便直接
`tail` / `grep` 查看原始记录。
"""

import json
from pathlib import Path

# 项目根目录下的日志目录，与 app_config 里 logging.file.path 保持一致
_TRACE_DIR = Path(__file__).parents[2] / "logs"
_TRACE_FILE = _TRACE_DIR / "traces.jsonl"


def append_trace(trace: dict) -> None:
    """追加一条 trace 记录到 JSONL 文件"""
    _TRACE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")


def list_traces(session_id: int) -> list[dict]:
    """按会话读取 trace，按开始时间倒序返回"""
    if not _TRACE_FILE.exists():
        return []
    traces: list[dict] = []
    with open(_TRACE_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("session_id") == session_id:
                traces.append(record)
    return sorted(traces, key=lambda t: t.get("started_at", 0), reverse=True)
