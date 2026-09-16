"""
binlog 增量同步 worker

从全量同步记录的位点起订阅源库 binlog，把写入/更新/删除与建表/改表/删表等事件
实时应用到 dw 里的镜像表。每个数据源一个 worker，跑在独立后台线程中；阻塞式
BinLogStreamReader 不会触碰事件循环。断线后按最后落库位点自动重连续传。
"""

import re
import socket
import threading
from datetime import datetime
from typing import Callable

import pymysql
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.event import QueryEvent
from pymysqlreplication.row_event import (
    DeleteRowsEvent,
    UpdateRowsEvent,
    WriteRowsEvent,
)

from app.clients.source_connection import SourceConnection
from app.core.log import logger
from app.core.security import deobfuscate_secret
from app.entities.data_source import DataSource
from app.services.sync_service import (
    dw_connection,
    meta_connection,
    quote_ident,
    rewrite_mirror_ddl,
    update_source_status,
    upsert_sql,
)

# 事件顺序里只关心行变更与 DDL，其余事件（如事务边界、GTID）交给库处理
TRACKED_EVENTS = [WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent, QueryEvent]


def _normalize(value):
    """把 binlog 里的字节串还原成文本，其余类型原样交给 pymysql 处理"""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


class BinlogWorker(threading.Thread):
    """消费单个数据源 binlog 的后台线程"""

    def __init__(
        self,
        source: DataSource,
        stop_event: threading.Event,
        on_new_tables: Callable[[DataSource, list[str]], None] | None = None,
        on_drop_tables: Callable[[DataSource, list[str]], None] | None = None,
    ):
        super().__init__(name=f"binlog-{source.id}", daemon=True)
        self.source = source
        self.stop_event = stop_event
        self.on_new_tables = on_new_tables
        self.on_drop_tables = on_drop_tables
        self._stream: BinLogStreamReader | None = None

    def stop(self):
        """通知停止并打断阻塞中的流读取

        不能直接调 ``stream.close()``：pymysql 的 close 会先 close 缓冲读器
        ``_rfile``，而 worker 线程此刻正持有 ``_rfile`` 的锁阻塞在 socket read
        上，close 会在等锁时死锁（曾导致重同步/删除接口卡死整个事件循环）。
        这里越过缓冲层，直接对底层 socket 做 shutdown 打断阻塞读，让 worker
        线程的 read 立即返回，随后由它自己的 finally 干净地 close 整个 stream。
        """
        self.stop_event.set()
        stream = self._stream
        if stream is not None:
            try:
                self._interrupt_stream(stream)
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _interrupt_stream(stream) -> None:
        """关闭 stream 底层 socket，打断阻塞中的 binlog 读取"""
        for name in ("_stream_connection", "_ctl_connection"):
            conn = getattr(stream, name, None)
            sock = getattr(conn, "_sock", None)
            if sock is None:
                continue
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                # shutdown 失败（如连接已断）时退化为直接 close
                try:
                    sock.close()
                except OSError:
                    pass

    def run(self):
        while not self.stop_event.is_set():
            try:
                self._stream_loop()
            except pymysql.OperationalError as e:
                if self.stop_event.is_set():
                    break
                logger.warning("数据源 {} binlog 连接异常，5 秒后重连：{}", self.source.id, e)
                self.stop_event.wait(5)
            except Exception as e:  # noqa: BLE001
                if self.stop_event.is_set():
                    break
                logger.exception("数据源 {} binlog 消费异常", self.source.id)
                update_source_status(self.source.id, status="error", sync_error=str(e))
                self.stop_event.wait(5)

    def _stream_loop(self):
        log_file, log_pos = self._resolve_start_position()
        if not log_file:
            raise RuntimeError("源库未开启 binlog，无法启动增量同步")

        stream = BinLogStreamReader(
            connection_settings={
                "host": self.source.host,
                "port": self.source.port,
                "user": self.source.username,
                "passwd": deobfuscate_secret(self.source.password_encrypted),
                "charset": "utf8mb4",
            },
            server_id=self._server_id(),
            blocking=True,
            resume_stream=True,
            auto_position=False,
            log_file=log_file,
            log_pos=log_pos,
            only_schemas=[self.source.database],
            only_events=TRACKED_EVENTS,
            # MySQL 8.0.13+ / 9.x 默认 binlog_row_metadata=MINIMAL，行事件里不带
            # 列名，需要从 INFORMATION_SCHEMA 兜底拉取列名；该兜底默认关闭
            # （use_column_name_cache=False 会直接返回空），必须显式开启，否则
            # 列名变 None/UNKNOWN_COL0，写镜像表时 KeyError。
            use_column_name_cache=True,
        )
        self._stream = stream
        dw_conn = dw_connection()
        meta_conn = meta_connection()
        try:
            # 连接正常进入消费，状态从 error 恢复为 active
            update_source_status(self.source.id, status="active", sync_error=None)
            for event in stream:
                if self.stop_event.is_set():
                    break
                self._handle_event(dw_conn, event)
                self._persist_position(meta_conn, stream.log_file, stream.log_pos)
        finally:
            dw_conn.close()
            meta_conn.close()
            stream.close()
            self._stream = None

    def _resolve_start_position(self) -> tuple[str | None, int | None]:
        """从元数据库读最新落库位点续传，缺失时退回源库当前位点

        位点由全量同步或上一次增量消费写回，worker 始终以库里的最新值为准，
        避免拿到过期的内存实体而漏掉快照之后的变化。
        """
        conn = meta_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT binlog_file, binlog_pos FROM data_source WHERE id = %s",
                    (self.source.id,),
                )
                row = cursor.fetchone()
                if row and row[0] is not None and row[1] is not None:
                    return row[0], row[1]
        finally:
            conn.close()

        source_conn = SourceConnection(
            host=self.source.host,
            port=self.source.port,
            user=self.source.username,
            password=deobfuscate_secret(self.source.password_encrypted),
            database=self.source.database,
        ).connect()
        try:
            return source_conn.show_master_status()
        finally:
            source_conn.close()

    def _server_id(self) -> int:
        """生成一个进程内唯一、且不会与真实 server_id 冲突的复制端标识"""
        return 100000 + self.source.id

    def _handle_event(self, dw_conn, event):
        if isinstance(event, WriteRowsEvent):
            self._apply_write(dw_conn, event)
        elif isinstance(event, UpdateRowsEvent):
            self._apply_update(dw_conn, event)
        elif isinstance(event, DeleteRowsEvent):
            self._apply_delete(dw_conn, event)
        elif isinstance(event, QueryEvent):
            self._apply_ddl(dw_conn, event.query)

    def _apply_write(self, dw_conn, event: WriteRowsEvent):
        columns = [col.name for col in event.columns]
        mirror = self._mirror(event.table)
        sql = upsert_sql(mirror, columns, unique=True)
        # mysql-replication 1.0.17 的行结构：rows 里每个元素是
        # {"values": {列名: 值}, "none_sources": {...}}，列值在 values 下
        rows = [
            tuple(_normalize(row["values"][c]) for c in columns) for row in event.rows
        ]
        with dw_conn.cursor() as cursor:
            cursor.executemany(sql, rows)
        dw_conn.commit()

    def _apply_update(self, dw_conn, event: UpdateRowsEvent):
        columns = [col.name for col in event.columns]
        mirror = self._mirror(event.table)
        set_clause = ", ".join(f"{quote_ident(c)} = %s" for c in columns)
        where = " AND ".join(f"{quote_ident(c)} <=> %s" for c in columns)
        sql = f"UPDATE {quote_ident(mirror)} SET {set_clause} WHERE {where}"
        with dw_conn.cursor() as cursor:
            for row in event.rows:
                after = row["after_values"]
                before = row["before_values"]
                params = [_normalize(after[c]) for c in columns] + [
                    _normalize(before[c]) for c in columns
                ]
                cursor.execute(sql, params)
        dw_conn.commit()

    def _apply_delete(self, dw_conn, event: DeleteRowsEvent):
        columns = [col.name for col in event.columns]
        mirror = self._mirror(event.table)
        where = " AND ".join(f"{quote_ident(c)} <=> %s" for c in columns)
        sql = f"DELETE FROM {quote_ident(mirror)} WHERE {where}"
        with dw_conn.cursor() as cursor:
            for row in event.rows:
                # 同 WriteRowsEvent：列值在 row["values"] 下
                params = [_normalize(row["values"][c]) for c in columns]
                cursor.execute(sql, params)
        dw_conn.commit()

    def _apply_ddl(self, dw_conn, query: str):
        q = query.strip()
        upper = q.upper()
        if upper.startswith("CREATE TABLE"):
            table = self._extract_table(q, r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([^`\s(]+)`?")
            if table:
                self._create_mirror_from_source(dw_conn, table)
                self._notify_new_tables([table])
        elif upper.startswith("ALTER TABLE"):
            table = self._extract_table(q, r"ALTER\s+TABLE\s+`?([^`\s]+)`?")
            if table:
                self._execute_rewritten(dw_conn, table, q)
        elif upper.startswith("DROP TABLE"):
            tables = re.findall(r"`([^`]+)`", q)
            for table in tables:
                self._drop_mirror(dw_conn, table)
            self._notify_drop_tables(tables)
        elif upper.startswith("RENAME TABLE"):
            logger.warning("数据源 {} 的表重命名暂不支持自动同步，请手动重同步：{}", self.source.id, q)
        else:
            # 库级/会话级/权限/事务语句（CREATE DATABASE、DROP DATABASE、USE、SET、
            # GRANT、BEGIN 等）以及 /*!40000 ALTER ... DISABLE KEYS */ 这类导入辅助
            # 语句都与镜像表无关，直接忽略。不能盲目改写执行，否则会把库名误当表名
            # （曾把 CREATE DATABASE `dw` 改写成 `s1_dw`，触发 1044 权限错误）
            logger.info("数据源 {} 忽略与镜像表无关的 DDL：{}", self.source.id, q[:120])

    def _create_mirror_from_source(self, dw_conn, table: str):
        mirror = self._mirror(table)
        source_conn = SourceConnection(
            host=self.source.host,
            port=self.source.port,
            user=self.source.username,
            password=deobfuscate_secret(self.source.password_encrypted),
            database=self.source.database,
        ).connect()
        try:
            ddl = rewrite_mirror_ddl(source_conn.get_create_table(table), mirror)
            with dw_conn.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {quote_ident(mirror)}")
                cursor.execute(ddl)
            dw_conn.commit()
            logger.info("数据源 {} 捕获新建表 {}，已创建镜像表 {}", self.source.id, table, mirror)
        finally:
            source_conn.close()

    def _execute_rewritten(self, dw_conn, table: str, query: str):
        mirror = self._mirror(table)
        rewritten = query.replace(f"`{table}`", f"`{mirror}`", 1)
        with dw_conn.cursor() as cursor:
            cursor.execute(rewritten)
        dw_conn.commit()

    def _drop_mirror(self, dw_conn, table: str):
        mirror = self._mirror(table)
        with dw_conn.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {quote_ident(mirror)}")
        dw_conn.commit()
        logger.info("数据源 {} 捕获删表 {}，已删除镜像表 {}", self.source.id, table, mirror)

    def _mirror(self, table: str) -> str:
        return f"{self.source.table_prefix}_{table}"

    @staticmethod
    def _extract_table(query: str, pattern: str) -> str | None:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        return match.group(1).strip("`") if match else None

    def _notify_new_tables(self, tables: list[str]):
        if self.on_new_tables and tables:
            try:
                self.on_new_tables(self.source, tables)
            except Exception:  # noqa: BLE001
                logger.exception("通知新表元数据同步失败")

    def _notify_drop_tables(self, tables: list[str]):
        if self.on_drop_tables and tables:
            try:
                self.on_drop_tables(self.source, tables)
            except Exception:  # noqa: BLE001
                logger.exception("通知删表元数据清理失败")

    def _persist_position(self, meta_conn, log_file: str, log_pos: int):
        with meta_conn.cursor() as cursor:
            cursor.execute(
                "UPDATE data_source SET binlog_file = %s, binlog_pos = %s, "
                "last_sync_at = %s WHERE id = %s",
                (log_file, log_pos, datetime.utcnow(), self.source.id),
            )
