"""
用户业务实体

用于在鉴权 Service 与仓储层之间传递统一的用户语义信息，
scope 字段预留给后续行级数据权限，本次登录鉴权阶段暂不启用。
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    """系统内部统一使用的用户表达"""

    id: int
    username: str
    password_hash: str
    nickname: str | None = None
    avatar: str | None = None
    role: str = "user"
    scope: dict | None = None
    disabled: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
