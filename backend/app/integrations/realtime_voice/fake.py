"""測試與開發用的假實作：照劇本送出事件，並記下呼叫端做過的每一個動作。"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.integrations.realtime_voice.base import RealtimeVoiceConnection, RealtimeVoiceProvider
from app.integrations.realtime_voice.errors import RealtimeVoiceUnavailable
from app.integrations.realtime_voice.types import (
    RealtimeVoiceConfig,
    RealtimeVoiceEvent,
    SpeechRejectedReason,
    SpeechRequestResult,
)

_CLOSED = object()


class FakeRealtimeVoiceConnection(RealtimeVoiceConnection):
    def __init__(self, config: RealtimeVoiceConfig) -> None:
        self.config = config
        # 每個動作一個 tuple：(動作名稱, *參數)
        self.actions: list[tuple[Any, ...]] = []
        # 真的送出（沒被拒）的「請主持人開口」
        self.speech_requests: list[str] = []
        self.closed = False
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._rejections: list[SpeechRejectedReason] = []
        self._reject_always: SpeechRejectedReason | None = None

    # --- 測試用：寫劇本 ---

    def emit(self, event: RealtimeVoiceEvent) -> None:
        """讓呼叫端收到一個事件。"""
        self._queue.put_nowait(event)

    def reject_speech(self, reason: SpeechRejectedReason, times: int | None = 1) -> None:
        """接下來 times 次「請主持人開口」都被拒；times 為 None 代表一直被拒。"""
        if times is None:
            self._reject_always = reason
        else:
            self._rejections.extend([reason] * times)

    def accept_speech(self) -> None:
        """取消 reject_speech 的設定。"""
        self._rejections.clear()
        self._reject_always = None

    def action_names(self) -> list[str]:
        return [action[0] for action in self.actions]

    # --- 介面 ---

    async def send_audio(self, data: bytes) -> None:
        self.actions.append(("send_audio", data))

    async def press_talk(self) -> None:
        self.actions.append(("press_talk",))

    async def release_talk(self) -> None:
        self.actions.append(("release_talk",))

    async def send_system_message(self, text: str) -> None:
        self.actions.append(("send_system_message", text))

    async def request_speech(self, text: str) -> SpeechRequestResult:
        self.actions.append(("request_speech", text))
        if self._rejections:
            return SpeechRequestResult(accepted=False, rejected_reason=self._rejections.pop(0))
        if self._reject_always is not None:
            return SpeechRequestResult(accepted=False, rejected_reason=self._reject_always)
        self.speech_requests.append(text)
        return SpeechRequestResult(accepted=True)

    async def send_tool_result(self, call_id: str, output: str, *, respond: bool = True) -> None:
        self.actions.append(("send_tool_result", call_id, output, respond))

    async def cancel_response(self) -> None:
        self.actions.append(("cancel_response",))

    async def close(self) -> None:
        self.actions.append(("close",))
        if not self.closed:
            self.closed = True
            self._queue.put_nowait(_CLOSED)

    async def events(self) -> AsyncIterator[RealtimeVoiceEvent]:
        while True:
            item = await self._queue.get()
            if item is _CLOSED:
                # 放回去，讓之後再呼叫 events() 的人也馬上結束
                self._queue.put_nowait(_CLOSED)
                return
            yield item


class FakeRealtimeVoiceProvider(RealtimeVoiceProvider):
    def __init__(self) -> None:
        self.configs: list[RealtimeVoiceConfig] = []
        self.connections: list[FakeRealtimeVoiceConnection] = []
        self.connect_attempts = 0
        self._failures = 0
        self._fail_always = False

    def fail_connect(self, times: int | None = 1) -> None:
        """接下來 times 次 connect 都失敗；times 為 None 代表一直失敗。"""
        if times is None:
            self._fail_always = True
        else:
            self._failures += times

    @property
    def last_connection(self) -> FakeRealtimeVoiceConnection:
        return self.connections[-1]

    async def connect(self, config: RealtimeVoiceConfig) -> RealtimeVoiceConnection:
        self.connect_attempts += 1
        if self._fail_always:
            raise RealtimeVoiceUnavailable("fake：設定成連不上")
        if self._failures > 0:
            self._failures -= 1
            raise RealtimeVoiceUnavailable("fake：設定成連不上")
        connection = FakeRealtimeVoiceConnection(config)
        self.configs.append(config)
        self.connections.append(connection)
        return connection
