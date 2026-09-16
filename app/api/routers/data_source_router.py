"""
数据源接口路由

提供数据源列表、接入申请、审批、重同步与删除接口。除审批/重同步/删除外，
其余接口只需登录即可访问；审批通过后在后台触发全量同步与增量订阅。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_current_admin,
    get_current_user,
    get_data_source_service,
)
from app.api.schemas.data_source_schema import (
    DataSourceCreateRequest,
    DataSourceOut,
    ReviewRequest,
    SyncResult,
)
from app.entities.user import User
from app.services.data_source_service import DataSourceService

data_source_router = APIRouter()


@data_source_router.get("/api/data-sources", response_model=list[DataSourceOut])
async def list_data_sources(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
):
    """管理员查看全部数据源，普通用户查看自己提交的申请"""
    return await service.list(user)


@data_source_router.post("/api/data-sources/apply", response_model=DataSourceOut)
async def apply_data_source(
    request: DataSourceCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
):
    """提交接入数据库申请，等待管理员审批"""
    return await service.apply(user, request)


@data_source_router.post(
    "/api/data-sources/{source_id}/review", response_model=DataSourceOut
)
async def review_data_source(
    source_id: int,
    request: ReviewRequest,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
):
    """管理员审批申请（approved / rejected），通过后触发全量同步"""
    try:
        return await service.review(admin, source_id, request.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@data_source_router.post(
    "/api/data-sources/{source_id}/resync", response_model=SyncResult
)
async def resync_data_source(
    source_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
):
    """管理员手动触发全量重同步"""
    try:
        return await service.resync(source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@data_source_router.delete("/api/data-sources/{source_id}", response_model=SyncResult)
async def delete_data_source(
    source_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
):
    """管理员删除数据源：停增量线程、删镜像表、清元数据并删除记录"""
    try:
        await service.delete(source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SyncResult(ok=True, status="deleted")
