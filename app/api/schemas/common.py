"""
公共响应字段类型

后端统一用 UTC 无时区时间入库，出参时补齐 UTC 时区并序列化为带
``Z`` 的 ISO 字符串，让前端 ``new Date()`` 能正确解析并转成用户本地时间。
"""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer


def _as_utc_iso(value: datetime | None) -> str | None:
    """把库里的 naive UTC 时间序列化为带 ``Z`` 的 ISO 字符串"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


# 非空时间字段（如会话 created_at / updated_at）
UTCDateTime = Annotated[
    datetime,
    PlainSerializer(_as_utc_iso, return_type=str | None, when_used="json"),
]

# 可空时间字段（如申请/审批时间）
UTCOptionalDateTime = Annotated[
    datetime | None,
    PlainSerializer(_as_utc_iso, return_type=str | None, when_used="json"),
]
