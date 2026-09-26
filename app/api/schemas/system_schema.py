"""系统设置接口请求/响应体定义

覆盖管理员专用的模型切换与 DeepSeek 余额查询两个接口的输入输出结构。
"""

from pydantic import BaseModel


class ModelSettingRequest(BaseModel):
    """切换运行时模型的请求体"""

    model: str


class ModelSettingResponse(BaseModel):
    """当前模型与可切换模型列表"""

    current: str
    available: list[str]


class DeepSeekBalanceResponse(BaseModel):
    """DeepSeek 账户余额查询结果，查询失败时 is_available 为 False"""

    is_available: bool = False
    currency: str | None = None
    total_balance: str | None = None
    granted_balance: str | None = None
    topped_up_balance: str | None = None
    message: str | None = None
