"""
多轮会话接口路由

提供当前登录用户的会话列表、会话详情、重命名与删除。
所有接口都挂在 get_current_user 上，并按 user_id 过滤，
保证不同账号之间只能访问各自的会话。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_chat_repository, get_current_user
from app.api.schemas.chat_schema import (
    ChatSessionOut,
    RenameRequest,
    SessionDetail,
)
from app.entities.user import User
from app.observability import trace_store
from app.repositories.mysql.meta.chat_repository import ChatRepository

session_router = APIRouter()


@session_router.get("/api/sessions", response_model=list[ChatSessionOut])
async def list_sessions(
    user: Annotated[User, Depends(get_current_user)],
    chat_repository: Annotated[ChatRepository, Depends(get_chat_repository)],
):
    """返回当前用户的会话列表"""
    return await chat_repository.list_by_user(user.id)


@session_router.get("/api/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)],
    chat_repository: Annotated[ChatRepository, Depends(get_chat_repository)],
):
    """返回会话详情与历史消息，校验会话归属"""
    session = await _get_owned_session(session_id, user, chat_repository)
    messages = await chat_repository.get_messages(session_id)
    return SessionDetail(session=session, messages=messages)


@session_router.patch("/api/sessions/{session_id}", response_model=ChatSessionOut)
async def rename_session(
    session_id: int,
    request: RenameRequest,
    user: Annotated[User, Depends(get_current_user)],
    chat_repository: Annotated[ChatRepository, Depends(get_chat_repository)],
):
    """重命名会话，校验会话归属"""
    await _get_owned_session(session_id, user, chat_repository)
    await chat_repository.rename(session_id, request.title)
    return await chat_repository.get_session(session_id)


@session_router.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)],
    chat_repository: Annotated[ChatRepository, Depends(get_chat_repository)],
):
    """删除会话，校验会话归属"""
    await _get_owned_session(session_id, user, chat_repository)
    await chat_repository.delete(session_id)
    return {"ok": True}


@session_router.get("/api/sessions/{session_id}/traces")
async def list_session_traces(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)],
    chat_repository: Annotated[ChatRepository, Depends(get_chat_repository)],
):
    """返回当前会话的全部链路追踪记录，校验会话归属"""
    await _get_owned_session(session_id, user, chat_repository)
    return trace_store.list_traces(session_id)


async def _get_owned_session(
    session_id: int, user: User, chat_repository: ChatRepository
):
    """读取会话并校验归属，非本人会话抛 404，避免越权访问"""
    session = await chat_repository.get_session(session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session
