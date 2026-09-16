"""
反馈接口路由

提供对单条智能体消息提交反馈的接口（赞/踩/纠错）。
纠错会带上正确 SQL，作为后续 SQL 生成的 few-shot 示例，形成在线进化闭环。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_chat_repository,
    get_current_user,
    get_feedback_repository,
)
from app.api.schemas.feedback_schema import FeedbackCreate, FeedbackOut
from app.entities.user import User
from app.repositories.mysql.meta.chat_repository import ChatRepository
from app.repositories.mysql.meta.feedback_repository import FeedbackRepository

feedback_router = APIRouter()


@feedback_router.post("/api/messages/{message_id}/feedback", response_model=FeedbackOut)
async def submit_feedback(
    message_id: int,
    request: FeedbackCreate,
    user: Annotated[User, Depends(get_current_user)],
    chat_repository: Annotated[ChatRepository, Depends(get_chat_repository)],
    feedback_repository: Annotated[FeedbackRepository, Depends(get_feedback_repository)],
):
    """对一条智能体消息提交反馈，校验消息归属"""
    message = await chat_repository.get_message(message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="消息不存在")
    session = await chat_repository.get_session(message.session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="消息不存在")

    # 原问题 = 同会话中该消息之前最近一条用户消息
    question = await _find_question(chat_repository, message.session_id, message_id)

    return await feedback_repository.save(
        message_id=message_id,
        session_id=message.session_id,
        user_id=user.id,
        kind=request.kind,
        comment=request.comment,
        corrected_sql=request.corrected_sql,
        question=question,
        wrong_sql=message.query_sql,
    )


async def _find_question(
    chat_repository: ChatRepository, session_id: int, message_id: int
) -> str | None:
    """返回该消息之前最近一条用户消息内容，作为纠错示例的「问题」"""
    messages = await chat_repository.get_messages(session_id)
    for message in reversed(messages):
        if message.id < message_id and message.role == "user" and message.content:
            return message.content
    return None
