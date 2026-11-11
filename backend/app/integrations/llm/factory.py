from app.core.config import Settings
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.cloud import CloudLLMProvider
from app.integrations.llm.fake import FakeLLMProvider

UNIMPLEMENTED = ("local",)


def get_llm_provider(name: str, settings: Settings | None = None) -> LLMProvider:
    """依 LLM_PROVIDER 選擇實作。尚未實作的值明確報錯，不靜默退回 fake。

    fake 不需要 settings；cloud 從 settings 讀 LLM_* 欄位，缺欄位時拋 ValueError。
    """
    if name == "fake":
        return FakeLLMProvider()
    if name == "cloud":
        return _cloud_provider(settings)
    if name in UNIMPLEMENTED:
        raise NotImplementedError(f"LLM_PROVIDER={name} 尚未實作，目前支援 fake、cloud")
    raise ValueError(f"未知的 LLM_PROVIDER：{name}")


def _cloud_provider(settings: Settings | None) -> CloudLLMProvider:
    if settings is None:
        raise ValueError("LLM_PROVIDER=cloud 需要傳入 settings")
    required = {
        "LLM_ENDPOINT": settings.llm_endpoint,
        "LLM_API_KEY": settings.llm_api_key,
        "LLM_MODEL": settings.llm_model,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"LLM_PROVIDER=cloud 缺少設定：{'、'.join(missing)}")
    return CloudLLMProvider(
        endpoint=settings.llm_endpoint,  # type: ignore[arg-type]
        api_key=settings.llm_api_key,  # type: ignore[arg-type]
        model=settings.llm_model,  # type: ignore[arg-type]
        reasoning_effort=settings.llm_reasoning_effort,
        timeout_seconds=settings.llm_timeout_seconds,
    )
