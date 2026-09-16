"""
管理员接口请求/响应体定义

集中声明用户管理相关接口的输入输出结构，字段校验与 OpenAPI
文档生成交给 Pydantic 完成。
"""

from datetime import datetime

from pydantic import BaseModel

from app.api.schemas.auth_schema import UserOut


class AdminUserOut(UserOut):
    """管理员视图下的用户信息，在 UserOut 基础上补充注册时间"""

    created_at: datetime | None = None


class AdminResetPasswordRequest(BaseModel):
    """管理员重置用户密码请求体"""

    new_password: str


class AdminOkOut(BaseModel):
    """通用成功响应"""

    ok: bool = True
