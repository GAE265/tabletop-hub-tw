"""OCR factory：依 OCR_PROVIDER 選擇實作，缺設定時明確報錯。不連網路。"""

import pytest

from app.core.config import Settings
from app.integrations.ocr import (
    FakeOCRProvider,
    FakeVisionProvider,
    OCRNotConfigured,
    get_ocr_provider,
    get_vision_provider,
)
from app.integrations.ocr.azure_di import AzureDocumentIntelligenceProvider
from app.integrations.ocr.vision import CloudVisionProvider

DB = "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, database_url=DB, **overrides)  # type: ignore[arg-type]


def test_fake_needs_no_settings() -> None:
    assert isinstance(get_ocr_provider("fake"), FakeOCRProvider)
    assert isinstance(get_vision_provider("fake"), FakeVisionProvider)


def test_unknown_provider_is_value_error_not_fake() -> None:
    with pytest.raises(ValueError, match="fake、cloud"):
        get_ocr_provider("local", settings())
    with pytest.raises(ValueError, match="fake、cloud"):
        get_vision_provider("local", settings())


def test_cloud_ocr_lists_missing_settings() -> None:
    with pytest.raises(OCRNotConfigured) as info:
        get_ocr_provider("cloud", settings())

    assert info.value.missing == ["OCR_DI_ENDPOINT", "LLM_API_KEY"]
    assert "OCR_DI_ENDPOINT" in str(info.value)


def test_cloud_ocr_does_not_borrow_llm_endpoint() -> None:
    with pytest.raises(OCRNotConfigured) as info:
        get_ocr_provider(
            "cloud",
            settings(llm_endpoint="https://res.openai.azure.com/openai/v1/", llm_api_key="k"),
        )
    assert info.value.missing == ["OCR_DI_ENDPOINT"]


def test_cloud_ocr_with_settings() -> None:
    provider = get_ocr_provider(
        "cloud",
        settings(ocr_di_endpoint="https://res.cognitiveservices.azure.com/", llm_api_key="k"),
    )
    assert isinstance(provider, AzureDocumentIntelligenceProvider)


def test_cloud_vision_lists_missing_settings() -> None:
    with pytest.raises(OCRNotConfigured) as info:
        get_vision_provider("cloud", settings())

    assert info.value.missing == [
        "OCR_VISION_ENDPOINT（或 LLM_ENDPOINT）",
        "LLM_API_KEY",
        "OCR_VISION_MODEL（或 LLM_MODEL）",
    ]


def test_cloud_vision_uses_ocr_vision_endpoint_when_set() -> None:
    provider = get_vision_provider(
        "cloud",
        settings(
            llm_endpoint="https://llm.openai.azure.com/openai/v1/",
            ocr_vision_endpoint="https://vision.openai.azure.com/openai/v1/",
            llm_api_key="k",
            llm_model="m",
        ),
    )
    assert str(provider._client.base_url).startswith("https://vision.openai.azure.com")


def test_cloud_vision_falls_back_to_llm_model() -> None:
    provider = get_vision_provider(
        "cloud", settings(llm_endpoint="https://x.example/", llm_api_key="k", llm_model="m")
    )
    assert isinstance(provider, CloudVisionProvider)
    assert provider._model == "m"
    assert str(provider._client.base_url).startswith("https://x.example")


def test_cloud_vision_prefers_ocr_vision_model() -> None:
    provider = get_vision_provider(
        "cloud",
        settings(
            llm_endpoint="https://x.example/",
            llm_api_key="k",
            llm_model="m",
            ocr_vision_model="vision-m",
        ),
    )
    assert provider._model == "vision-m"


def test_default_provider_is_fake_and_timeout_is_120() -> None:
    config = settings()
    assert config.ocr_provider == "fake"
    assert config.ocr_vision_timeout_seconds == 120
