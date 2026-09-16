"""
数据源仓储

负责 `data_source` 表的读写，是数据源申请、审批与同步链路访问该表的唯一入口。
实体与 ORM 模型的转换就地完成，写方法 flush 不 commit，提交由服务层事务控制。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.data_source import DataSource
from app.models.data_source import DataSourceMySQL


class DataSourceRepository:
    """负责数据源的增删改查"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password_encrypted: str,
        description: str | None = None,
        created_by: int | None = None,
    ) -> DataSource:
        """创建数据源（默认 pending），flush 后回填 table_prefix = s{id}"""
        model = DataSourceMySQL(
            name=name,
            description=description,
            host=host,
            port=port,
            database=database,
            username=username,
            password_encrypted=password_encrypted,
            table_prefix="",
            status="pending",
            created_by=created_by,
        )
        self.session.add(model)
        await self.session.flush()
        model.table_prefix = f"s{model.id}"
        await self.session.flush()
        return self._to_entity(model)

    async def get_by_id(self, source_id: int) -> DataSource | None:
        """按主键查询数据源"""
        model = await self.session.get(DataSourceMySQL, source_id)
        return self._to_entity(model) if model else None

    async def list(self, status: str | None = None) -> list[DataSource]:
        """查询全部数据源，可按状态过滤"""
        stmt = select(DataSourceMySQL).order_by(DataSourceMySQL.id.asc())
        if status:
            stmt = stmt.where(DataSourceMySQL.status == status)
        result = await self.session.execute(stmt)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def list_by_user(self, user_id: int) -> list[DataSource]:
        """查询某用户提交的数据源申请"""
        result = await self.session.execute(
            select(DataSourceMySQL)
            .where(DataSourceMySQL.created_by == user_id)
            .order_by(DataSourceMySQL.id.asc())
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def update(self, source_id: int, **fields) -> DataSource | None:
        """按字段更新数据源（状态、位点、错误等），flush 由调用方提交"""
        model = await self.session.get(DataSourceMySQL, source_id)
        if model is None:
            return None
        for key, value in fields.items():
            setattr(model, key, value)
        await self.session.flush()
        return self._to_entity(model)

    async def delete(self, source_id: int) -> None:
        """删除数据源（flush，提交由调用方事务控制）"""
        model = await self.session.get(DataSourceMySQL, source_id)
        if model:
            await self.session.delete(model)
            await self.session.flush()

    @staticmethod
    def _to_entity(model: DataSourceMySQL) -> DataSource:
        """把 ORM 模型还原成业务实体"""
        return DataSource(
            id=model.id,
            name=model.name,
            description=model.description,
            host=model.host,
            port=model.port,
            database=model.database,
            username=model.username,
            password_encrypted=model.password_encrypted,
            table_prefix=model.table_prefix,
            status=model.status,
            binlog_file=model.binlog_file,
            binlog_pos=model.binlog_pos,
            sync_error=model.sync_error,
            last_sync_at=model.last_sync_at,
            created_by=model.created_by,
            created_at=model.created_at,
            reviewed_by=model.reviewed_by,
            reviewed_at=model.reviewed_at,
        )
