"""
表级权限业务实体

用于在权限 Service 与仓储层之间传递统一的表授权信息。
status 取值：pending（待审批）、approved（已授权）、rejected（已拒绝）。
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TablePermission:
    """用户对某张表的授权/申请记录"""

    id: int
    user_id: int
    table_name: str
    status: str = "pending"
    requested_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by: int | None = None
