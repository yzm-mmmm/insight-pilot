"""系统设置接口路由

提供管理员专用的运行时模型切换与 DeepSeek 余额查询接口，全部受
get_current_admin 守卫，普通用户访问返回 403。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_admin, get_deepseek_service
from app.api.schemas.system_schema import (
    DeepSeekBalanceResponse,
    ModelSettingRequest,
    ModelSettingResponse,
)
from app.core.runtime_model import runtime_model
from app.entities.user import User
from app.services.deepseek_service import DeepSeekService

system_router = APIRouter()


@system_router.get("/api/admin/model", response_model=ModelSettingResponse)
async def get_model_setting(
    admin: Annotated[User, Depends(get_current_admin)],
):
    """管理员查看当前运行时模型与可切换列表"""
    return ModelSettingResponse(
        current=runtime_model.current(),
        available=runtime_model.available(),
    )


@system_router.put("/api/admin/model", response_model=ModelSettingResponse)
async def set_model_setting(
    request: ModelSettingRequest,
    admin: Annotated[User, Depends(get_current_admin)],
):
    """管理员切换运行时模型，持久化后对后续查询立即生效"""
    try:
        current = runtime_model.set_model(request.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ModelSettingResponse(
        current=current,
        available=runtime_model.available(),
    )


@system_router.get(
    "/api/admin/deepseek/balance", response_model=DeepSeekBalanceResponse
)
async def get_deepseek_balance(
    admin: Annotated[User, Depends(get_current_admin)],
    deepseek_service: Annotated[DeepSeekService, Depends(get_deepseek_service)],
):
    """管理员查询 DeepSeek 账户余额，通过后端代理避免前端持有 API Key"""
    try:
        data = await deepseek_service.fetch_balance()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        # 网络抖动或上游异常时降级为不可用状态，前端友好展示而非报 500
        return DeepSeekBalanceResponse(is_available=False, message=f"余额查询失败：{e}")
    return DeepSeekBalanceResponse(**data)
