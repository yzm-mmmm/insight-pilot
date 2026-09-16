"""
数据源业务实体

用于在数据源申请、审批与同步链路之间传递统一的语义信息。
一个数据源对应一个待接入的外部 MySQL 数据库；接入后其表会以
`table_prefix` 前缀镜像到我们自己的数仓，并通过 binlog 保持增量同步。
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DataSource:
    """系统内部统一使用的数据源表达"""

    id: int
    name: str
    host: str
    port: int
    database: str
    username: str
    password_encrypted: str
    table_prefix: str
    status: str
    description: str | None = None
    binlog_file: str | None = None
    binlog_pos: int | None = None
    sync_error: str | None = None
    last_sync_at: datetime | None = None
    created_by: int | None = None
    created_at: datetime | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
