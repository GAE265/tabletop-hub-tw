import pytest

from app.integrations.llm import FakeLLMProvider, LLMProvider, get_llm_provider
from app.main import create_app


def test_fake_returns_fixed_text_for_any_prompt() -> None:
    provider = FakeLLMProvider()
    assert provider.generate("a") == provider.generate("完全不同的 prompt")


def test_fake_returns_custom_reply() -> None:
    assert FakeLLMProvider("你好").generate("hi") == "你好"


def test_fake_is_an_llm_provider() -> None:
    assert isinstance(FakeLLMProvider(), LLMProvider)


def test_factory_returns_fake_for_fake() -> None:
    assert isinstance(get_llm_provider("fake"), FakeLLMProvider)


@pytest.mark.parametrize("name", ["cloud", "local"])
def test_unimplemented_provider_raises_clear_error(name: str) -> None:
    with pytest.raises(NotImplementedError, match="尚未實作"):
        get_llm_provider(name)


def test_unknown_provider_raises_value_error() -> None:
    with pytest.raises(ValueError):
        get_llm_provider("nope")


def test_app_startup_fails_loudly_for_unimplemented_provider(make_settings) -> None:
    with pytest.raises(NotImplementedError):
        create_app(make_settings(llm_provider="cloud"))
