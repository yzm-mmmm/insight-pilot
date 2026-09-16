"""
用户管理接口路由

提供管理员视角的用户列表、重置密码与删除用户三个接口，
全部受 get_current_admin 守卫，普通用户访问返回 403。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_admin_service, get_current_admin
from app.api.schemas.admin_schema import (
    AdminOkOut,
    AdminResetPasswordRequest,
    AdminUserOut,
)
from app.entities.user import User
from app.services.admin_service import AdminService

admin_router = APIRouter()


@admin_router.get("/api/admin/users", response_model=list[AdminUserOut])
async def list_users(
    admin: Annotated[User, Depends(get_current_admin)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    search: str | None = None,
):
    """管理员查看全部用户，可按用户名或昵称模糊搜索"""
    return await admin_service.list_users(search)


@admin_router.post(
    "/api/admin/users/{user_id}/password", response_model=AdminOkOut
)
async def reset_password(
    user_id: int,
    request: AdminResetPasswordRequest,
    admin: Annotated[User, Depends(get_current_admin)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
):
    """管理员重置某用户密码"""
    try:
        await admin_service.reset_password(user_id, request.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AdminOkOut(ok=True)


@admin_router.delete("/api/admin/users/{user_id}", response_model=AdminOkOut)
async def delete_user(
    user_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
):
    """管理员删除某用户及其会话、消息、反馈与权限记录"""
    try:
        await admin_service.delete_user(admin, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AdminOkOut(ok=True)
