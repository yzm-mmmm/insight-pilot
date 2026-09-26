"""
FastAPI 应用入口

负责创建后端应用实例，注册应用生命周期函数，并把各业务模块中的 router
挂载到同一个 app 上。HTTP 请求会先进入这里创建的 app，再按路由分发到
具体的接口处理函数。
"""

import uuid

from fastapi import FastAPI, Request

from app.api.lifespan import lifespan
from app.api.routers.admin_router import admin_router
from app.api.routers.auth_router import auth_router
from app.api.routers.data_source_router import data_source_router
from app.api.routers.feedback_router import feedback_router
from app.api.routers.permission_router import permission_router
from app.api.routers.query_router import query_router
from app.api.routers.session_router import session_router
from app.api.routers.system_router import system_router
from app.api.routers.upload_router import upload_router
from app.core.context import request_id_ctx_var

# lifespan 交给 FastAPI 管理，用于在服务启动和关闭时统一初始化与释放外部客户端
app = FastAPI(lifespan=lifespan)

# 把查询路由注册进应用；没有挂载时，/docs 和真实 HTTP 请求都访问不到该接口
app.include_router(query_router)

# 注册鉴权路由：提供注册、登录与查询当前用户三个接口
app.include_router(auth_router)

# 注册多轮会话路由：提供会话列表、详情、重命名与删除
app.include_router(session_router)

# 注册表级权限路由：提供可申请表清单、申请与审批
app.include_router(permission_router)

# 注册反馈路由：提供对单条消息的赞/踩/纠错
app.include_router(feedback_router)

# 注册用户管理路由：提供管理员视角的用户列表、重置密码与删除
app.include_router(admin_router)

# 注册数据源路由：提供数据源接入申请、审批与同步管理
app.include_router(data_source_router)

# 注册上传路由：提供头像上传（写入阿里云 OSS，数据库只存 URL）
app.include_router(upload_router)

# 注册系统设置路由：提供管理员专用的模型切换与 DeepSeek 余额查询
app.include_router(system_router)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # 请求被处理之前
    request_id = uuid.uuid4()
    request_id_ctx_var.set(request_id)
    response = await call_next(request)
    # 请求被处理之后
    return response
