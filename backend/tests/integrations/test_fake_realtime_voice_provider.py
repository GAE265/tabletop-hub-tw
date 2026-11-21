"""FakeRealtimeVoiceProvider（host spec §13.3）。

照劇本送出「呼叫端會收到的事」的每一種事件；記下呼叫端做過的每一個動作；
「請主持人開口」可以設定成被拒（兩種原因）。
"""

import ast
import asyncio
from pathlib import Path

import pytest

import app.integrations.realtime_voice as package
from app.integrations.realtime_voice import (
    ConnectionLost,
    FakeRealtimeVoiceProvider,
    HostAudio,
    HostUtteranceEnded,
    HostUtteranceStarted,
    PlayerSpeechStarted,
    PlayerTranscript,
    RealtimeVoiceConfig,
    RealtimeVoiceConnection,
    RealtimeVoiceEvent,
    RealtimeVoiceProvider,
    RealtimeVoiceUnavailable,
    SpeechNotAddressed,
    SpeechRequestResult,
    ToolRequested,
    VoiceToolSpec,
)

TOOL = VoiceToolSpec(
    name="lookup_rules",
    description="查規則",
    parameters={
        "type": "object",
        "properties": {"question": {"type": "string"}},
        "required": ["question"],
    },
)
CONFIG = RealtimeVoiceConfig(
    instructions="你是主持人",
    tools=[TOOL],
    voice="male",
    turn_taking_mode="auto",
    history_turns=50,
    turn_sensitivity=0.5,
)
EVERY_EVENT: list[RealtimeVoiceEvent] = [
    HostUtteranceStarted(utterance_id="u1"),
    HostAudio(utterance_id="u1", data=b"\x01\x02"),
    HostUtteranceEnded(utterance_id="u1", cancelled=False, usage={"total_tokens": 12}),
    HostUtteranceEnded(utterance_id="u2", cancelled=True, usage=None),
    PlayerSpeechStarted(),
    PlayerTranscript(speech_id="s1", text="下一", is_final=False),
    PlayerTranscript(speech_id="s1", text="下一步", is_final=True),
    SpeechNotAddressed(speech_id="s2"),
    ToolRequested(call_id="c1", name="lookup_rules", arguments={"question": "?"}, speech_id="s3"),
    ConnectionLost(reason="idle_timeout"),
]


def test_is_a_provider() -> None:
    assert isinstance(FakeRealtimeVoiceProvider(), RealtimeVoiceProvider)


def test_connect_records_config_and_returns_connection() -> None:
    async def scenario() -> None:
        fake = FakeRealtimeVoiceProvider()
        connection = await fake.connect(CONFIG)
        assert isinstance(connection, RealtimeVoiceConnection)
        assert fake.configs == [CONFIG]
        assert fake.connections == [connection]
        assert fake.last_connection is connection

    asyncio.run(scenario())


def test_emits_every_kind_of_event_in_order() -> None:
    async def scenario() -> None:
        fake = FakeRealtimeVoiceProvider()
        connection = await fake.connect(CONFIG)
        for event in EVERY_EVENT:
            fake.last_connection.emit(event)
        received = []
        async for event in connection.events():
            received.append(event)
            if len(received) == len(EVERY_EVENT):
                break
        assert received == EVERY_EVENT

    asyncio.run(scenario())


def test_events_end_after_close() -> None:
    async def scenario() -> None:
        fake = FakeRealtimeVoiceProvider()
        connection = await fake.connect(CONFIG)
        fake.last_connection.emit(PlayerSpeechStarted())
        await connection.close()
        received = [event async for event in connection.events()]
        assert received == [PlayerSpeechStarted()]
        assert fake.last_connection.closed is True

    asyncio.run(scenario())


def test_records_every_action() -> None:
    async def scenario() -> None:
        fake = FakeRealtimeVoiceProvider()
        connection = await fake.connect(CONFIG)
        await connection.send_audio(b"\x00\x01")
        await connection.press_talk()
        await connection.release_talk()
        await connection.send_system_message("現在是第 1 回合階段 2")
        result = await connection.request_speech("請說開場")
        await connection.send_tool_result("c1", "片段", respond=True)
        await connection.send_tool_result("c2", "", respond=False)
        await connection.cancel_response()
        await connection.close()

        assert result == SpeechRequestResult(accepted=True, rejected_reason=None)
        assert fake.last_connection.actions == [
            ("send_audio", b"\x00\x01"),
            ("press_talk",),
            ("release_talk",),
            ("send_system_message", "現在是第 1 回合階段 2"),
            ("request_speech", "請說開場"),
            ("send_tool_result", "c1", "片段", True),
            ("send_tool_result", "c2", "", False),
            ("cancel_response",),
            ("close",),
        ]
        assert fake.last_connection.speech_requests == ["請說開場"]

    asyncio.run(scenario())


@pytest.mark.parametrize("reason", ["player_speaking", "response_in_progress"])
def test_request_speech_can_be_rejected_with_reason(reason: str) -> None:
    async def scenario() -> None:
        fake = FakeRealtimeVoiceProvider()
        connection = await fake.connect(CONFIG)
        fake.last_connection.reject_speech(reason, times=2)

        first = await connection.request_speech("階段 1 的規則要點")
        second = await connection.request_speech("階段 1 的規則要點")
        third = await connection.request_speech("階段 1 的規則要點")

        assert first == SpeechRequestResult(accepted=False, rejected_reason=reason)
        assert second == SpeechRequestResult(accepted=False, rejected_reason=reason)
        assert third == SpeechRequestResult(accepted=True, rejected_reason=None)
        # 被拒的請求也記在 actions，但只有送出的才算進 speech_requests
        assert fake.last_connection.actions.count(("request_speech", "階段 1 的規則要點")) == 3
        assert fake.last_connection.speech_requests == ["階段 1 的規則要點"]

    asyncio.run(scenario())


def test_connect_can_fail() -> None:
    async def scenario() -> None:
        fake = FakeRealtimeVoiceProvider()
        fake.fail_connect(times=2)
        for _ in range(2):
            with pytest.raises(RealtimeVoiceUnavailable):
                await fake.connect(CONFIG)
        connection = await fake.connect(CONFIG)
        assert fake.connections == [connection]
        assert fake.connect_attempts == 3

    asyncio.run(scenario())


def test_integration_layer_does_not_import_domains() -> None:
    """整合層不知道任何 domain 的存在（AGENTS.md §4.2）。"""
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
