"""
表级权限仓储

负责 `table_permission` 表的读写，是权限申请与审批链路的唯一入口。
执行期白名单读取（list_approved_tables）也集中在这里，供查询链路校验。
写方法各自提交事务，避免与元数据检索链路共享的隐式事务相互嵌套。
"""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.table_permission import TablePermission
from app.models.table_permission import TablePermissionMySQL


class PermissionRepository:
    """负责表级权限的申请、审批与查询"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_approved_tables(self, user_id: int) -> set[str]:
        """查询某用户已授权（approved）的表名集合，供执行期白名单校验"""
        result = await self.session.execute(
            select(TablePermissionMySQL.table_name).where(
                TablePermissionMySQL.user_id == user_id,
                TablePermissionMySQL.status == "approved",
            )
        )
        return set(result.scalars().all())

    async def get_user_permissions(self, user_id: int) -> list[TablePermission]:
        """查询某用户的全部申请/授权记录，按申请时间倒序"""
        result = await self.session.execute(
            select(TablePermissionMySQL)
            .where(TablePermissionMySQL.user_id == user_id)
            .order_by(TablePermissionMySQL.requested_at.desc())
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def apply(self, user_id: int, tables: list[str]) -> list[str]:
        """批量提交申请

        已授权/待审批的记录保持不变；被拒绝的记录重置为待审批以支持重新申请；
        全新表新建 pending 记录。返回本次实际发起申请的表名。
        """
        created: list[str] = []
        for table in tables:
            model = await self._get_row(user_id, table)
            if model is None:
                self.session.add(
                    TablePermissionMySQL(
                        user_id=user_id, table_name=table, status="pending"
                    )
                )
                created.append(table)
            elif model.status == "rejected":
                model.status = "pending"
                model.reviewed_at = None
                model.reviewed_by = None
                created.append(table)
            # pending / approved 保持不变
        if created:
            await self.session.commit()
        return created

    async def list_requests(self) -> list[TablePermission]:
        """查询全部申请记录（管理员视图），按申请时间倒序"""
        result = await self.session.execute(
            select(TablePermissionMySQL).order_by(
                TablePermissionMySQL.requested_at.desc()
            )
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def list_approved_by_user(self) -> dict[int, list[str]]:
        """查询全部已授权（approved）记录，按用户分组返回表名列表"""
        result = await self.session.execute(
            select(TablePermissionMySQL).where(
                TablePermissionMySQL.status == "approved"
            )
        )
        grants: dict[int, list[str]] = {}
        for model in result.scalars().all():
            grants.setdefault(model.user_id, []).append(model.table_name)
        return grants

    async def revoke(self, user_id: int, table_name: str) -> bool:
        """取消某用户对某表的授权，删除该 approved 记录，返回是否真的删除"""
        model = await self._get_row(user_id, table_name)
        if model is None or model.status != "approved":
            return False
        await self.session.delete(model)
        await self.session.commit()
        return True

    async def review(
        self, permission_id: int, status: str, reviewer_id: int
    ) -> TablePermission | None:
        """审批申请：写入状态与审批人信息"""
        model = await self.session.get(TablePermissionMySQL, permission_id)
        if model is None:
            return None
        model.status = status
        model.reviewed_at = datetime.utcnow()
        model.reviewed_by = reviewer_id
        await self.session.commit()
        return self._to_entity(model)

    async def delete_by_user(self, user_id: int) -> None:
        """删除某用户的全部权限申请/授权记录（flush，提交由调用方事务控制）"""
        await self.session.execute(
            delete(TablePermissionMySQL).where(TablePermissionMySQL.user_id == user_id)
        )
        await self.session.flush()

    async def _get_row(
        self, user_id: int, table_name: str
    ) -> TablePermissionMySQL | None:
        result = await self.session.execute(
            select(TablePermissionMySQL).where(
                TablePermissionMySQL.user_id == user_id,
                TablePermissionMySQL.table_name == table_name,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_entity(model: TablePermissionMySQL) -> TablePermission:
        return TablePermission(
            id=model.id,
            user_id=model.user_id,
            table_name=model.table_name,
            status=model.status,
            requested_at=model.requested_at,
            reviewed_at=model.reviewed_at,
            reviewed_by=model.reviewed_by,
        )
