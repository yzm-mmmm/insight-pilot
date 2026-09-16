"""
数据源全量同步服务

审批通过后，把源库的数据一次性镜像进自有数仓 dw：对每张源表生成 `s{id}_` 前缀的
镜像表，在一致性快照内把数据批量拷贝过来，并记录快照时点的 binlog 位点，供后续
增量同步无缝衔接。本服务整体是阻塞式同步实现，由 SyncManager 放到后台线程执行，
不占用 FastAPI 事件循环。

本模块同时提供 dw/meta 同步连接与状态回写等共享工具，供增量同步 worker 复用。
"""

import re
from datetime import datetime

import pymysql

from app.clients.source_connection import SourceConnection
from app.conf.app_config import app_config
from app.core.log import logger
from app.core.security import deobfuscate_secret
from app.entities.data_source import DataSource


def quote_ident(ident: str) -> str:
    """用反引号包裹 MySQL 标识符"""
    return f"`{ident}`"


def dw_connection() -> pymysql.connections.Connection:
    """打开一条到自有数仓 dw 的同步连接，用于建镜像表与写数据"""
    cfg = app_config.db_dw
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset="utf8mb4",
        autocommit=False,
    )


def meta_connection() -> pymysql.connections.Connection:
    """打开一条到元数据库 meta 的同步连接，用于回写同步状态与位点"""
    cfg = app_config.db_meta
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset="utf8mb4",
        autocommit=True,
    )


def update_source_status(source_id: int, **fields) -> None:
    """把同步状态字段回写到 data_source 表，提交即生效"""
    assignments = ", ".join(f"{key} = %s" for key in fields)
    values = list(fields.values())
    conn = meta_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"UPDATE data_source SET {assignments} WHERE id = %s",
                values + [source_id],
            )
        conn.commit()
    finally:
        conn.close()


def rewrite_mirror_ddl(ddl: str, mirror_name: str) -> str:
    """把源表建表 DDL 改造成镜像表 DDL：改名并去除跨表外键约束"""
    ddl = re.sub(
        r"CREATE\s+TABLE\s+`[^`]+`",
        f"CREATE TABLE `{mirror_name}`",
        ddl,
        count=1,
    )
    # 外键引用的是源库里的原表名，镜像后名字已经变化，直接剔除约束最稳妥
    lines = []
    for line in ddl.splitlines():
        upper = line.strip().upper()
        if "FOREIGN KEY" in upper or upper.startswith("CONSTRAINT"):
            continue
        lines.append(line)
    ddl = "\n".join(lines)
    # 剔除约束后可能留下悬空逗号
    ddl = re.sub(r",(\s*\))", r"\1", ddl)
    return ddl


def upsert_sql(mirror_name: str, columns: list[str], unique: bool) -> str:
    """生成幂等插入 SQL：有唯一键时用 ON DUPLICATE KEY UPDATE，否则 INSERT IGNORE"""
    cols = ", ".join(quote_ident(c) for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    if unique:
        updates = ", ".join(f"{quote_ident(c)} = VALUES({quote_ident(c)})" for c in columns)
        return (
            f"INSERT INTO {quote_ident(mirror_name)} ({cols}) "
            f"VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}"
        )
    return f"INSERT IGNORE INTO {quote_ident(mirror_name)} ({cols}) VALUES ({placeholders})"


class SyncService:
    """负责把单个数据源全量镜像进 dw，并记录增量同步起点"""

    def full_sync(self, source: DataSource) -> list[str] | None:
        """执行一次完整全量同步，成功返回源表名列表，失败返回 None

        步骤：置 syncing → 连源库开一致性快照 → 记 binlog 位点 → 逐表建镜像并
        拷贝数据 → 成功后置 active 并写位点；任何异常置 error 并记录错误。
        """
        source_conn = None
        dw_conn = None
        try:
            update_source_status(source.id, status="syncing", sync_error=None)
            password = deobfuscate_secret(source.password_encrypted)

            source_conn = SourceConnection(
                host=source.host,
                port=source.port,
                user=source.username,
                password=password,
                database=source.database,
            ).connect()

            tables = source_conn.list_tables()
            if not tables:
                raise RuntimeError("源库没有可同步的数据表")

            dw_conn = dw_connection()
            source_conn.start_consistent_snapshot()
            binlog_file, binlog_pos = source_conn.show_master_status()
            if binlog_file is None:
                raise RuntimeError(
                    "源库未开启 binlog（SHOW MASTER STATUS 为空），"
                    "请确认 log_bin=ON 且账号具备 REPLICATION CLIENT 权限"
                )

            mirrored: list[str] = []
            for table in tables:
                mirror_name = f"{source.table_prefix}_{table}"
                ddl = rewrite_mirror_ddl(
                    source_conn.get_create_table(table), mirror_name
                )
                self._create_mirror_table(dw_conn, mirror_name, ddl)
                unique = source_conn.has_unique_key(table)
                self._copy_rows(dw_conn, source_conn, table, mirror_name, unique)
                mirrored.append(mirror_name)

            source_conn.commit()
            dw_conn.commit()

            update_source_status(
                source.id,
                status="active",
                binlog_file=binlog_file,
                binlog_pos=binlog_pos,
                sync_error=None,
                last_sync_at=datetime.utcnow(),
            )
            logger.info(
                "数据源 {} 全量同步完成，共镜像 {} 张表，binlog 位点 {}:{}",
                source.id,
                len(mirrored),
                binlog_file,
                binlog_pos,
            )
            return tables
        except Exception as e:  # noqa: BLE001 —— 同步失败统一落库，供前端展示
            logger.exception("数据源 {} 全量同步失败", source.id)
            update_source_status(source.id, status="error", sync_error=str(e))
            return None
        finally:
            if source_conn is not None:
                source_conn.close()
            if dw_conn is not None:
                dw_conn.close()

    @staticmethod
    def _create_mirror_table(dw_conn, mirror_name: str, ddl: str):
        """在 dw 中先删后建镜像表，保证重复同步时结构以源表为准"""
        with dw_conn.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {quote_ident(mirror_name)}")
            cursor.execute(ddl)

    @staticmethod
    def _copy_rows(dw_conn, source_conn, table: str, mirror_name: str, unique: bool):
        """按批把源表数据写入镜像表，整批一次 commit 保证原子性"""
        with dw_conn.cursor() as cursor:
            for columns, rows in source_conn.stream_rows(table):
                sql = upsert_sql(mirror_name, columns, unique)
                cursor.executemany(sql, rows)
            dw_conn.commit()
