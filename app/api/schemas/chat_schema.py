"""
会话接口请求/响应体定义

集中声明会话列表、会话详情等接口的输入输出结构，
配合 ORM 模型通过 from_attributes 直接序列化，避免手写字段拷贝。
"""

from pydantic import BaseModel, ConfigDict

from app.api.schemas.common import UTCDateTime


class ChatSessionOut(BaseModel):
    """会话列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ChatMessageOut(BaseModel):
    """会话历史消息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str | None
    query_sql: str | None
    result_summary: str | None
    created_at: UTCDateTime


class SessionDetail(BaseModel):
    """会话详情：会话元信息 + 历史消息"""

    session: ChatSessionOut
    messages: list[ChatMessageOut]


class RenameRequest(BaseModel):
    """重命名会话请求体"""

    title: str
