"""
`data_source` ORM 模型

定义元数据库中数据源表的结构，保存待接入/已接入的外部 MySQL
数据库连接信息与同步状态。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DataSourceMySQL(Base):
    """数据源表对应的 ORM 模型"""

    __tablename__ = "data_source"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="数据源名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="说明")
    host: Mapped[str] = mapped_column(String(128), nullable=False, comment="源库主机")
    port: Mapped[int] = mapped_column(Integer, nullable=False, comment="源库端口")
    database: Mapped[str] = mapped_column(String(128), nullable=False, comment="源库名")
    username: Mapped[str] = mapped_column(String(128), nullable=False, comment="源库账号")
    password_encrypted: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="源库密码(可逆加密)"
    )
    table_prefix: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="镜像表名前缀"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="pending",
        comment="pending/approved/rejected/syncing/active/error/disabled",
    )
    binlog_file: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="binlog 文件名")
    binlog_pos: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="binlog 位点")
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最近同步错误")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近同步时间")
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="申请人/创建人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="审批人")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="审批时间")
