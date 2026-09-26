"""运行时模型设置

管理员可以在前端切换当前使用的 DeepSeek 模型，切换结果持久化到
logs/model_setting.json，进程重启后仍生效；未设置时回退到配置里的默认模型。
llm 模块通过 current() 读取当前模型名，切换后自动重建模型实例。
"""

import json
from pathlib import Path

from app.conf.app_config import app_config
from app.core.log import logger

_SETTING_FILE = Path(__file__).parents[2] / "logs" / "model_setting.json"


class RuntimeModel:
    """进程内共享的运行时模型设置"""

    def __init__(self) -> None:
        self._current: str | None = None

    def available(self) -> list[str]:
        """返回可切换的模型列表（来自配置）"""
        return list(app_config.llm.available_models)

    def current(self) -> str:
        """返回当前生效的模型名，优先取持久化设置，否则回退配置默认值"""
        if self._current is not None:
            return self._current

        model = self._load()
        if model and model in self.available():
            self._current = model
            return model

        self._current = app_config.llm.model_name
        return self._current

    def set_model(self, name: str) -> str:
        """切换模型名并持久化，非法模型抛 ValueError"""
        available = self.available()
        if name not in available:
            raise ValueError(f"不支持的模型：{name}，可选：{'、'.join(available)}")

        self._current = name
        self._save(name)
        logger.info("运行时模型已切换为 %s", name)
        return name

    def _load(self) -> str | None:
        try:
            if _SETTING_FILE.exists():
                data = json.loads(_SETTING_FILE.read_text(encoding="utf-8"))
                return data.get("model")
        except Exception as e:  # noqa: BLE001
            logger.warning("读取模型设置失败：%s", e)
        return None

    def _save(self, name: str) -> None:
        try:
            _SETTING_FILE.parent.mkdir(parents=True, exist_ok=True)
            _SETTING_FILE.write_text(
                json.dumps({"model": name}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("写入模型设置失败：%s", e)


runtime_model = RuntimeModel()
