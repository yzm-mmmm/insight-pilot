"""
数据源种子脚本

负责幂等地初始化数据源管理所需的 `data_source` 表，对已初始化（非全新
volume）的元数据库做兜底建表。可安全重复运行。

用法：
    uv run python -m app.scripts.seed_data_sources
"""

import asyncio

from sqlalchemy import text

from app.clients.mysql_client_manager import meta_mysql_client_manager

# 与 docker/mysql/meta.sql 保持一致
DATA_SOURCE_DDL = """
CREATE TABLE IF NOT EXISTS data_source (
    id                 BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '数据源编号',
    name               VARCHAR(128) NOT NULL COMMENT '数据源名称',
    description        TEXT NULL COMMENT '说明',
    host               VARCHAR(128) NOT NULL COMMENT '源库主机',
    port               INT NOT NULL COMMENT '源库端口',
    `database`        VARCHAR(128) NOT NULL COMMENT '源库名',
    username           VARCHAR(128) NOT NULL COMMENT '源库账号',
    password_encrypted VARCHAR(512) NOT NULL COMMENT '源库密码(可逆加密)',
    table_prefix       VARCHAR(64) NOT NULL COMMENT '镜像表名前缀',
    status             VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected/syncing/active/error/disabled',
    binlog_file        VARCHAR(128) NULL COMMENT 'binlog 文件名',
    binlog_pos         BIGINT NULL COMMENT 'binlog 位点',
    sync_error         TEXT NULL COMMENT '最近同步错误',
    last_sync_at       DATETIME NULL COMMENT '最近同步时间',
    created_by         BIGINT NULL COMMENT '申请人/创建人',
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    reviewed_by        BIGINT NULL COMMENT '审批人',
    reviewed_at        DATETIME NULL COMMENT '审批时间',
    UNIQUE KEY uq_ds_host_db (host, port, `database`),
    KEY idx_ds_status (status)
)
"""


async def seed():
    """初始化 data_source 表"""
    meta_mysql_client_manager.init()

    async with meta_mysql_client_manager.session_factory() as session:
        await session.execute(text(DATA_SOURCE_DDL))
        await session.commit()
        print("data_source 表已就绪")

    await meta_mysql_client_manager.close()


if __name__ == "__main__":
    asyncio.run(seed())
