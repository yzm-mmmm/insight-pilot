"""模型价格服务

DeepSeek 没有公开的价格 API，这里通过爬取官方定价页来获取各模型单价。
价格以「懒加载 + 当天落盘缓存」方式获取：某天第一次需要某模型价格时才发起爬取，
成功后写入 logs/model_prices.json 缓存当天有效，进程重启也不丢；爬取失败则回退到
配置里的兜底单价，保证成本估算始终可用。

价格单位统一为人民币（元 / 1M token）。成本估算按「输入缓存未命中 + 输出」计，
并依据北京时间切空闲/高峰时段（空闲价为高峰价的一半）。
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.conf.app_config import app_config
from app.core.log import logger

_BEIJING = ZoneInfo("Asia/Shanghai")
_CACHE_FILE = Path(__file__).parents[2] / "logs" / "model_prices.json"

# 高峰时段：北京时间工作日 9:00-12:00、14:00-18:00（中国法定节假日暂按非高峰近似）
_PEAK_WINDOWS = ((dtime(9, 0), dtime(12, 0)), (dtime(14, 0), dtime(18, 0)))


@dataclass
class PriceTier:
    """空闲/高峰两档单价"""

    off_peak: float
    peak: float


@dataclass
class ModelPrice:
    """单个模型的计费单价（元 / 1M token）"""

    model: str
    input_cache_miss: PriceTier
    output: PriceTier
    currency: str = "CNY"


def _is_peak(dt: datetime) -> bool:
    """判断给定北京时间是否处于高峰计费时段"""
    if dt.weekday() >= 5:  # 周末
        return False
    t = dt.time()
    return any(start <= t < end for start, end in _PEAK_WINDOWS)


def estimate_cost_cny(
    prompt_tokens: int,
    completion_tokens: int,
    price: ModelPrice,
    dt: datetime | None = None,
) -> float:
    """按 token 数估算一次调用成本（元），默认按当前北京时间的空闲/高峰档计价"""
    now = dt or datetime.now(_BEIJING)
    peak = _is_peak(now)
    input_price = price.input_cache_miss.peak if peak else price.input_cache_miss.off_peak
    output_price = price.output.peak if peak else price.output.off_peak
    return prompt_tokens / 1_000_000 * input_price + completion_tokens / 1_000_000 * output_price


def _parse_prices(html_text: str) -> dict[str, ModelPrice]:
    """从定价页 HTML 解析各模型价格，失败抛 ValueError"""
    table_match = re.search(r"<table.*?</table>", html_text, re.S)
    if not table_match:
        raise ValueError("未找到定价表格")
    table = table_match.group(0)

    models: list[str] = []
    seen: set[str] = set()
    for name in re.findall(r"deepseek-[a-z0-9][a-z0-9-]*", table):
        if name not in seen:
            seen.add(name)
            models.append(name)

    numbers = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)元", table)]
    if not models or len(numbers) < len(models) * 6:
        raise ValueError(f"解析到的模型/价格数量不匹配：{models} / {len(numbers)}")

    prices: dict[str, ModelPrice] = {}
    for idx, model in enumerate(models):
        vals = numbers[idx :: len(models)][:6]
        # 顺序：输入命中(空闲/高峰)、输入未命中(空闲/高峰)、输出(空闲/高峰)
        prices[model] = ModelPrice(
            model=model,
            input_cache_miss=PriceTier(off_peak=vals[2], peak=vals[3]),
            output=PriceTier(off_peak=vals[4], peak=vals[5]),
        )
    return prices


def _price_to_dict(price: ModelPrice) -> dict:
    return {
        "input_cache_miss_off_peak": price.input_cache_miss.off_peak,
        "input_cache_miss_peak": price.input_cache_miss.peak,
        "output_off_peak": price.output.off_peak,
        "output_peak": price.output.peak,
        "currency": price.currency,
    }


def _price_from_dict(model: str, data: dict) -> ModelPrice:
    return ModelPrice(
        model=model,
        input_cache_miss=PriceTier(
            off_peak=float(data["input_cache_miss_off_peak"]),
            peak=float(data["input_cache_miss_peak"]),
        ),
        output=PriceTier(
            off_peak=float(data["output_off_peak"]),
            peak=float(data["output_peak"]),
        ),
        currency=data.get("currency", "CNY"),
    )


class PriceCache:
    """懒加载 + 当天落盘缓存的模型价格提供器"""

    def __init__(self, source_url: str, fallback: dict, aliases: dict):
        self._source_url = source_url
        self._fallback = fallback
        self._aliases = aliases
        # fetched_on -> model -> ModelPrice
        self._memory: dict[str, dict[str, ModelPrice]] = {}
        self._disk: dict | None = None

    @staticmethod
    def _today() -> str:
        return datetime.now(_BEIJING).strftime("%Y-%m-%d")

    def _load_disk(self) -> dict:
        if self._disk is None:
            try:
                self._disk = (
                    json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
                    if _CACHE_FILE.exists()
                    else {}
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("读取模型价格缓存失败：%s", e)
                self._disk = {}
        return self._disk

    def _save_disk(self, fetched_on: str, prices: dict[str, ModelPrice]) -> None:
        data = {
            "fetched_on": fetched_on,
            "prices": {m: _price_to_dict(p) for m, p in prices.items()},
        }
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _CACHE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._disk = data
        except Exception as e:  # noqa: BLE001
            logger.warning("写入模型价格缓存失败：%s", e)

    def _from_fallback(self, model: str) -> ModelPrice | None:
        raw = self._fallback.get(model)
        if not raw:
            return None
        return ModelPrice(
            model=model,
            input_cache_miss=PriceTier(
                off_peak=float(raw["input_cache_miss_off_peak"]),
                peak=float(raw["input_cache_miss_peak"]),
            ),
            output=PriceTier(
                off_peak=float(raw["output_off_peak"]),
                peak=float(raw["output_peak"]),
            ),
        )

    async def fetch_prices(self) -> dict[str, ModelPrice]:
        """爬取定价页并解析，失败抛异常由调用方兜底"""
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(self._source_url)
            resp.raise_for_status()
            html_text = resp.content.decode("utf-8", errors="ignore")
            return _parse_prices(html_text)

    async def get_price(self, model: str) -> ModelPrice:
        """获取某模型当天的价格，懒加载：内存缓存 → 磁盘缓存 → 爬取 → 兜底"""
        # 旧别名（如 deepseek-chat）先解析到定价页里的规范模型名
        model = self._aliases.get(model, model)
        today = self._today()

        cached = self._memory.get(today)
        if cached and model in cached:
            return cached[model]

        disk = self._load_disk()
        if disk.get("fetched_on") == today:
            prices = {
                m: _price_from_dict(m, d) for m, d in (disk.get("prices") or {}).items()
            }
            self._memory[today] = prices
            if model in prices:
                return prices[model]

        try:
            fetched = await self.fetch_prices()
        except Exception as e:  # noqa: BLE001
            logger.warning("爬取模型价格失败，回退兜底价：%s", e)
            fetched = {}

        # 用兜底价补齐缺失的模型，保证已配置模型都有价
        for name in self._fallback:
            fetched.setdefault(name, self._from_fallback(name))

        if fetched:
            self._save_disk(today, fetched)
        self._memory[today] = fetched

        if model in fetched:
            return fetched[model]

        fallback = self._from_fallback(model)
        if fallback:
            return fallback
        raise ValueError(f"未找到模型 {model} 的价格，且无兜底配置")


price_cache = PriceCache(
    source_url=app_config.model_price.source_url,
    fallback=app_config.model_price.fallback,
    aliases=app_config.model_price.aliases,
)
