from app.core.config import Settings
from app.integrations.ocr.azure_di import AzureDocumentIntelligenceProvider
from app.integrations.ocr.base import OCRProvider, VisionProvider
from app.integrations.ocr.errors import OCRNotConfigured
from app.integrations.ocr.fake import FakeOCRProvider, FakeVisionProvider
from app.integrations.ocr.vision import CloudVisionProvider

PROVIDERS = ("fake", "cloud")


def _check_name(name: str) -> None:
    if name not in PROVIDERS:
        raise ValueError(f"未知的 OCR_PROVIDER：{name}，合法值是 {'、'.join(PROVIDERS)}")


def get_ocr_provider(name: str, settings: Settings | None = None) -> OCRProvider:
    """依 OCR_PROVIDER 選擇版面分析實作。cloud 缺設定時立刻拋 OCRNotConfigured。"""
    _check_name(name)
    if name == "fake":
        return FakeOCRProvider()
    if settings is None:
        raise ValueError("OCR_PROVIDER=cloud 需要傳入 settings")
    missing = [
        field
        for field, value in (
            ("OCR_DI_ENDPOINT", settings.ocr_di_endpoint),
            ("OCR_DI_API_KEY", settings.ocr_di_api_key),
        )
        if not value
    ]
    if missing:
        raise OCRNotConfigured(missing)
    return AzureDocumentIntelligenceProvider(
        endpoint=settings.ocr_di_endpoint,  # type: ignore[arg-type]
        api_key=settings.ocr_di_api_key,  # type: ignore[arg-type]
    )


def get_vision_provider(name: str, settings: Settings | None = None) -> VisionProvider:
    """依 OCR_PROVIDER 選擇視覺模型實作。端點與金鑰沿用 LLM_*，模型名稱 OCR_VISION_MODEL 優先。"""
    _check_name(name)
    if name == "fake":
        return FakeVisionProvider()
    if settings is None:
        raise ValueError("OCR_PROVIDER=cloud 需要傳入 settings")
    model = settings.ocr_vision_model or settings.llm_model
    missing = [
        field
        for field, value in (
            ("LLM_ENDPOINT", settings.llm_endpoint),
            ("LLM_API_KEY", settings.llm_api_key),
            ("OCR_VISION_MODEL（或 LLM_MODEL）", model),
        )
        if not value
    ]
    if missing:
        raise OCRNotConfigured(missing)
    return CloudVisionProvider(
        endpoint=settings.llm_endpoint,  # type: ignore[arg-type]
        api_key=settings.llm_api_key,  # type: ignore[arg-type]
        model=model,  # type: ignore[arg-type]
        timeout_seconds=settings.ocr_vision_timeout_seconds,
    )
