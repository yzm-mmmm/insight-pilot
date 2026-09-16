"""
数据源接口请求/响应体定义

集中声明数据源申请、审批、列表与同步相关接口的输入输出结构。
出于安全考虑，所有出参都不包含密码或密码密文。
"""

from pydantic import BaseModel, Field

from app.api.schemas.common import UTCOptionalDateTime


class DataSourceCreateRequest(BaseModel):
    """接入数据库申请请求体"""

    name: str = Field(description="数据源名称")
    description: str | None = Field(default=None, description="说明")
    host: str = Field(description="源库主机")
    port: int = Field(description="源库端口")
    database: str = Field(description="源库名")
    username: str = Field(description="源库账号")
    password: str = Field(description="源库密码（可逆加密存储，接口不回传）")


class DataSourceOut(BaseModel):
    """一条数据源记录（不含密码）"""

    id: int
    name: str
    description: str | None = None
    host: str
    port: int
    database: str
    username: str
    table_prefix: str
    status: str
    binlog_file: str | None = None
    binlog_pos: int | None = None
    sync_error: str | None = None
    last_sync_at: UTCOptionalDateTime
    created_by: int | None = None
    created_at: UTCOptionalDateTime
    reviewed_by: int | None = None
    reviewed_at: UTCOptionalDateTime


class ReviewRequest(BaseModel):
    """审批请求体"""

    status: str = Field(description="approved / rejected")


class SyncResult(BaseModel):
    """同步触发结果"""

    ok: bool
    status: str
