"""
鉴权接口路由

提供注册、登录和查询当前用户三个接口。登录/注册成功后返回 JWT，
前端拿到后放进 Authorization 头，后续请求由 get_current_user 校验。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_auth_service, get_current_user
from app.api.schemas.auth_schema import (
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.entities.user import User
from app.services.auth_service import AuthService

auth_router = APIRouter()


@auth_router.post("/api/auth/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """注册新用户，成功后直接返回登录令牌"""
    try:
        token, user = await auth_service.register(request.username, request.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _build_token_response(token, user)


@auth_router.post("/api/auth/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """登录并签发令牌"""
    try:
        token, user = await auth_service.login(request.username, request.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return _build_token_response(token, user)


@auth_router.get("/api/auth/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    """返回当前登录用户信息，供前端启动时校验 token 是否有效"""
    return _build_user_out(user)


@auth_router.patch("/api/auth/profile", response_model=UserOut)
async def update_profile(
    request: ProfileUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """更新当前用户的昵称与头像"""
    updated = await auth_service.update_profile(user.id, request.nickname, request.avatar)
    return _build_user_out(updated)


@auth_router.patch("/api/auth/password")
async def change_password(
    request: PasswordChangeRequest,
    user: Annotated[User, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """修改当前用户的密码，需校验原密码"""
    try:
        await auth_service.change_password(user.id, request.old_password, request.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


def _build_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        disabled=user.disabled,
        nickname=user.nickname,
        avatar=user.avatar,
    )


def _build_token_response(token: str, user: User) -> TokenResponse:
    return TokenResponse(access_token=token, user=_build_user_out(user))
