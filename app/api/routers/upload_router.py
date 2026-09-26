"""文件上传接口路由

提供头像上传接口：接收前端压缩后的 data URL，写入阿里云 OSS 后返回公网 URL，
数据库只保存 URL 地址。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, get_oss_service
from app.api.schemas.upload_schema import AvatarUploadRequest, AvatarUploadResponse
from app.entities.user import User
from app.services.oss_service import OSSService

upload_router = APIRouter()


@upload_router.post("/api/upload/avatar", response_model=AvatarUploadResponse)
async def upload_avatar(
    request: AvatarUploadRequest,
    user: Annotated[User, Depends(get_current_user)],
    oss_service: Annotated[OSSService, Depends(get_oss_service)],
):
    """上传当前用户头像，返回 OSS 公网 URL"""
    try:
        url = await oss_service.upload_avatar(user.id, request.image)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AvatarUploadResponse(url=url)
