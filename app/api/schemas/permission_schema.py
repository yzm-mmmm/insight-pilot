"""
权限接口请求/响应体定义

集中声明表权限申请、审批和查询相关接口的输入输出结构。
"""

from pydantic import BaseModel

from app.api.schemas.common import UTCOptionalDateTime


class TableOut(BaseModel):
    """可申请的数据表信息"""

    id: str
    name: str | None
    role: str | None
    description: str | None


class PermissionOut(BaseModel):
    """一条申请/授权记录"""

    id: int
    table_name: str
    status: str
    requested_at: UTCOptionalDateTime
    reviewed_at: UTCOptionalDateTime
    username: str | None = None


class MyPermissionsOut(BaseModel):
    """当前用户的权限概览：已授权表名 + 申请记录"""

    grants: list[str]
    requests: list[PermissionOut]


class UserGrantsOut(BaseModel):
    """单个用户的数据权限概览（管理员视图）"""

    user_id: int
    username: str
    role: str
    nickname: str | None = None
    grants: list[str]


class RevokeResult(BaseModel):
    """取消授权结果"""

    ok: bool


class ApplyRequest(BaseModel):
    """申请表权限请求体"""

    tables: list[str]


class ReviewRequest(BaseModel):
    """审批请求体"""

    status: str


class ApplyResult(BaseModel):
    """申请结果：本次实际发起申请的表名"""

    created: list[str]
