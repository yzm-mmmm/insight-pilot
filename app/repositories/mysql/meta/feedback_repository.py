"""
反馈仓储

负责 `chat_feedback` 表的读写：记录用户的赞/踩/纠错，并把带正确 SQL 的纠错
记录读取为 SQL 生成的 few-shot 示例，作为在线进化闭环的数据来源。
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_feedback import ChatFeedback


class FeedbackRepository:
    """负责反馈的增删改查"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self,
        message_id: int,
        session_id: int,
        user_id: int,
        kind: str,
        comment: str | None,
        corrected_sql: str | None,
        question: str | None,
        wrong_sql: str | None,
    ) -> ChatFeedback:
        """追加一条反馈并提交"""
        model = ChatFeedback(
            message_id=message_id,
            session_id=session_id,
            user_id=user_id,
            kind=kind,
            comment=comment,
            corrected_sql=corrected_sql,
            question=question,
            wrong_sql=wrong_sql,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.commit()
        return model

    async def delete_by_user(self, user_id: int) -> None:
        """删除某用户的全部反馈（flush，提交由调用方事务控制）"""
        await self.session.execute(
            delete(ChatFeedback).where(ChatFeedback.user_id == user_id)
        )
        await self.session.flush()

    async def list_correct_examples(self, limit: int = 5) -> list[dict]:
        """返回最近若干条带正确 SQL 的纠错记录，作为 SQL 生成 few-shot 示例"""
        result = await self.session.execute(
            select(ChatFeedback)
            .where(
                ChatFeedback.kind == "correct",
                ChatFeedback.corrected_sql.is_not(None),
            )
            .order_by(ChatFeedback.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "question": row.question,
                "wrong_sql": row.wrong_sql,
                "corrected_sql": row.corrected_sql,
            }
            for row in rows
        ]
