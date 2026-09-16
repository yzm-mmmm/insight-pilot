"""
`chat_message` ORM 模型

负责定义元数据库中会话消息表的结构。每条消息记录用户问题或智能体回复，
用于恢复多轮上下文；sql 与 result_summary 字段预留给后续富摘要与追溯。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatMessage(Base):
    """会话消息表对应的 ORM 模型"""

    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 用 query_sql 而非 sql：sql 是 MySQL 的关键字，直接作列名会语法报错
    query_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
