"""阿里雲的 cloud 實作，不需要金鑰的部分（host 實作 ticket 08）：

事件轉換、聲線對應、接話方式的設定、錯誤轉換。連線換成手寫的 FakeUpstream。
"""

import ast
import asyncio
import base64
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import app.integrations.realtime_voice as package
from app.core.config import Settings
from app.integrations.realtime_voice import (
    CloudRealtimeVoiceProvider,
    ConnectionLost,
    HostAudio,
    HostUtteranceEnded,
    HostUtteranceStarted,
    PlayerSpeechStarted,
    PlayerTranscript,
    RealtimeVoiceConfig,
    RealtimeVoiceConnection,
    RealtimeVoiceEvent,
    RealtimeVoiceUnavailable,
    SpeechNotAddressed,
    SpeechRequestResult,
    ToolRequested,
    VoiceToolSpec,
    get_realtime_voice_provider,
)
from tests.integrations import fake_realtime_upstream as wire
from tests.integrations.fake_realtime_upstream import FakeConnector, FakeUpstream

TOOL = VoiceToolSpec(
    name="lookup_rules",
    description="查規則",
    parameters={
        "type": "object",
        "properties": {"question": {"type": "string"}},
        "required": ["question"],
    },
)


def config(**overrides: Any) -> RealtimeVoiceConfig:
    values: dict[str, Any] = {
        "instructions": "你是主持人",
        "tools": [TOOL],
        "voice": "male",
        "turn_taking_mode": "auto",
        "history_turns": 50,
        "turn_sensitivity": 0.5,
    }
    values.update(overrides)
    return RealtimeVoiceConfig(**values)


def provider(connector: FakeConnector, **overrides: Any) -> CloudRealtimeVoiceProvider:
    kwargs: dict[str, Any] = {
        "api_key": "test-key",
        "api_host": "ws-test.ap-southeast-1.example.invalid",
        "model": "qwen-audio-3.1-realtime-flash",
        "connector": connector,
        # 測試不真的等：連線設定與「請回答」的結果都只等一下
        "session_timeout": 0.5,
        "create_timeout": 0.05,
        "retry_interval": 0.01,
    }
    kwargs.update(overrides)
    return CloudRealtimeVoiceProvider(**kwargs)


async def connect(
    upstream: FakeUpstream | None = None, **config_overrides: Any
) -> tuple[RealtimeVoiceConnection, FakeUpstream]:
    upstream = upstream or FakeUpstream()
    connection = await provider(FakeConnector(upstream)).connect(config(**config_overrides))
    return connection, upstream


async def collect(connection: RealtimeVoiceConnection, count: int) -> list[RealtimeVoiceEvent]:
    events: list[RealtimeVoiceEvent] = []

    async def read() -> None:
        async for event in connection.events():
            events.append(event)
            if len(events) == count:
                return

    await asyncio.wait_for(read(), timeout=2)
    return events


async def settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0.005)


def run(scenario: Callable[[], Any]) -> None:
    asyncio.run(asyncio.wait_for(scenario(), timeout=10))


# --- 開連線與設定 ---


def test_connect_uses_the_api_host_model_and_key() -> None:
    async def scenario() -> None:
        connector = FakeConnector()
        await provider(connector).connect(config())
        url, headers = connector.calls[0]
        assert url == (
            "wss://ws-test.ap-southeast-1.example.invalid/api-ws/v1/realtime"
            "?model=qwen-audio-3.1-realtime-flash"
        )
        assert headers == {"Authorization": "Bearer test-key"}

    run(scenario)


@pytest.mark.parametrize(
    "api_host",
    [
        "https://ws-test.ap-southeast-1.example.invalid",
        "wss://ws-test.ap-southeast-1.example.invalid/api-ws/v1/realtime",
        "ws-test.ap-southeast-1.example.invalid/",
    ],
)
def test_api_host_may_be_pasted_with_scheme_or_path(api_host: str) -> None:
    async def scenario() -> None:
        connector = FakeConnector()
        await provider(connector, api_host=api_host).connect(config())
        assert connector.calls[0][0].startswith(
            "wss://ws-test.ap-southeast-1.example.invalid/api-ws/v1/realtime?model="
        )

    run(scenario)


def test_session_settings_for_auto_turn_taking() -> None:
    async def scenario() -> None:
        _, upstream = await connect()
        assert upstream.sent_types() == ["session.update"]
        session = upstream.sent[0]["session"]
        assert session["instructions"] == "你是主持人"
        assert session["modalities"] == ["text", "audio"]
        assert session["input_audio_format"] == "pcm"
        assert session["output_audio_format"] == "pcm"
        assert session["input_audio_transcription"] == {"language": "zh"}
        assert session["max_history_turns"] == 50
        # 自動接話用 smart_turn_v2、靈敏度 0.5；不用 server_vad
        assert session["turn_detection"] == {"type": "smart_turn_v2", "threshold": 0.5}
        assert session["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "lookup_rules",
                    "description": "查規則",
                    "parameters": TOOL.parameters,
                },
            }
        ]

    run(scenario)


def test_push_to_talk_turns_automatic_turn_taking_off() -> None:
    async def scenario() -> None:
        _, upstream = await connect(turn_taking_mode="push_to_talk", turn_sensitivity=None)
        session = upstream.sent[0]["session"]
        assert "turn_detection" in session
        assert session["turn_detection"] is None

    run(scenario)


@pytest.mark.parametrize(
    "voice, expected", [("male", "xunanchuan_v3.1"), ("female", "longyuan_v3.1")]
)
def test_voice_codes_map_to_vendor_voices(voice: str, expected: str) -> None:
    async def scenario() -> None:
        _, upstream = await connect(voice=voice)
        assert upstream.sent[0]["session"]["voice"] == expected

    run(scenario)


def test_unknown_voice_code_is_rejected_before_connecting() -> None:
    async def scenario() -> None:
        connector = FakeConnector()
        with pytest.raises(ValueError):
            await provider(connector).connect(config(voice="robot"))
        assert connector.calls == []

    run(scenario)


# --- 錯誤轉換 ---


@pytest.mark.parametrize(
    "error", [OSError("連不上"), TimeoutError(), RealtimeVoiceUnavailable("握手失敗 HTTP 401")]
)
def test_connect_failure_becomes_unavailable(error: Exception) -> None:
    async def scenario() -> None:
        with pytest.raises(RealtimeVoiceUnavailable):
            await provider(FakeConnector(error=error)).connect(config())

    run(scenario)


def test_session_settings_rejected_becomes_unavailable_and_closes() -> None:
    async def scenario() -> None:
        upstream = FakeUpstream(ack_session=False)
        upstream.reply_to(
            "session.update",
            {"type": "error", "error": {"code": "invalid_value", "message": "bad voice"}},
        )
        with pytest.raises(RealtimeVoiceUnavailable) as exc:
            await provider(FakeConnector(upstream)).connect(config())
        assert "bad voice" in str(exc.value)
        assert upstream.closed is True

    run(scenario)


def test_no_answer_to_session_settings_becomes_unavailable() -> None:
    async def scenario() -> None:
        upstream = FakeUpstream(ack_session=False)
        with pytest.raises(RealtimeVoiceUnavailable):
            await provider(FakeConnector(upstream), session_timeout=0.05).connect(config())
        assert upstream.closed is True

    run(scenario)


def test_key_never_appears_in_error_messages() -> None:
    async def scenario() -> None:
        with pytest.raises(RealtimeVoiceUnavailable) as exc:
            await provider(FakeConnector(error=OSError("x")), api_key="super-secret").connect(
                config()
            )
        assert "super-secret" not in str(exc.value)

    run(scenario)


def test_connection_dropped_by_the_server_becomes_connection_lost() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.drop(code=1007, reason="no response was generated for 180 seconds")
        events = [event async for event in connection.events()]
        assert len(events) == 1
        assert isinstance(events[0], ConnectionLost)
        assert "1007" in events[0].reason

    run(scenario)


def test_closing_ourselves_ends_events_without_connection_lost() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        await connection.close()
        await connection.close()
        assert upstream.closed is True
        assert [event async for event in connection.events()] == []

    run(scenario)


# --- 事件轉換 ---


def test_host_speech_becomes_utterance_start_audio_and_end_with_usage() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            wire.response_created("resp_1"),
            {"type": "response.output_item.added", "response_id": "resp_1", "item": {}},
            wire.audio_delta("resp_1", b"\x01\x02"),
            wire.audio_delta("resp_1", b"\x03\x04"),
            {"type": "response.audio_transcript.done", "response_id": "resp_1", "transcript": "好"},
            wire.response_done("resp_1"),
        )
        events = await collect(connection, 4)
        assert events == [
            HostUtteranceStarted(utterance_id="resp_1"),
            HostAudio(utterance_id="resp_1", data=b"\x01\x02"),
            HostAudio(utterance_id="resp_1", data=b"\x03\x04"),
            HostUtteranceEnded(
                utterance_id="resp_1",
                cancelled=False,
                usage={"total_tokens": 496, "input_tokens": 409, "output_tokens": 87},
            ),
        ]

    run(scenario)


def test_cancelled_response_ends_the_utterance_as_cancelled() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            wire.response_created("resp_1"),
            wire.audio_delta("resp_1", b"\x01\x02"),
            wire.response_done("resp_1", status="cancelled", reason="turn_detected"),
        )
        events = await collect(connection, 3)
        assert isinstance(events[2], HostUtteranceEnded)
        assert events[2].cancelled is True

    run(scenario)


def test_response_without_audio_is_not_an_utterance() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            wire.committed("item_u1"),
            wire.response_created("resp_1"),
            wire.function_call("resp_1", "call_1", "no_reply", "{}"),
            wire.response_done("resp_1"),
            wire.speech_started("item_u2"),
        )
        events = await collect(connection, 2)
        assert events == [
            ToolRequested(call_id="call_1", name="no_reply", arguments={}, speech_id="item_u1"),
            PlayerSpeechStarted(),
        ]

    run(scenario)


def test_player_speech_and_transcripts() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            wire.speech_started("item_u1"),
            wire.transcript_delta("item_u1", "下一", "步"),
            wire.speech_stopped("item_u1"),
            wire.committed("item_u1"),
            wire.transcript_completed("item_u1", "下一步。"),
        )
        events = await collect(connection, 3)
        assert events == [
            PlayerSpeechStarted(),
            # 片段：已確定的前半加上還沒確定的尾巴
            PlayerTranscript(speech_id="item_u1", text="下一步", is_final=False),
            PlayerTranscript(speech_id="item_u1", text="下一步。", is_final=True),
        ]

    run(scenario)


def test_speech_judged_not_for_the_host() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            wire.speech_started("item_u1"),
            wire.transcript_delta("item_u1", "", "等一下", ambient=True),
            wire.speech_stopped("item_u1", reason="turn_invalid"),
            wire.transcript_completed("item_u1", "等一下。", ambient=True),
        )
        events = await collect(connection, 4)
        assert events == [
            PlayerSpeechStarted(),
            # 被當成環境音的話也有辨識文字，後端才看得到「等一下」這種語音指令
            PlayerTranscript(speech_id="item_u1", text="等一下", is_final=False),
            SpeechNotAddressed(speech_id="item_u1"),
            PlayerTranscript(speech_id="item_u1", text="等一下。", is_final=True),
        ]

    run(scenario)


def test_empty_transcripts_are_skipped() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            wire.transcript_delta("item_u1", "", ""),
            wire.transcript_completed("item_u1", ""),
            wire.speech_started("item_u2"),
        )
        assert await collect(connection, 1) == [PlayerSpeechStarted()]

    run(scenario)


def test_tool_request_carries_the_sentence_that_triggered_it() -> None:
    """工具請求的事件本身沒有帶是哪一句話；用事件的順序對出來（ticket 08 第 5 點）。"""

    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            wire.speech_started("item_u1"),
            wire.speech_stopped("item_u1"),
            wire.committed("item_u1"),
            wire.response_created("resp_1"),
            wire.function_call("resp_1", "call_1", "lookup_rules", '{"question": "幾個人？"}'),
            wire.response_done("resp_1"),
            # 下一句話
            wire.speech_started("item_u2"),
            wire.speech_stopped("item_u2"),
            wire.committed("item_u2"),
            wire.response_created("resp_2"),
            wire.function_call("resp_2", "call_2", "next_step", "{}"),
        )
        events = await collect(connection, 4)
        tools = [event for event in events if isinstance(event, ToolRequested)]
        assert tools == [
            ToolRequested(
                call_id="call_1",
                name="lookup_rules",
                arguments={"question": "幾個人？"},
                speech_id="item_u1",
            ),
            ToolRequested(call_id="call_2", name="next_step", arguments={}, speech_id="item_u2"),
        ]

    run(scenario)


def test_tool_request_in_a_response_we_asked_for_has_no_sentence() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(wire.committed("item_u1"))
        upstream.reply_to("response.create", wire.response_created("resp_ours"))
        await connection.request_speech("請說開場")
        upstream.feed(wire.function_call("resp_ours", "call_9", "lookup_rules", "{}"))
        events = await collect(connection, 1)
        assert events == [
            ToolRequested(call_id="call_9", name="lookup_rules", arguments={}, speech_id=None)
        ]

    run(scenario)


def test_bad_tool_arguments_become_an_empty_dict() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            wire.response_created("resp_1"),
            wire.function_call("resp_1", "call_1", "lookup_rules", "{不是 JSON"),
        )
        events = await collect(connection, 1)
        assert isinstance(events[0], ToolRequested)
        assert events[0].arguments == {}

    run(scenario)


def test_unknown_events_are_ignored() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            {"type": "some.future.event", "x": 1},
            {"type": "response.content_part.added", "response_id": "r"},
            wire.speech_started("item_u1"),
        )
        assert await collect(connection, 1) == [PlayerSpeechStarted()]

    run(scenario)


# --- 動作 ---


def test_send_audio_is_base64_appended() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        await connection.send_audio(b"\x01\x02\x03\x04")
        assert upstream.sent[-1] == {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(b"\x01\x02\x03\x04").decode(),
        }

    run(scenario)


def test_system_message_is_added_without_asking_for_a_response() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        await connection.send_system_message("現況：第 2 回合")
        assert upstream.sent_types() == ["session.update", "conversation.item.create"]
        item = upstream.sent[-1]["item"]
        assert item["type"] == "message"
        assert item["role"] == "system"
        assert item["content"] == [{"type": "input_text", "text": "現況：第 2 回合"}]

    run(scenario)


def test_request_speech_adds_the_text_and_asks_for_a_response() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.reply_to("response.create", wire.response_created("resp_1"))

        result = await connection.request_speech("請照唸：歡迎")

        assert result == SpeechRequestResult(accepted=True)
        assert upstream.sent_types()[-2:] == ["conversation.item.create", "response.create"]
        item = upstream.sent[-2]["item"]
        assert item["type"] == "message"
        assert "請照唸：歡迎" in item["content"][0]["text"]

    run(scenario)


def test_request_speech_without_any_answer_counts_as_accepted() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        result = await connection.request_speech("請照唸：歡迎")
        assert result.accepted is True

    run(scenario)


def test_request_speech_is_rejected_locally_while_the_player_is_speaking() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(wire.speech_started("item_u1"))
        await collect(connection, 1)

        result = await connection.request_speech("階段 1 的規則要點")

        assert result == SpeechRequestResult(accepted=False, rejected_reason="player_speaking")
        # 還沒送出去，對話裡不會多一則沒人回的訊息
        assert upstream.sent_types() == ["session.update"]

        upstream.feed(wire.speech_stopped("item_u1"))
        await settle()
        upstream.reply_to("response.create", wire.response_created("resp_1"))
        assert (await connection.request_speech("階段 1 的規則要點")).accepted is True

    run(scenario)


def test_request_speech_is_rejected_locally_while_a_response_is_in_progress() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(wire.response_created("resp_1"), wire.audio_delta("resp_1", b"\x00\x00"))
        await collect(connection, 2)

        result = await connection.request_speech("階段 1 的規則要點")

        assert result == SpeechRequestResult(accepted=False, rejected_reason="response_in_progress")
        assert upstream.sent_types() == ["session.update"]

        upstream.feed(wire.response_done("resp_1"))
        await settle()
        upstream.reply_to("response.create", wire.response_created("resp_2"))
        assert (await connection.request_speech("階段 1 的規則要點")).accepted is True

    run(scenario)


@pytest.mark.parametrize(
    "message, reason",
    [
        ("Cannot create response while user is speaking.", "player_speaking"),
        (
            "Cannot create response while another response is in progress.",
            "response_in_progress",
        ),
    ],
)
def test_request_speech_rejected_by_the_server_reports_the_reason(
    message: str, reason: str
) -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.reply_to("response.create", wire.create_rejected(message))
        result = await connection.request_speech("階段 1 的規則要點")
        assert result == SpeechRequestResult(accepted=False, rejected_reason=reason)

    run(scenario)


def test_tool_result_with_respond_asks_for_a_response() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.reply_to("response.create", wire.response_created("resp_2"))
        await connection.send_tool_result("call_1", "片段", respond=True)
        await settle()
        assert upstream.sent_types()[-2:] == ["conversation.item.create", "response.create"]
        assert upstream.sent[-2]["item"] == {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "片段",
        }

    run(scenario)


def test_tool_result_without_respond_only_records_the_output() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        await connection.send_tool_result("call_1", "", respond=False)
        await settle()
        assert upstream.sent_types() == ["session.update", "conversation.item.create"]
        assert upstream.sent[-1]["item"]["type"] == "function_call_output"

    run(scenario)


def test_tool_result_waits_for_the_calling_response_to_finish() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(
            wire.committed("item_u1"),
            wire.response_created("resp_1"),
            wire.function_call("resp_1", "call_1", "lookup_rules", "{}"),
        )
        await collect(connection, 1)

        await connection.send_tool_result("call_1", "片段", respond=True)
        await settle()
        # 呼叫工具的那個回答還沒結束：先放工具結果，「請回答」等它結束再送
        assert upstream.sent_types().count("response.create") == 0
        assert upstream.sent[-1]["item"]["type"] == "function_call_output"

        upstream.reply_to("response.create", wire.response_created("resp_2"))
        upstream.feed(wire.response_done("resp_1"))
        await settle()
        assert upstream.sent_types().count("response.create") == 1

    run(scenario)


def test_tool_result_response_is_resent_when_the_server_rejects_it() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.reply_to(
            "response.create",
            wire.create_rejected("Cannot create response while user is speaking."),
        )
        await connection.send_tool_result("call_1", "片段", respond=True)
        await settle()
        assert upstream.sent_types().count("response.create") >= 1

        upstream.reply_to("response.create", wire.response_created("resp_2"))
        await asyncio.sleep(0.1)
        count = upstream.sent_types().count("response.create")
        await asyncio.sleep(0.1)
        # 送出去之後就不再重送；工具結果只放一份
        assert upstream.sent_types().count("response.create") == count
        assert upstream.sent_types().count("conversation.item.create") == 1

    run(scenario)


def test_cancel_response_only_when_one_is_in_progress() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        await connection.cancel_response()
        # 沒有回答在進行時不送，不然對方會回錯誤
        assert "response.cancel" not in upstream.sent_types()

        upstream.feed(wire.response_created("resp_1"), wire.audio_delta("resp_1", b"\x00\x00"))
        await collect(connection, 2)
        await connection.cancel_response()
        assert upstream.sent_types()[-1] == "response.cancel"

    run(scenario)


def test_cancel_response_also_drops_a_tool_response_that_is_still_waiting() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.feed(wire.speech_started("item_u1"))
        await collect(connection, 1)
        await connection.send_tool_result("call_1", "片段", respond=True)
        await settle()
        await connection.cancel_response()
        upstream.feed(wire.speech_stopped("item_u1"))
        await asyncio.sleep(0.1)
        assert upstream.sent_types().count("response.create") == 0

    run(scenario)


def test_push_to_talk_press_clears_and_release_commits_and_asks_for_a_response() -> None:
    async def scenario() -> None:
        connection, upstream = await connect(turn_taking_mode="push_to_talk")
        await connection.press_talk()
        await connection.send_audio(b"\x01\x02")
        await connection.release_talk()
        await settle()
        assert upstream.sent_types()[1:] == [
            "input_audio_buffer.clear",
            "input_audio_buffer.append",
            "input_audio_buffer.commit",
            "response.create",
        ]

    run(scenario)


def test_actions_after_the_connection_dropped_raise_unavailable() -> None:
    async def scenario() -> None:
        connection, upstream = await connect()
        upstream.drop()
        await collect(connection, 1)
        with pytest.raises(RealtimeVoiceUnavailable):
            await connection.send_audio(b"\x01\x02")
        with pytest.raises(RealtimeVoiceUnavailable):
            await connection.request_speech("請說")

    run(scenario)


# --- 工廠與分層 ---


def test_factory_builds_the_cloud_provider(make_settings: Callable[..., Settings]) -> None:
    settings = make_settings(
        host_realtime_provider="cloud",
        host_realtime_api_key="test-key",
        host_realtime_api_host="ws-test.example.invalid",
    )
    assert isinstance(get_realtime_voice_provider(settings), CloudRealtimeVoiceProvider)


def test_integration_layer_still_does_not_import_domains() -> None:
    for path in Path(package.__file__).parent.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith("app.domains"), f"{path.name} import 了 {name}"
