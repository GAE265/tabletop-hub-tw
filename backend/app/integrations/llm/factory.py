from app.integrations.llm.base import LLMProvider
from app.integrations.llm.fake import FakeLLMProvider

UNIMPLEMENTED = ("cloud", "local")


def get_llm_provider(name: str) -> LLMProvider:
    """依 LLM_PROVIDER 選擇實作。尚未實作的值明確報錯，不靜默退回 fake。"""
    if name == "fake":
        return FakeLLMProvider()
    if name in UNIMPLEMENTED:
        raise NotImplementedError(f"LLM_PROVIDER={name} 尚未實作，目前只支援 fake")
    raise ValueError(f"未知的 LLM_PROVIDER：{name}")
