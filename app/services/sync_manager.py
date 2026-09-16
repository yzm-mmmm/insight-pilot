"""
同步管理器

统一调度每个数据源的全量同步线程与 binlog 增量同步线程：审批通过后触发全量同步，
成功后接上增量同步；应用启动时恢复 active 源；停用/删除时停止对应线程；关闭时
全部停止。全量与增量都跑在独立后台线程，管理器只负责生命周期编排。
"""

import asyncio
import threading
from contextlib import asynccontextmanager

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.core.log import logger
from app.entities.data_source import DataSource
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.data_source_repository import DataSourceRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.services.binlog_worker import BinlogWorker
from app.services.meta_knowledge_service import MetaKnowledgeService
from app.services.sync_service import SyncService


class SyncManager:
    """管理各数据源同步线程的生命周期"""

    def __init__(self):
        self._workers: dict[int, BinlogWorker] = {}
        self._full_sync_threads: set[threading.Thread] = set()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop):
        """绑定事件循环，供后台线程把元数据爬取调度回事件循环"""
        self._loop = loop

    async def resume_active(self):
        """应用启动时恢复所有 active 数据源的增量同步"""
        try:
            async with meta_mysql_client_manager.session_factory() as session:
                sources = await DataSourceRepository(session).list(status="active")
        except Exception as e:  # noqa: BLE001
            # data_source 表尚未初始化时不影响主流程，仅记录提示
            logger.warning("恢复数据源增量同步失败（可能 data_source 表未初始化）：{}", e)
            return
        for source in sources:
            self.start_binlog(source)
        logger.info("已恢复 {} 个 active 数据源的增量同步", len(sources))

    def start_full_sync(self, source: DataSource):
        """在后台线程执行一次全量同步，成功后自动接上增量同步与元数据爬取"""
        thread = threading.Thread(
            target=self._run_full_sync,
            args=(source,),
            name=f"fullsync-{source.id}",
            daemon=True,
        )
        self._full_sync_threads.add(thread)
        thread.start()

    def _run_full_sync(self, source: DataSource):
        try:
            tables = SyncService().full_sync(source)
            if tables:
                self.start_binlog(source)
                self._schedule_crawl(source, tables)
        except Exception:  # noqa: BLE001
            logger.exception("数据源 {} 全量同步线程异常", source.id)
        finally:
            self._full_sync_threads.discard(threading.current_thread())

    def start_binlog(self, source: DataSource):
        """为数据源启动（或复用）一个增量同步线程"""
        with self._lock:
            existing = self._workers.get(source.id)
            if existing is not None and existing.is_alive():
                return
            worker = BinlogWorker(
                source,
                threading.Event(),
                on_new_tables=self._on_new_tables,
                on_drop_tables=self._on_drop_tables,
            )
            self._workers[source.id] = worker
        worker.start()

    def stop(self, source_id: int):
        """停止指定数据源的增量同步线程"""
        with self._lock:
            worker = self._workers.pop(source_id, None)
        if worker is not None:
            worker.stop()

    def shutdown(self):
        """停止全部增量同步线程（应用关闭时调用）"""
        with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()
        for worker in workers:
            worker.stop()

    def _schedule_crawl(self, source: DataSource, tables: list[str]):
        if self._loop is None:
            logger.error("数据源 {} 元数据爬取未调度：事件循环未绑定", source.id)
            return
        future = asyncio.run_coroutine_threadsafe(
            self._crawl_tables(source.table_prefix, tables), self._loop
        )

        def _log_crawl_result(fut):
            # run_coroutine_threadsafe 的异常若无人消费会在 GC 时才报，且不进业务日志；
            # 这里主动消费，把爬取失败明确记录出来，避免镜像表已建好但元数据缺失的静默故障
            try:
                fut.result()
            except Exception:  # noqa: BLE001
                logger.exception("数据源 {} 镜像表元数据爬取失败", source.id)

        future.add_done_callback(_log_crawl_result)

    def _on_new_tables(self, source: DataSource, tables: list[str]):
        self._schedule_crawl(source, tables)

    def _on_drop_tables(self, source: DataSource, tables: list[str]):
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._delete_tables(source.table_prefix, tables), self._loop
            )

    async def _crawl_tables(self, prefix: str, tables: list[str]):
        """对镜像表自动爬取元数据并写入 Meta MySQL 与 Qdrant"""
        async with self._meta_service() as service:
            await service.sync_mirror_tables(prefix, tables)

    async def _delete_tables(self, prefix: str, tables: list[str]):
        """删除镜像表的元数据（表被 drop 时清理）"""
        async with self._meta_service() as service:
            await service.delete_mirror_tables(prefix, tables)

    @asynccontextmanager
    async def _meta_service(self):
        """在全新 session 上下文里组装元数据知识服务，供后台爬取复用"""
        async with (
            meta_mysql_client_manager.session_factory() as meta_session,
            dw_mysql_client_manager.session_factory() as dw_session,
        ):
            yield MetaKnowledgeService(
                meta_mysql_repository=MetaMySQLRepository(meta_session),
                dw_mysql_repository=DWMySQLRepository(dw_session),
                column_qdrant_repository=ColumnQdrantRepository(
                    qdrant_client_manager.client
                ),
                embedding_client=embedding_client_manager.client,
                value_es_repository=ValueESRepository(es_client_manager.client),
                metric_qdrant_repository=MetricQdrantRepository(
                    qdrant_client_manager.client
                ),
            )


# 模块级单例：lifespan 中 bind_loop + resume_active，依赖注入处直接取用
sync_manager = SyncManager()
