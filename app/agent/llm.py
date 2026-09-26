"""
电商问数 Agent 使用的大模型实例

集中初始化一个 OpenAI 兼容的 Chat Model，供节点或本地测试直接复用。
模型名不再固定为配置默认值，而是按运行时设置读取：管理员切换模型后，
get_llm() 会自动用新模型名重建实例，节点调用时无需关心切换细节。
"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.conf.app_config import app_config
from app.core.runtime_model import runtime_model

# 缓存当前模型名对应的实例，切换模型时重建，避免每次节点调用重复初始化
_cached_llm: BaseChatModel | None = None
_cached_model: str | None = None


def _build(model_name: str) -> BaseChatModel:
    return init_chat_model(
        model=model_name,
        # 硅基流动等服务兼容 OpenAI 协议时，可以使用 openai provider 接入
        model_provider="openai",
        base_url=app_config.llm.base_url,
        api_key=app_config.llm.api_key,
        # 字段扩展、SQL 生成更看重稳定性，所以这里关闭随机发散
        temperature=0,
    )


def get_llm() -> BaseChatModel:
    """返回当前运行时模型，模型名变化时自动重建实例"""
    global _cached_llm, _cached_model
    model_name = runtime_model.current()
    if _cached_llm is None or _cached_model != model_name:
        _cached_llm = _build(model_name)
        _cached_model = model_name
    return _cached_llm


if __name__ == "__main__":
    # 本地快速验证 LLM 配置是否能正常调用
    print(get_llm().invoke("你好").content)
