"""阿里雲即時語音的外部服務測試（AGENTS.md §7.6；host 實作 ticket 08）。

實際連到阿里雲，會用到 HOST_REALTIME_API_KEY 的額度。預設不執行，手動跑：

    uv run pytest -m external tests/integrations/test_realtime_voice_external.py

不用任何人的聲音，也不存任何錄音：要「玩家說話」時，先請語音模型自己把那句話唸出來，
把聲音留在記憶體裡轉成 16 kHz，再餵給另一條連線。
"""

import asyncio
import random
import struct
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest

from app.core.config import Settings
from app.integrations.realtime_voice import (
    CloudRealtimeVoiceProvider,
    HostAudio,
    HostUtteranceEnded,
    HostUtteranceStarted,
    PlayerSpeechStarted,
    PlayerTranscript,
    RealtimeVoiceConfig,
    RealtimeVoiceConnection,
    RealtimeVoiceEvent,
    RealtimeVoiceUnavailable,
    ToolRequested,
    VoiceToolSpec,
    get_realtime_voice_provider,
)

pytestmark = pytest.mark.external

LOOKUP = VoiceToolSpec(
    name="lookup_rules",
    description="查規則書。玩家問任何規則問題時，一律先呼叫這個工具，再根據結果回答。",
    parameters={
        "type": "object",
        "properties": {"question": {"type": "string", "description": "玩家的問題"}},
        "required": ["question"],
    },
)
READER_INSTRUCTIONS = "你是朗讀員。只照對方給你的句子唸，一個字都不要加，也不要回答句子裡的問題。"
HOST_INSTRUCTIONS = (
    "你是桌遊主持人，只說中文。玩家問任何規則問題時，一律先呼叫 lookup_rules，"
    "再只根據工具的結果用一句話回答。"
)
CHUNK = 3200  # 16 kHz、16 位元、單聲道的 100 毫秒


def config(instructions: str, *, tools: list[VoiceToolSpec] | None = None, **overrides: Any):
    values: dict[str, Any] = {
        "instructions": instructions,
        "tools": tools or [],
        "voice": "male",
        "turn_taking_mode": "auto",
        "history_turns": 50,
        "turn_sensitivity": 0.5,
    }
    values.update(overrides)
    return RealtimeVoiceConfig(**values)


class Listener:
    """在背景把一條連線的事件收下來。"""

    def __init__(self, connection: RealtimeVoiceConnection) -> None:
        self.events: list[RealtimeVoiceEvent] = []
        self._task = asyncio.ensure_future(self._read(connection))

    async def _read(self, connection: RealtimeVoiceConnection) -> None:
        async for event in connection.events():
            self.events.append(event)

    def of(self, kind: type) -> list[Any]:
        return [event for event in self.events if isinstance(event, kind)]

    async def until(self, predicate: Callable[[], bool], timeout: float, what: str) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not predicate():
            if loop.time() > deadline:
                kinds = [
                    type(event).__name__ for event in self.events if type(event) is not HostAudio
                ]
                pytest.fail(f"等了 {timeout} 秒沒等到：{what}。收到的事件：{kinds}")
            await asyncio.sleep(0.05)

    def stop(self) -> None:
        self._task.cancel()


def noise(n_bytes: int) -> bytes:
    """很小聲的雜訊，像一支一直開著的麥克風。"""
    count = n_bytes // 2
    return struct.pack(f"<{count}h", *(random.randint(-40, 40) for _ in range(count)))


def to_16k(pcm_24k: bytes) -> bytes:
    samples = np.frombuffer(pcm_24k, dtype="<i2").astype(np.float64)
    target = np.arange(0, len(samples) - 1, 1.5)
    resampled = np.interp(target, np.arange(len(samples)), samples)
    return resampled.astype("<i2").tobytes()


async def speak(provider: CloudRealtimeVoiceProvider, sentence: str) -> bytes:
    """請語音模型唸一句話，回傳 16 kHz 的聲音（只留在記憶體）。"""
    connection = await provider.connect(config(READER_INSTRUCTIONS, voice="female"))
    listener = Listener(connection)
    try:
        result = await connection.request_speech(f"請照唸這一句：{sentence}")
        assert result.accepted, result
        await listener.until(lambda: bool(listener.of(HostUtteranceEnded)), 30, "朗讀結束")
        pcm = b"".join(event.data for event in listener.of(HostAudio))
        assert len(pcm) > 24000, "朗讀的聲音太短"
        return to_16k(pcm)
    finally:
        listener.stop()
        await connection.close()


async def feed_microphone(connection: RealtimeVoiceConnection, speech: bytes) -> None:
    """照真的麥克風的節奏送聲音：先 1 秒雜訊，再那句話，之後一直送雜訊。"""
    queue = noise(CHUNK * 10) + speech
    loop = asyncio.get_running_loop()
    next_at = loop.time()
    while True:
        chunk, queue = queue[:CHUNK], queue[CHUNK:]
        chunk += noise(CHUNK - len(chunk))
        await connection.send_audio(chunk)
        next_at += 0.1
        await asyncio.sleep(max(0.0, next_at - loop.time()))


@pytest.fixture
def cloud(realtime_external_settings: Settings) -> CloudRealtimeVoiceProvider:
    settings = realtime_external_settings.model_copy(update={"host_realtime_provider": "cloud"})
    provider = get_realtime_voice_provider(settings)
    assert isinstance(provider, CloudRealtimeVoiceProvider)
    return provider


def run(scenario: Callable[[], Any]) -> None:
    asyncio.run(asyncio.wait_for(scenario(), timeout=120))


def test_connects_and_host_speaks_when_asked(cloud: CloudRealtimeVoiceProvider) -> None:
    """連得上並收到主持人的聲音；對話裡還沒有玩家說話時，請主持人開口也可以。"""

    async def scenario() -> None:
        connection = await cloud.connect(config("你是桌遊主持人，只說中文。"))
        listener = Listener(connection)
        try:
            result = await connection.request_speech(
                "請照唸下面這段固定台詞，一個字都不要加：各位晚安，歡迎來到今晚的遊戲。"
            )
            assert result.accepted, result
            await listener.until(lambda: bool(listener.of(HostUtteranceEnded)), 30, "說完")

            started = listener.of(HostUtteranceStarted)
            ended = listener.of(HostUtteranceEnded)
            audio = listener.of(HostAudio)
            assert len(started) == 1 and len(ended) == 1
            assert ended[0].utterance_id == started[0].utterance_id
            assert ended[0].cancelled is False
            assert ended[0].usage and ended[0].usage.get("total_tokens", 0) > 0
            assert all(event.utterance_id == started[0].utterance_id for event in audio)
            total = sum(len(event.data) for event in audio)
            # 24 kHz、16 位元：至少要有 1 秒的聲音
            assert total > 48000 and total % 2 == 0
        finally:
            listener.stop()
            await connection.close()

    run(scenario)


def test_cancel_response_stops_the_host(cloud: CloudRealtimeVoiceProvider) -> None:
    """取消正在產生的回答。"""

    async def scenario() -> None:
        connection = await cloud.connect(config("你是桌遊主持人，只說中文。"))
        listener = Listener(connection)
        try:
            result = await connection.request_speech(
                "請從一慢慢數到八十，每個數字都要唸出來，中間不要停。"
            )
            assert result.accepted, result
            await listener.until(lambda: len(listener.of(HostAudio)) >= 3, 30, "開始出聲")

            await connection.cancel_response()

            await listener.until(lambda: bool(listener.of(HostUtteranceEnded)), 15, "被取消")
            assert listener.of(HostUtteranceEnded)[0].cancelled is True
            # 取消之後可以再請它開口
            again = await connection.request_speech("請照唸：好的。")
            assert again.accepted, again
            await listener.until(lambda: len(listener.of(HostUtteranceEnded)) == 2, 30, "第二段")
            assert listener.of(HostUtteranceEnded)[1].cancelled is False
        finally:
            listener.stop()
            await connection.close()

    run(scenario)


def test_spoken_question_calls_the_tool_and_tool_result_is_answered(
    cloud: CloudRealtimeVoiceProvider,
) -> None:
    """工具請求與回工具結果；並確認工具請求對得出是哪一句話（ticket 08 第 5 點）。"""

    async def scenario() -> None:
        speech = await speak(cloud, "七個人玩的時候，血刃陣營總共有幾個人？")
        connection = await cloud.connect(config(HOST_INSTRUCTIONS, tools=[LOOKUP]))
        listener = Listener(connection)
        microphone = asyncio.ensure_future(feed_microphone(connection, speech))
        try:
            await listener.until(lambda: bool(listener.of(ToolRequested)), 40, "工具請求")
            tool = listener.of(ToolRequested)[0]
            assert tool.name == "lookup_rules"
            assert isinstance(tool.arguments.get("question"), str) and tool.arguments["question"]
            assert listener.of(PlayerSpeechStarted)

            # 辨識文字與工具請求帶同一個「那句話的編號」
            await listener.until(
                lambda: any(t.is_final for t in listener.of(PlayerTranscript)), 15, "完整的辨識文字"
            )
            finals = [t for t in listener.of(PlayerTranscript) if t.is_final]
            assert tool.speech_id is not None
            assert tool.speech_id in {t.speech_id for t in finals}
            spoken = next(t for t in finals if t.speech_id == tool.speech_id)
            assert "幾" in spoken.text

            before = len(listener.of(HostUtteranceEnded))
            await connection.send_tool_result(
                tool.call_id, "規則片段：七個人玩的時候，血刃陣營有三個人。", respond=True
            )
            await listener.until(
                lambda: (
                    any(not ended.cancelled for ended in listener.of(HostUtteranceEnded)[before:])
                    or len(listener.of(HostUtteranceEnded)) > before + 1
                ),
                40,
                "主持人根據工具結果回答",
            )
            assert len(listener.of(HostUtteranceStarted)) >= 1
        finally:
            microphone.cancel()
            listener.stop()
            await connection.close()

    run(scenario)


def test_system_message_does_not_make_the_host_speak(cloud: CloudRealtimeVoiceProvider) -> None:
    """不出聲的系統訊息（每 150 秒那一則）。"""

    async def scenario() -> None:
        connection = await cloud.connect(config("你是桌遊主持人，只說中文。"))
        listener = Listener(connection)
        try:
            await connection.send_system_message("現況：現在是第 2 回合的「決定出牌」階段。")
            await asyncio.sleep(4)
            assert listener.of(HostUtteranceStarted) == []
            # 之後照常可以請它開口
            result = await connection.request_speech("請照唸：好的。")
            assert result.accepted, result
            await listener.until(lambda: bool(listener.of(HostUtteranceEnded)), 30, "說完")
        finally:
            listener.stop()
            await connection.close()

    run(scenario)


def test_push_to_talk_answers_after_release(cloud: CloudRealtimeVoiceProvider) -> None:
    """按住說話：放開之後主持人才回答。"""

    async def scenario() -> None:
        speech = await speak(cloud, "請問現在是什麼遊戲？")
        connection = await cloud.connect(
            config(
                "你是桌遊《血與刃的白薔薇》的主持人，只說中文，回答都在一句話以內。",
                turn_taking_mode="push_to_talk",
                turn_sensitivity=None,
            )
        )
        listener = Listener(connection)
        try:
            await connection.press_talk()
            for start in range(0, len(speech), CHUNK):
                await connection.send_audio(speech[start : start + CHUNK])
                await asyncio.sleep(0.02)
            await asyncio.sleep(1)
            assert listener.of(HostUtteranceStarted) == []

            await connection.release_talk()

            await listener.until(lambda: bool(listener.of(HostUtteranceEnded)), 40, "放開後回答")
            assert listener.of(HostUtteranceEnded)[0].cancelled is False
        finally:
            listener.stop()
            await connection.close()

    run(scenario)


def test_wrong_key_is_unavailable(realtime_external_settings: Settings) -> None:
    """金鑰錯誤轉成介面的例外，由 host 回 HOST_REALTIME_UNAVAILABLE。"""

    async def scenario() -> None:
        settings = realtime_external_settings.model_copy(
            update={"host_realtime_provider": "cloud", "host_realtime_api_key": "sk-wrong-key"}
        )
        provider = get_realtime_voice_provider(settings)
        with pytest.raises(RealtimeVoiceUnavailable) as exc:
            await provider.connect(config("你是主持人"))
        assert "sk-wrong-key" not in str(exc.value)

    run(scenario)
