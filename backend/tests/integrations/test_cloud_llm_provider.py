"""整合層提案 §11.4：LLM 雲端實作。用 FakeAzureTransport 假造 Azure 的回應，不連網路。"""

import json
from urllib.parse import urlparse

import pytest

from app.integrations.llm import (
    JsonSchema,
    LLMConversationNotFound,
    LLMError,
    LLMOutputRejected,
    LLMResponse,
    LLMUnavailable,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from app.integrations.llm.cloud import CloudLLMProvider
from tests.integrations.fake_azure import (
    FakeAzureTransport,
    content_filter_error,
    error_response,
    function_call_item,
    message_item,
    reasoning_item,
    refusal_item,
    response_ok,
    transient_failures,
)

ENDPOINT = "https://example.openai.azure.com/openai/v1/"
DEPLOYMENT = "test-deployment"

REPLY_SCHEMA = JsonSchema(
    name="reply",
    schema={
        "type": "object",
        "properties": {"reply": {"type": "string"}},
        "required": ["reply"],
        "additionalProperties": False,
    },
)
SEARCH_TOOL = ToolSpec(
    name="search_games",
    description="查桌遊",
    parameters={
        "type": "object",
        "properties": {"players": {"type": "integer"}},
        "required": ["players"],
        "additionalProperties": False,
    },
)


def make_provider(
    transport: FakeAzureTransport, *, reasoning_effort: str | None = None
) -> CloudLLMProvider:
    return CloudLLMProvider(
        endpoint=ENDPOINT,
        api_key="test-key",
        model=DEPLOYMENT,
        reasoning_effort=reasoning_effort,
        timeout_seconds=30,
        http_client=transport.client(),
    )


def call_respond(provider: CloudLLMProvider, **overrides: object) -> LLMResponse:
    kwargs: dict[str, object] = {
        "instructions": "你是推薦 Agent",
        "input": "想找 4 個人玩的派對遊戲",
        "tools": [SEARCH_TOOL],
        "output_schema": REPLY_SCHEMA,
        "previous_response_id": "resp_prev",
    }
    kwargs.update(overrides)
    return provider.respond(**kwargs)  # type: ignore[arg-type]


def call_generate_json(provider: CloudLLMProvider) -> dict:
    return provider.generate_json(
        instructions="依 schema 回答", input="今天想玩什麼", schema=REPLY_SCHEMA
    )


def call_method(provider: CloudLLMProvider, method: str) -> object:
    if method == "generate":
        return provider.generate("你好")
    if method == "generate_json":
        return call_generate_json(provider)
    return call_respond(provider)


# --- 送出的請求 ---


def test_respond_sends_stateful_request_with_strict_tools_and_schema() -> None:
    transport = FakeAzureTransport([response_ok([message_item('{"reply": "好"}')])])

    call_respond(make_provider(transport))

    request = transport.requests[0]
    url = urlparse(str(request.url))
    assert request.method == "POST"
    assert url.path == "/openai/v1/responses"
    assert "api-version" not in url.query  # v1 端點不帶 api-version（ticket 02 第 3 點）
    body = transport.json_body()
    assert body["model"] == DEPLOYMENT
    assert body["store"] is True
    assert body["instructions"] == "你是推薦 Agent"
    assert body["input"] == "想找 4 個人玩的派對遊戲"
    assert body["previous_response_id"] == "resp_prev"
    assert body["tools"] == [
        {
            "type": "function",
            "name": "search_games",
            "description": "查桌遊",
            "parameters": SEARCH_TOOL.parameters,
            "strict": True,
        }
    ]
    assert body["parallel_tool_calls"] is False
    assert body["text"] == {
        "format": {
            "type": "json_schema",
            "name": "reply",
            "schema": REPLY_SCHEMA.schema,
            "strict": True,
        }
    }
    assert "tool_choice" not in body


def test_respond_without_tool_calls_still_sends_tools_with_tool_choice_none() -> None:
    transport = FakeAzureTransport([response_ok([message_item('{"reply": "好"}')])])

    call_respond(make_provider(transport), allow_tool_calls=False)

    body = transport.json_body()
    assert len(body["tools"]) == 1
    assert body["tool_choice"] == "none"


def test_respond_sends_tool_results_as_function_call_output_without_escaping() -> None:
    transport = FakeAzureTransport([response_ok([message_item('{"reply": "好"}')])])

    call_respond(
        make_provider(transport),
        input=[ToolResult(call_id="call_1", output={"games": ["卡坦島"]})],
    )

    items = transport.json_body()["input"]
    assert len(items) == 1
    assert items[0]["type"] == "function_call_output"
    assert items[0]["call_id"] == "call_1"
    assert isinstance(items[0]["output"], str)
    assert "卡坦島" in items[0]["output"]  # ensure_ascii=False，中文沒有變成 \uXXXX
    assert json.loads(items[0]["output"]) == {"games": ["卡坦島"]}


# --- Azure 的回應 ---


def test_respond_returns_tool_calls_and_token_usage() -> None:
    transport = FakeAzureTransport(
        [
            response_ok(
                [reasoning_item(), function_call_item("call_1", "search_games", {"players": 4})],
                response_id="resp_new",
                input_tokens=752,
                output_tokens=178,
            )
        ]
    )

    result = call_respond(make_provider(transport))

    assert result.response_id == "resp_new"
    assert result.tool_calls == [
        ToolCall(call_id="call_1", name="search_games", arguments={"players": 4})
    ]
    assert result.output is None
    assert result.input_tokens == 752
    assert result.output_tokens == 178


def test_respond_returns_parsed_json_output() -> None:
    transport = FakeAzureTransport(
        [response_ok([reasoning_item(), message_item('{"reply": "推薦卡坦島"}')])]
    )

    result = call_respond(make_provider(transport))

    assert result.output == {"reply": "推薦卡坦島"}
    assert result.tool_calls == []


def test_generate_json_sends_stateless_request_and_returns_dict() -> None:
    transport = FakeAzureTransport([response_ok([message_item('{"reply": "好"}')])])

    result = call_generate_json(make_provider(transport))

    body = transport.json_body()
    assert body["store"] is False
    assert "tools" not in body
    assert body["instructions"] == "依 schema 回答"
    assert body["input"] == "今天想玩什麼"
    assert body["text"]["format"] == {
        "type": "json_schema",
        "name": "reply",
        "schema": REPLY_SCHEMA.schema,
        "strict": True,
    }
    assert result == {"reply": "好"}


def test_generate_returns_text_without_storing() -> None:
    transport = FakeAzureTransport([response_ok([message_item("你好，有什麼可以幫忙？")])])

    result = make_provider(transport).generate("你好")

    body = transport.json_body()
    assert body["store"] is False
    assert body["input"] == "你好"
    assert result == "你好，有什麼可以幫忙？"


@pytest.mark.parametrize("method", ["generate", "generate_json", "respond"])
def test_reasoning_effort_is_sent_when_configured(method: str) -> None:
    transport = FakeAzureTransport([response_ok([message_item('{"reply": "好"}')])])

    call_method(make_provider(transport, reasoning_effort="low"), method)

    assert transport.json_body()["reasoning"] == {"effort": "low"}


@pytest.mark.parametrize("method", ["generate", "generate_json", "respond"])
def test_reasoning_is_omitted_when_not_configured(method: str) -> None:
    transport = FakeAzureTransport([response_ok([message_item('{"reply": "好"}')])])

    call_method(make_provider(transport), method)

    assert "reasoning" not in transport.json_body()


# --- 錯誤轉換（ticket 02 第 4 節「給 08 的轉換規則」） ---


@pytest.mark.parametrize(
    "error",
    [
        error_response(
            400,
            code="previous_response_not_found",
            param="previous_response_id",
            message="Previous response with id 'resp_000' not found.",
        ),
        error_response(
            400,
            code="invalid_value",
            param="previous_response_id",
            message="Invalid 'previous_response_id': 'not-a-valid-id'.",
        ),
    ],
    ids=["not-found", "invalid-value"],
)
def test_invalid_previous_response_id_raises_conversation_not_found(error) -> None:
    transport = FakeAzureTransport([error])

    with pytest.raises(LLMConversationNotFound):
        call_respond(make_provider(transport))
    assert len(transport.requests) == 1


@pytest.mark.parametrize("kind", ["429", "500", "503", "timeout"])
def test_transient_errors_raise_unavailable_after_sdk_retries(kind: str) -> None:
    transport = FakeAzureTransport(transient_failures(kind))

    with pytest.raises(LLMUnavailable):
        call_generate_json(make_provider(transport))
    assert len(transport.requests) == 3  # 第 1 次加上 SDK 重試 2 次


@pytest.mark.parametrize(
    "reply",
    [
        content_filter_error(),
        response_ok(
            [message_item("I'm sorry, but I cannot assist with that request.")],
            status="incomplete",
            incomplete_reason="content_filter",
        ),
    ],
    ids=["input-blocked-400", "output-blocked-200"],
)
def test_content_filter_raises_output_rejected(reply) -> None:
    transport = FakeAzureTransport([reply])

    with pytest.raises(LLMOutputRejected):
        call_generate_json(make_provider(transport))


def test_refusal_raises_output_rejected() -> None:
    transport = FakeAzureTransport([response_ok([refusal_item("I can't help with that.")])])

    with pytest.raises(LLMOutputRejected):
        call_generate_json(make_provider(transport))


def test_truncated_output_raises_output_rejected() -> None:
    transport = FakeAzureTransport(
        [
            response_ok(
                [message_item('{"reply": "被截')],
                status="incomplete",
                incomplete_reason="max_output_tokens",
            )
        ]
    )

    with pytest.raises(LLMOutputRejected):
        call_generate_json(make_provider(transport))


def test_wrong_api_key_raises_base_llm_error_only() -> None:
    transport = FakeAzureTransport([error_response(401, code="invalid_api_key")])

    with pytest.raises(LLMError) as raised:
        call_generate_json(make_provider(transport))
    assert not isinstance(
        raised.value, LLMUnavailable | LLMConversationNotFound | LLMOutputRejected
    )
    assert len(transport.requests) == 1
