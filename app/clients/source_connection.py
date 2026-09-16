"""
源库连接助手

基于 pymysql 的同步连接封装，用于全量同步与 binlog 增量同步阶段读取源库。
项目其余部分走 asyncmy 异步引擎，但全量同步与 binlog 消费都跑在独立后台线程里，
这里统一用同步 pymysql，避免把阻塞式 I/O 放到事件循环上。
"""

from collections.abc import Iterator

import pymysql
from pymysql.cursors import DictCursor, SSCursor
from pymysql.err import ProgrammingError


class SourceConnection:
    """管理一条到外部源库的同步 MySQL 连接"""

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.conn: pymysql.connections.Connection | None = None

    def connect(self) -> "SourceConnection":
        """建立连接，使用 DictCursor 便于按列名取字段"""
        self.conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=10,
            read_timeout=30,
        )
        return self

    def close(self):
        """释放连接"""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "SourceConnection":
        return self.connect()

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def list_tables(self) -> list[str]:
        """列出源库全部表名"""
        with self.conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            key = f"Tables_in_{self.database}"
            return [row[key] for row in cursor.fetchall()]

    def get_create_table(self, table: str) -> str:
        """读取源表建表 DDL"""
        with self.conn.cursor() as cursor:
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            return cursor.fetchone()["Create Table"]

    def has_unique_key(self, table: str) -> bool:
        """判断源表是否存在主键或唯一索引，决定镜像数据是否可幂等写入"""
        with self.conn.cursor() as cursor:
            cursor.execute(f"SHOW INDEX FROM `{table}`")
            return any(row["Non_unique"] == 0 for row in cursor.fetchall())

    def show_master_status(self) -> tuple[str | None, int | None]:
        """读取当前 binlog 位点（file, position），源库未开 binlog 时返回空

        MySQL 8.4 移除了 ``SHOW MASTER STATUS``，改用 ``SHOW BINARY LOG STATUS``
        （8.0.22 起两者等价）。这里优先新语法，对更老的源库退回旧语法。
        """
        with self.conn.cursor() as cursor:
            try:
                cursor.execute("SHOW BINARY LOG STATUS")
            except ProgrammingError:
                cursor.execute("SHOW MASTER STATUS")
            row = cursor.fetchone()
            if row is None:
                return None, None
            return row.get("File"), row.get("Position")

    def start_consistent_snapshot(self):
        """开启 REPEATABLE READ 一致性快照，保证整次全量读到的数据一致"""
        with self.conn.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT")

    def commit(self):
        """提交当前事务（结束一致性快照）"""
        self.conn.commit()

    def stream_rows(
        self, table: str, batch_size: int = 1000
    ) -> Iterator[tuple[list[str], list[tuple]]]:
        """流式读取整张表，按批返回 (列名, 行元组列表)，避免整表一次读进内存"""
        with self.conn.cursor(SSCursor) as cursor:
            cursor.execute(f"SELECT * FROM `{table}`")
            columns = [desc[0] for desc in cursor.description]
            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                yield columns, rows
