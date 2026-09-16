"""
表级权限接口路由

提供可申请表清单、我的权限、申请、以及管理员的申请列表与审批接口。
除管理员审批接口外，其余接口只需登录即可访问。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_current_admin,
    get_current_user,
    get_permission_service,
)
from app.api.schemas.permission_schema import (
    ApplyRequest,
    ApplyResult,
    MyPermissionsOut,
    PermissionOut,
    ReviewRequest,
    RevokeResult,
    TableOut,
    UserGrantsOut,
)
from app.entities.user import User
from app.services.permission_service import PermissionService

permission_router = APIRouter()


@permission_router.get("/api/permissions/tables", response_model=list[TableOut])
async def list_tables(
    user: Annotated[User, Depends(get_current_user)],
    permission_service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """返回所有可申请的数据表"""
    return await permission_service.list_tables()


@permission_router.get("/api/permissions/my", response_model=MyPermissionsOut)
async def my_permissions(
    user: Annotated[User, Depends(get_current_user)],
    permission_service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """返回当前用户的已授权表名与申请记录"""
    return await permission_service.my_permissions(user)


@permission_router.post("/api/permissions/apply", response_model=ApplyResult)
async def apply(
    request: ApplyRequest,
    user: Annotated[User, Depends(get_current_user)],
    permission_service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """提交表权限申请"""
    try:
        created = await permission_service.apply(user, request.tables)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ApplyResult(created=created)


@permission_router.get("/api/permissions/requests", response_model=list[PermissionOut])
async def list_requests(
    admin: Annotated[User, Depends(get_current_admin)],
    permission_service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """管理员查看全部申请记录"""
    return await permission_service.list_requests()


@permission_router.get(
    "/api/permissions/users", response_model=list[UserGrantsOut]
)
async def list_user_grants(
    admin: Annotated[User, Depends(get_current_admin)],
    permission_service: Annotated[PermissionService, Depends(get_permission_service)],
    search: str | None = None,
):
    """管理员查看所有用户及其已授权表，可按用户名/昵称搜索"""
    return await permission_service.list_user_grants(search)


@permission_router.delete(
    "/api/permissions/grants/{user_id}/{table_name}", response_model=RevokeResult
)
async def revoke_grant(
    user_id: int,
    table_name: str,
    admin: Annotated[User, Depends(get_current_admin)],
    permission_service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """管理员取消某用户某张表的授权"""
    try:
        await permission_service.revoke(user_id, table_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RevokeResult(ok=True)


@permission_router.post(
    "/api/permissions/{permission_id}/review", response_model=PermissionOut
)
async def review(
    permission_id: int,
    request: ReviewRequest,
    admin: Annotated[User, Depends(get_current_admin)],
    permission_service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """管理员审批申请（approved / rejected）"""
    try:
        return await permission_service.review(admin, permission_id, request.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
