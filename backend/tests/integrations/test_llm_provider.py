import pytest
from pydantic import ValidationError

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


# cloud 已實作，「尚未實作的值要明確報錯」改由 local 驗證（整合層提案第 9 節第 2 點）
@pytest.mark.parametrize("name", ["local"])
def test_unimplemented_provider_raises_clear_error(name: str) -> None:
    with pytest.raises(NotImplementedError, match="尚未實作"):
        get_llm_provider(name)


def test_unknown_provider_raises_value_error() -> None:
    with pytest.raises(ValueError):
        get_llm_provider("nope")


def test_app_startup_fails_loudly_for_unimplemented_provider(make_settings) -> None:
    with pytest.raises(NotImplementedError):
        create_app(make_settings(llm_provider="local"))


@pytest.mark.parametrize("effort", ["none", "low", "medium", "high", "xhigh", "max"])
def test_valid_reasoning_effort_is_accepted(make_settings, effort: str) -> None:
    assert make_settings(llm_reasoning_effort=effort).llm_reasoning_effort == effort


def test_invalid_reasoning_effort_fails_startup_naming_the_field(make_settings) -> None:
    with pytest.raises(ValidationError, match="llm_reasoning_effort"):
        create_app(make_settings(llm_reasoning_effort="extreme"))
