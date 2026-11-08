from app.core.config import Settings
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.fake import FakeLLMProvider

# 🚧 cloud 由 games_advisor-impl ticket 08 實作
UNIMPLEMENTED = ("cloud", "local")


def get_llm_provider(name: str, settings: Settings | None = None) -> LLMProvider:
    """依 LLM_PROVIDER 選擇實作。尚未實作的值明確報錯，不靜默退回 fake。

    fake 不需要 settings；雲端實作會從 settings 讀 LLM_* 欄位。
    """
    if name == "fake":
        return FakeLLMProvider()
    if name in UNIMPLEMENTED:
        raise NotImplementedError(f"LLM_PROVIDER={name} 尚未實作，目前只支援 fake")
    raise ValueError(f"未知的 LLM_PROVIDER：{name}")
