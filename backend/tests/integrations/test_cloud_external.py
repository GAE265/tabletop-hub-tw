"""整合層提案 §11.6：外部服務測試，在本機連真的 Azure（AGENTS.md 7.6）。

預設不執行，CI 也不跑。本機執行：在 backend/ 跑 `uv run pytest -m external`。
目的只是確認連得上 Azure、回應格式和 FakeAzureTransport 假造的一致；行為細節由其他測試負責。
工具、schema、文字都自行編寫，不用桌遊或心得資料。跑一次的費用不到 NTD 1。
"""

import pytest

from app.core.config import Settings
from app.integrations.embedding import EmbeddingConfig, get_embedding_provider
from app.integrations.llm import (
    JsonSchema,
    LLMConversationNotFound,
    LLMProvider,
    ToolResult,
    ToolSpec,
    get_llm_provider,
)

pytestmark = pytest.mark.external

ANSWER_SCHEMA = JsonSchema(
    name="answer",
    schema={
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    },
)
WEATHER_TOOL = ToolSpec(
    name="lookup_weather",
    description="查詢某個城市今天的天氣",
    parameters={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
        "additionalProperties": False,
    },
)


def llm(settings: Settings) -> LLMProvider:
    return get_llm_provider("cloud", settings)


def test_respond_calls_tool_then_returns_output_matching_schema(
    external_settings: Settings,
) -> None:
    provider = llm(external_settings)
    instructions = "你是測試用的助理。回答天氣問題前，一定要先呼叫 lookup_weather 查詢。"

    first = provider.respond(
        instructions=instructions,
        input="台北今天天氣如何？",
        tools=[WEATHER_TOOL],
        output_schema=ANSWER_SCHEMA,
        previous_response_id=None,
    )
    assert first.tool_calls

    second = provider.respond(
        instructions=instructions,
        input=[
            ToolResult(call_id=call.call_id, output={"city": "台北", "weather": "晴天"})
            for call in first.tool_calls
        ],
        tools=[WEATHER_TOOL],
        output_schema=ANSWER_SCHEMA,
        previous_response_id=first.response_id,
    )
    assert second.tool_calls == []
    assert isinstance(second.output, dict)
    assert set(second.output) == {"answer"}
    assert isinstance(second.output["answer"], str)


def test_generate_json_returns_dict_matching_schema(external_settings: Settings) -> None:
    result = llm(external_settings).generate_json(
        instructions="只用一個詞回答。",
        input="晴天時天空通常是什麼顏色？",
        schema=ANSWER_SCHEMA,
    )

    assert set(result) == {"answer"}
    assert isinstance(result["answer"], str)


def test_embed_returns_vectors_with_configured_dimension(external_settings: Settings) -> None:
    provider = get_embedding_provider(
        EmbeddingConfig(
            provider="cloud",
            dim=external_settings.games_advisor_embedding_dim,
            endpoint=external_settings.games_advisor_embedding_endpoint,
            api_key=external_settings.games_advisor_embedding_api_key,
            model=external_settings.games_advisor_embedding_model,
        )
    )

    vectors = provider.embed(["今天天氣很好", "The weather is nice today"])

    assert len(vectors) == 2
    assert all(len(vector) == external_settings.games_advisor_embedding_dim for vector in vectors)


@pytest.mark.parametrize(
    "previous_response_id",
    ["resp_" + "0" * 48, "not-a-valid-id"],
    ids=["resp-prefixed", "garbage"],
)
def test_unknown_previous_response_id_raises_conversation_not_found(
    external_settings: Settings, previous_response_id: str
) -> None:
    with pytest.raises(LLMConversationNotFound):
        llm(external_settings).respond(
            instructions="你是測試用的助理。",
            input="你好",
            tools=[],
            output_schema=ANSWER_SCHEMA,
            previous_response_id=previous_response_id,
        )
