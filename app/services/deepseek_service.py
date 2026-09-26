"""DeepSeek 账户服务

负责查询 DeepSeek 账户余额：通过后端代理调用官方余额接口，
避免把 API Key 暴露给前端。余额信息只读，不做任何扣费操作。
"""

import httpx

from app.conf.app_config import app_config

_BALANCE_URL = "https://api.deepseek.com/user/balance"


class DeepSeekService:
    """封装 DeepSeek 官方余额接口的代理调用"""

    async def fetch_balance(self) -> dict:
        """查询账户余额，返回 balance_infos 里 CNY 档（或首档）的结构化信息

        未配置 API Key 时抛 ValueError；网络或上游错误抛 httpx 异常，由路由兜底。
        """
        api_key = app_config.llm.api_key
        if not api_key:
            raise ValueError("未配置 DeepSeek API Key，无法查询余额")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _BALANCE_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        infos = data.get("balance_infos") or []
        if not data.get("is_available") or not infos:
            return {"is_available": False}

        info = next((i for i in infos if i.get("currency") == "CNY"), infos[0])
        return {
            "is_available": True,
            "currency": info.get("currency"),
            "total_balance": str(info.get("total_balance")),
            "granted_balance": str(info.get("granted_balance")),
            "topped_up_balance": str(info.get("topped_up_balance")),
        }
