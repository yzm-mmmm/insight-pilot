"""
反馈接口请求/响应体定义

集中声明提交反馈的输入结构与落库后的返回结构。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.api.schemas.common import UTCDateTime


class FeedbackCreate(BaseModel):
    """提交反馈的请求体"""

    kind: Literal["like", "dislike", "correct"]
    comment: str | None = None
    corrected_sql: str | None = None


class FeedbackOut(BaseModel):
    """反馈落库后的返回体"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    kind: str
    created_at: UTCDateTime
