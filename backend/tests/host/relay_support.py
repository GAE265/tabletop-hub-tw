"""轉送那一段的測試共用的工具：假的裝置、假時鐘、把 service、圖、假的語音模型接起來的 Rig。

圖跑真的；即時語音、查規則、思考模型都是手寫的 fake（spec §13.1）。
"""

import asyncio
import heapq
import json
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from app.core.auth import CurrentUser
from app.domains.host import content
from app.domains.host.graph import HostEvent, HostGraph
from app.domains.host.relay import HostRelay, Timers
from app.domains.host.service import HostService
from app.integrations.realtime_voice import (
    FakeRealtimeVoiceConnection,
    FakeRealtimeVoiceProvider,
    HostUtteranceEnded,
    HostUtteranceStarted,
    PlayerTranscript,
    RealtimeVoiceEvent,
    ToolRequested,
)
from tests.host.fakes import FakeClock, FakeRulesLookup, FakeThinkingModel

OWNER = CurrentUser(id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), role="player")


def run(scenario: Callable[[], Coroutine[Any, Any, None]]) -> None:
    """專案沒有裝 pytest 的 async 外掛，所以每個測試自己開事件迴圈。"""
    asyncio.run(asyncio.wait_for(scenario(), timeout=20))


class FakeDevice:
    """假的裝置（瀏覽器那一端）：記下後端送來的每一則訊息。"""

    def __init__(self) -> None:
        # JSON 訊息是 dict，聲音是 bytes，照收到的順序
        self.messages: list[dict[str, Any] | bytes] = []
        self.closed = False

    async def send_json(self, message: dict[str, Any]) -> None:
        assert not self.closed, f"連線關掉之後還送訊息：{message}"
        self.messages.append(message)

    async def send_bytes(self, data: bytes) -> None:
        assert not self.closed
        self.messages.append(data)

    async def close(self) -> None:
        self.closed = True

    def json(self, message_type: str | None = None) -> list[dict[str, Any]]:
        found = [m for m in self.messages if isinstance(m, dict)]
        if message_type is not None:
            found = [m for m in found if m["type"] == message_type]
        return found

    def last_state(self) -> dict[str, Any]:
        return self.json("state")[-1]

    def error_codes(self) -> list[str]:
        return [m["error"]["code"] for m in self.json("error")]


class FakeTimers:
    """可以控制的假時鐘：sleep 不真的等，advance 讓時間往前走並叫醒到期的人。"""

    def __init__(self) -> None:
        self.time = 0.0
        self._sleepers: list[tuple[float, int, asyncio.Future[None]]] = []
        self._seq = 0

    def now(self) -> float:
        return self.time

    async def sleep(self, seconds: float) -> None:
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._seq += 1
        heapq.heappush(self._sleepers, (self.time + max(seconds, 0), self._seq, future))
        await future

    def as_timers(self) -> Timers:
        return Timers(now=self.now, sleep=self.sleep)

    async def advance(self, seconds: float, settle: Callable[[], Awaitable[None]]) -> None:
        target = self.time + seconds
        while self._sleepers and self._sleepers[0][0] <= target + 1e-9:
            due, _, future = heapq.heappop(self._sleepers)
            self.time = max(self.time, due)
            if not future.done():
                future.set_result(None)
                await settle()
        self.time = target
        await settle()


class Rig:
    """一場主持加上一支假的裝置。"""

    def __init__(
        self,
        *,
        player_count: int = 7,
        turn_taking_mode: str = "auto",
        voice: str = "male",
        lookup: FakeRulesLookup | None = None,
        thinking: FakeThinkingModel | None = None,
    ) -> None:
        self.clock = FakeClock()
        self.lookup = lookup or FakeRulesLookup()
        self.thinking = thinking or FakeThinkingModel()
        self.graph = HostGraph(rules_lookup=self.lookup, thinking_model=self.thinking)
        self.service = HostService(self.graph, clock=self.clock)
        self.provider = FakeRealtimeVoiceProvider()
        self.timers = FakeTimers()
        view, _ = self.service.open_session(
            OWNER, player_count=player_count, turn_taking_mode=turn_taking_mode, voice=voice
        )
        self.sid = view.id
        self.device = FakeDevice()
        self.relay: HostRelay | None = None
        self._utterance_seq = 0

    # --- 準備 ---

    def advance_to(self, turn_number: int, phase_number: int) -> None:
        """連線之前先把流程推到指定的回合與階段（之後連上就是「重新連線」）。"""
        self.service.handle_event(self.sid, HostEvent.connected())
        presses = 4 + (turn_number - 1) * 3 + (phase_number - 1)
        for _ in range(presses):
            self.service.handle_event(self.sid, HostEvent.command("next"))

    async def connect(self, *, turn_taking_mode: str | None = None) -> FakeDevice:
        """用一張新的通行碼連上一支新的裝置。"""
        _, ticket = self.service.issue_ticket(OWNER, self.sid, turn_taking_mode=turn_taking_mode)
        redeemed = self.service.redeem_ticket(self.sid, ticket.ticket)
        self.device = FakeDevice()
        self.relay = HostRelay(
            service=self.service,
            provider=self.provider,
            session_id=self.sid,
            device=self.device,
            turn_taking_mode=redeemed.turn_taking_mode,
            timers=self.timers.as_timers(),
        )
        await self.relay.start()
        await self.settle()
        return self.device

    # --- 讀 ---

    @property
    def conn(self) -> FakeRealtimeVoiceConnection:
        return self.provider.last_connection

    @property
    def snapshot(self):
        return self.graph.snapshot(str(self.sid))

    def position(self) -> tuple[str, int | None, int | None]:
        snapshot = self.snapshot
        return snapshot.step, snapshot.turn_number, snapshot.phase_number

    def tool_results(self, call_id: str | None = None) -> list[tuple[Any, ...]]:
        found = [a for a in self.conn.actions if a[0] == "send_tool_result"]
        return [a for a in found if call_id is None or a[1] == call_id]

    def count_action(self, name: str) -> int:
        return self.conn.action_names().count(name)

    # --- 動作 ---

    async def settle(self) -> None:
        """等轉送那一段把手上的事做完（圖在另一條執行緒跑，所以要真的等一下）。"""
        assert self.relay is not None
        for _ in range(4):
            await asyncio.sleep(0.005)
            await self.relay.wait_idle()

    async def until(self, predicate: Callable[[], bool], timeout: float = 3.0) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not predicate():
            assert loop.time() < deadline, "等不到預期的狀態"
            await asyncio.sleep(0.005)
        await self.settle()

    async def advance(self, seconds: float) -> None:
        await self.timers.advance(seconds, self.settle)

    async def emit(self, *events: RealtimeVoiceEvent) -> None:
        for event in events:
            self.conn.emit(event)
        await self.settle()

    async def device_sends(self, **message: Any) -> None:
        assert self.relay is not None
        await self.relay.handle_device_text(json.dumps(message))
        await self.settle()

    async def press(self, action: str) -> None:
        await self.device_sends(type="command", action=action)

    async def hears(self, text: str, *, speech_id: str = "s1", final: bool = True) -> None:
        await self.emit(PlayerTranscript(speech_id=speech_id, text=text, is_final=final))

    async def tool(
        self,
        name: str,
        *,
        call_id: str = "c1",
        speech_id: str | None = "s1",
        **arguments: Any,
    ) -> None:
        await self.emit(
            ToolRequested(call_id=call_id, name=name, arguments=arguments, speech_id=speech_id)
        )

    async def host_starts(self) -> str:
        """語音模型開始說它被要求說的那一段。回傳那一段的編號。"""
        self._utterance_seq += 1
        utterance_id = f"u{self._utterance_seq}"
        await self.emit(HostUtteranceStarted(utterance_id=utterance_id))
        return utterance_id

    async def host_finishes(self, utterance_id: str | None = None, *, played: bool = True) -> str:
        """那一段正常說完；played 為真時裝置也回報播完。"""
        if utterance_id is None:
            utterance_id = await self.host_starts()
        await self.emit(HostUtteranceEnded(utterance_id=utterance_id, cancelled=False))
        if played:
            await self.device_sends(type="playback_done", utterance_id=utterance_id)
        return utterance_id


def rule_points(turn_number: int, phase_number: int) -> str:
    return content.rule_points_text(turn_number=turn_number, phase_number=phase_number)


def line(code: str, **kwargs: Any) -> str:
    if not kwargs and code in ("end_white_rose", "end_blood_blade"):
        # 宣布哪一方獲勝的兩句另外帶語氣與節奏的指示
        return content.line_request(code)
    return content.verbatim_request(content.fixed_line(code, **kwargs))


def back_to(turn_number: int, phase_number: int) -> str:
    return line("back_to", step="turn", turn_number=turn_number, phase_number=phase_number)
