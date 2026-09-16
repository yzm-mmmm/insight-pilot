"""
`chat_feedback` ORM 模型

记录用户对智能体回答的反馈（赞/踩/纠错）。其中「纠错」会带上用户给出的
正确 SQL 与原错误 SQL，作为后续 SQL 生成的 few-shot 示例，形成在线进化闭环。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatFeedback(Base):
    """消息反馈表对应的 ORM 模型"""

    __tablename__ = "chat_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # like / dislike / correct
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 冗余存储原问题与原 SQL，读取 few-shot 示例时无需跨表 JOIN
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    wrong_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
