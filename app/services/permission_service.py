"""
表级权限服务

承载权限申请、审批与查询的业务编排：校验表名、组装响应、补全申请用户名。
审批相关操作由路由层的 get_current_admin 依赖保证仅管理员可调用。
"""

from app.api.schemas.permission_schema import (
    MyPermissionsOut,
    PermissionOut,
    TableOut,
    UserGrantsOut,
)
from app.entities.table_permission import TablePermission
from app.entities.user import User
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.mysql.meta.permission_repository import PermissionRepository
from app.repositories.mysql.meta.user_repository import UserRepository


class PermissionService:
    """负责表权限申请与审批的编排"""

    def __init__(
        self,
        permission_repository: PermissionRepository,
        meta_mysql_repository: MetaMySQLRepository,
        user_repository: UserRepository,
        dw_mysql_repository: DWMySQLRepository,
    ):
        self.permission_repository = permission_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.user_repository = user_repository
        self.dw_mysql_repository = dw_mysql_repository

    async def list_tables(self) -> list[TableOut]:
        """返回所有可申请的数据表

        以数仓库真实数据表为准，元数据表 table_info 只用于补充角色与描述，
        保证可授权清单始终对应能真正执行 SQL 的数据表。
        """
        table_names = await self.dw_mysql_repository.list_tables()
        metadata = {
            table.id: table for table in await self.meta_mysql_repository.list_table_infos()
        }
        result: list[TableOut] = []
        for name in table_names:
            info = metadata.get(name)
            result.append(
                TableOut(
                    id=name,
                    name=info.name if info else name,
                    role=info.role if info else None,
                    description=info.description if info else None,
                )
            )
        return result

    async def my_permissions(self, user: User) -> MyPermissionsOut:
        """返回当前用户的已授权表名与申请记录"""
        grants = sorted(await self.permission_repository.list_approved_tables(user.id))
        requests = await self.permission_repository.get_user_permissions(user.id)
        return MyPermissionsOut(
            grants=grants,
            requests=[self._to_out(permission) for permission in requests],
        )

    async def apply(self, user: User, tables: list[str]) -> list[str]:
        """提交表权限申请，校验表名是否为数仓库真实存在的数据表"""
        valid = set(await self.dw_mysql_repository.list_tables())
        unknown = [table for table in tables if table not in valid]
        if unknown:
            raise ValueError(f"不存在的表：{', '.join(unknown)}")
        return await self.permission_repository.apply(user.id, tables)

    async def list_requests(self) -> list[PermissionOut]:
        """返回全部申请记录（管理员视图），补全申请用户名"""
        requests = await self.permission_repository.list_requests()
        result: list[PermissionOut] = []
        for permission in requests:
            user = await self.user_repository.get_by_id(permission.user_id)
            result.append(self._to_out(permission, user.username if user else None))
        return result

    async def review(self, reviewer: User, permission_id: int, status: str) -> PermissionOut:
        """审批申请，status 只允许 approved 或 rejected"""
        if status not in ("approved", "rejected"):
            raise ValueError("status 必须是 approved 或 rejected")
        updated = await self.permission_repository.review(
            permission_id, status, reviewer.id
        )
        if updated is None:
            raise ValueError("申请记录不存在")
        return self._to_out(updated)

    async def list_user_grants(self, search: str | None = None) -> list[UserGrantsOut]:
        """返回所有用户及其已授权表（管理员视图），可按用户名/昵称搜索"""
        users = await self.user_repository.list_users(search)
        grants = await self.permission_repository.list_approved_by_user()
        return [
            UserGrantsOut(
                user_id=user.id,
                username=user.username,
                role=user.role,
                nickname=user.nickname,
                grants=sorted(grants.get(user.id, [])),
            )
            for user in users
        ]

    async def revoke(self, user_id: int, table_name: str) -> None:
        """取消某用户某张表的已授权记录"""
        ok = await self.permission_repository.revoke(user_id, table_name)
        if not ok:
            raise ValueError("该用户没有这张表的已授权记录")

    @staticmethod
    def _to_out(
        permission: TablePermission, username: str | None = None
    ) -> PermissionOut:
        return PermissionOut(
            id=permission.id,
            table_name=permission.table_name,
            status=permission.status,
            requested_at=permission.requested_at,
            reviewed_at=permission.reviewed_at,
            username=username,
        )
