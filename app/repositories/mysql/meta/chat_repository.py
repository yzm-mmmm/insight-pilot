"""
会话与消息仓储

负责 `chat_session` 与 `chat_message` 两张表的读写，是多轮会话持久化的唯一入口。
会话按 user_id 隔离；消息按 created_at 升序读取，用于恢复上下文。
写方法各自提交事务，避免与元数据检索链路共享的隐式事务相互嵌套。
"""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession


class ChatRepository:
    """负责会话与消息的增删改查"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, user_id: int, title: str = "新会话") -> ChatSession:
        """新建会话并返回带自增主键的会话模型"""
        model = ChatSession(user_id=user_id, title=title or "新会话")
        self.session.add(model)
        await self.session.flush()
        await self.session.commit()
        return model

    async def list_by_user(self, user_id: int) -> list[ChatSession]:
        """返回指定用户的会话列表，按最近更新时间倒序"""
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_session(self, session_id: int) -> ChatSession | None:
        """按主键查询会话，供归属校验使用"""
        return await self.session.get(ChatSession, session_id)

    async def get_message(self, message_id: int) -> ChatMessage | None:
        """按主键查询单条消息，供反馈归属校验使用"""
        return await self.session.get(ChatMessage, message_id)

    async def rename(self, session_id: int, title: str) -> None:
        """重命名会话"""
        model = await self.session.get(ChatSession, session_id)
        if model:
            model.title = title
            await self.session.commit()

    async def delete(self, session_id: int) -> None:
        """删除会话（消息记录由外键级联或另行清理）"""
        model = await self.session.get(ChatSession, session_id)
        if model:
            await self.session.delete(model)
            await self.session.commit()

    async def get_messages(self, session_id: int) -> list[ChatMessage]:
        """按时间升序读取会话内的全部消息"""
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars().all())

    async def save_message(
        self,
        session_id: int,
        role: str,
        content: str | None = None,
        query_sql: str | None = None,
        result_summary: str | None = None,
    ) -> ChatMessage:
        """追加一条消息并提交"""
        model = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            query_sql=query_sql,
            result_summary=result_summary,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.commit()
        return model

    async def touch_session(self, session_id: int) -> None:
        """刷新会话的更新时间，使会话列表按最近活跃排序"""
        model = await self.session.get(ChatSession, session_id)
        if model:
            model.updated_at = datetime.utcnow()
            await self.session.commit()

    async def delete_by_user(self, user_id: int) -> None:
        """删除某用户的全部消息与会话（chat_message 只挂 session_id，需先取会话 id）"""
        session_ids = select(ChatSession.id).where(ChatSession.user_id == user_id)
        await self.session.execute(
            delete(ChatMessage).where(ChatMessage.session_id.in_(session_ids))
        )
        await self.session.execute(
            delete(ChatSession).where(ChatSession.user_id == user_id)
        )
        await self.session.flush()
