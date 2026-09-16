"""
鉴权接口请求/响应体定义

集中声明登录、注册和当前用户相关接口的输入输出结构，
字段校验和 OpenAPI 文档生成交给 Pydantic 完成。
"""

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    """注册请求体"""

    username: str
    password: str


class LoginRequest(BaseModel):
    """登录请求体"""

    username: str
    password: str


class UserOut(BaseModel):
    """返回给前端的用户信息，不暴露密码哈希"""

    id: int
    username: str
    role: str
    disabled: bool = False
    nickname: str | None = None
    avatar: str | None = None


class ProfileUpdateRequest(BaseModel):
    """更新个人资料请求体：昵称与头像（空值表示清空）"""

    nickname: str | None = None
    avatar: str | None = None


class PasswordChangeRequest(BaseModel):
    """修改密码请求体"""

    old_password: str
    new_password: str


class TokenResponse(BaseModel):
    """登录/注册成功后的令牌响应"""

    access_token: str
    token_type: str = "bearer"
    user: UserOut
