"""整合層提案 §11.2：FakeLLMProvider 的腳本、例外與 calls。"""

import pytest

from app.integrations.llm import (
    FakeLLMProvider,
    FakeResponse,
    JsonSchema,
    LLMConversationNotFound,
    LLMOutputRejected,
    LLMUnavailable,
    ToolCall,
    ToolResult,
    ToolSpec,
)

SCHEMA = JsonSchema(
    name="reply",
    schema={
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
        "additionalProperties": False,
    },
)
TOOL = ToolSpec(
    name="search_games",
    description="查桌遊",
    parameters={
        "type": "object",
        "properties": {"players": {"type": "integer"}},
        "required": ["players"],
        "additionalProperties": False,
    },
)
TOOL_CALL = ToolCall(call_id="call_1", name="search_games", arguments={"players": 4})


def respond(fake: FakeLLMProvider, **overrides: object):
    kwargs: dict[str, object] = {
        "instructions": "你是桌遊推薦助理",
        "input": "想找 4 人玩的歡樂遊戲",
        "tools": [TOOL],
        "output_schema": SCHEMA,
        "previous_response_id": None,
    }
    kwargs.update(overrides)
    return fake.respond(**kwargs)


def generate_json(fake: FakeLLMProvider) -> dict:
    return fake.generate_json(instructions="擷取候選詞", input="一段心得", schema=SCHEMA)


def test_respond_follows_script_and_chains_response_ids() -> None:
    fake = FakeLLMProvider(
        responses=[
            FakeResponse(tool_calls=[TOOL_CALL], input_tokens=10, output_tokens=5),
            FakeResponse(output={"message": "推薦《璀璨寶石》"}),
        ]
    )

    first = respond(fake)
    second = respond(
        fake,
        input=[ToolResult(call_id="call_1", output={"games": []})],
        previous_response_id=first.response_id,
    )

    assert first.tool_calls == [TOOL_CALL]
    assert first.output is None
    assert first.input_tokens == 10
    assert first.output_tokens == 5
    assert second.output == {"message": "推薦《璀璨寶石》"}
    assert second.tool_calls == []
    assert first.response_id != second.response_id


def test_unknown_previous_response_id_raises_without_consuming_script() -> None:
    fake = FakeLLMProvider(responses=[FakeResponse(output={"message": "第一筆"})])

    with pytest.raises(LLMConversationNotFound):
        respond(fake, previous_response_id="resp_expired")

    assert respond(fake).output == {"message": "第一筆"}


def test_respond_raises_scripted_exception() -> None:
    fake = FakeLLMProvider(responses=[LLMOutputRejected("被內容過濾擋下")])

    with pytest.raises(LLMOutputRejected, match="被內容過濾擋下"):
        respond(fake)


def test_generate_json_raises_scripted_exception() -> None:
    fake = FakeLLMProvider(json_outputs=[LLMUnavailable("逾時")])

    with pytest.raises(LLMUnavailable, match="逾時"):
        generate_json(fake)


def test_respond_raises_assertion_error_when_script_runs_out() -> None:
    fake = FakeLLMProvider(responses=[FakeResponse(output={"message": "唯一一筆"})])
    respond(fake)

    with pytest.raises(AssertionError):
        respond(fake)


def test_generate_json_raises_assertion_error_when_script_runs_out() -> None:
    fake = FakeLLMProvider(json_outputs=[{"terms": []}])
    generate_json(fake)

    with pytest.raises(AssertionError):
        generate_json(fake)


def test_respond_without_script_raises_llm_unavailable() -> None:
    with pytest.raises(LLMUnavailable, match="沒有設定模型"):
        respond(FakeLLMProvider())


def test_generate_json_without_script_raises_llm_unavailable() -> None:
    with pytest.raises(LLMUnavailable, match="沒有設定模型"):
        generate_json(FakeLLMProvider())


def test_calls_record_method_name_and_all_arguments() -> None:
    fake = FakeLLMProvider(responses=[FakeResponse(output={"message": "好"})])

    respond(fake)

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call.method == "respond"
    assert call.kwargs == {
        "instructions": "你是桌遊推薦助理",
        "input": "想找 4 人玩的歡樂遊戲",
        "tools": [TOOL],
        "output_schema": SCHEMA,
        "previous_response_id": None,
        "allow_tool_calls": True,
    }


def test_generate_json_returns_scripted_outputs_in_order() -> None:
    fake = FakeLLMProvider(json_outputs=[{"terms": ["歡樂"]}, {"terms": ["燒腦"]}])

    assert generate_json(fake) == {"terms": ["歡樂"]}
    assert generate_json(fake) == {"terms": ["燒腦"]}
