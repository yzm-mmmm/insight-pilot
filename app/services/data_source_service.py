"""
数据源服务

承载数据源申请、审批、列表与删除的业务编排。审批通过后交给 SyncManager 在
后台执行全量同步；删除时停止增量线程并清理镜像表与元数据。密码在入库前用
Fernet 可逆加密，任何接口都不回传密码或密文。
"""

from datetime import datetime

from app.api.schemas.data_source_schema import (
    DataSourceCreateRequest,
    DataSourceOut,
    SyncResult,
)
from app.core.security import obfuscate_secret
from app.entities.data_source import DataSource
from app.entities.user import User
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.data_source_repository import DataSourceRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.services.sync_manager import SyncManager


class DataSourceService:
    """负责数据源申请、审批与同步触发的编排"""

    def __init__(
        self,
        data_source_repository: DataSourceRepository,
        dw_mysql_repository: DWMySQLRepository,
        meta_mysql_repository: MetaMySQLRepository,
        column_qdrant_repository: ColumnQdrantRepository,
        sync_manager: SyncManager,
    ):
        self.data_source_repository = data_source_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.sync_manager = sync_manager

    async def list(self, user: User) -> list[DataSourceOut]:
        """管理员看到全部数据源，普通用户只看自己提交的申请"""
        if user.role == "admin":
            sources = await self.data_source_repository.list()
        else:
            sources = await self.data_source_repository.list_by_user(user.id)
        return [self._to_out(source) for source in sources]

    async def apply(self, user: User, request: DataSourceCreateRequest) -> DataSourceOut:
        """提交接入申请，密码加密后落库，状态置为 pending"""
        created = await self.data_source_repository.create(
            name=request.name,
            description=request.description,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password_encrypted=obfuscate_secret(request.password),
            created_by=user.id,
        )
        await self.data_source_repository.session.commit()
        return self._to_out(created)

    async def review(self, reviewer: User, source_id: int, status: str) -> DataSourceOut:
        """审批申请，通过后立即触发后台全量同步"""
        if status not in ("approved", "rejected"):
            raise ValueError("status 必须是 approved 或 rejected")
        source = await self.data_source_repository.get_by_id(source_id)
        if source is None:
            raise ValueError("数据源不存在")
        updated = await self.data_source_repository.update(
            source_id,
            status=status,
            reviewed_by=reviewer.id,
            reviewed_at=datetime.utcnow(),
        )
        await self.data_source_repository.session.commit()
        if status == "approved":
            self.sync_manager.start_full_sync(updated)
        return self._to_out(updated)

    async def resync(self, source_id: int) -> SyncResult:
        """手动触发一次全量重同步，先停掉旧增量线程"""
        source = await self.data_source_repository.get_by_id(source_id)
        if source is None:
            raise ValueError("数据源不存在")
        self.sync_manager.stop(source_id)
        self.sync_manager.start_full_sync(source)
        return SyncResult(ok=True, status="syncing")

    async def delete(self, source_id: int) -> None:
        """删除数据源：停增量线程、删镜像表、清元数据与向量、删数据源行"""
        source = await self.data_source_repository.get_by_id(source_id)
        if source is None:
            raise ValueError("数据源不存在")

        self.sync_manager.stop(source_id)
        await self.dw_mysql_repository.drop_tables_by_prefix(source.table_prefix)

        mirror_ids = await self.meta_mysql_repository.list_table_ids_by_prefix(
            source.table_prefix
        )
        if mirror_ids:
            await self.meta_mysql_repository.delete_by_table_ids(mirror_ids)
            await self.column_qdrant_repository.delete_by_table_ids(mirror_ids)

        await self.data_source_repository.delete(source_id)
        await self.data_source_repository.session.commit()

    @staticmethod
    def _to_out(source: DataSource) -> DataSourceOut:
        """实体转出参，去掉密码密文字段"""
        return DataSourceOut(
            id=source.id,
            name=source.name,
            description=source.description,
            host=source.host,
            port=source.port,
            database=source.database,
            username=source.username,
            table_prefix=source.table_prefix,
            status=source.status,
            binlog_file=source.binlog_file,
            binlog_pos=source.binlog_pos,
            sync_error=source.sync_error,
            last_sync_at=source.last_sync_at,
            created_by=source.created_by,
            created_at=source.created_at,
            reviewed_by=source.reviewed_by,
            reviewed_at=source.reviewed_at,
        )
