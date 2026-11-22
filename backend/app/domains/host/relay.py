"""轉送（host spec §5.2、§7、§8.3、§10、§12）：把裝置、語音模型、圖三邊接起來。

一支裝置的一條 WebSocket 對應一個 HostRelay。它做的事：

- 兩個方向的聲音原樣轉送。
- 按鍵、辨識文字、工具請求、播完回報都排隊交給圖（圖是同步的，用另一條執行緒跑），
  再照圖交回的清單去做：請主持人開口、停播、送現況、回工具結果。
- 圖以外的計時：片段辨識文字等 0.3 秒、思考模型第 8 秒與第 15 秒、每 150 秒的系統訊息、
  和語音模型斷線後重連、請主持人開口被拒就重送。

這裡不 import 任何廠商的 SDK，也看不到廠商的事件名稱；語音模型一律走
integrations/realtime_voice 的介面。紀錄不寫玩家說的話與金鑰（spec §13.5）。
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.errors import AppError
from app.domains.host import content
from app.domains.host.graph import (
    Effect,
    Flush,
    HostEvent,
    HostSnapshot,
    Outcome,
    Speak,
    StartThinking,
    StateChanged,
    ToolOutput,
    match_voice_command,
    spoken_core,
)
from app.domains.host.schemas import (
    CommandMessage,
    PageHiddenMessage,
    PlaybackDoneMessage,
    TalkMessage,
    connection_message,
    error_message,
    flush_message,
    parse_device_message,
    state_message,
    utterance_message,
)
from app.domains.host.service import HostService
from app.integrations.realtime_voice import (
    ConnectionLost,
    HostAudio,
    HostUtteranceEnded,
    HostUtteranceStarted,
    PlayerTranscript,
    RealtimeVoiceConfig,
    RealtimeVoiceConnection,
    RealtimeVoiceError,
    RealtimeVoiceEvent,
    RealtimeVoiceProvider,
    SpeechNotAddressed,
    ToolRequested,
)

logger = logging.getLogger(__name__)

# 對話歷史的輪數（D21 預設 3）
HISTORY_TURNS = 50
# 自動接話的靈敏度（D11 §1）
TURN_SENSITIVITY = 0.5
# 片段辨識文字整句就是指令時，等這麼久沒有新的片段才執行（spec §5.2，沒有實測過）
PARTIAL_COMMAND_DELAY = 0.3
# 那句話的編號帶不出來時，同一個動作在這段時間內只執行一次（spec §5.2 的退路）
SAME_ACTION_WINDOW = 3.0
# 轉交思考模型：第 8 秒補一句，第 15 秒放棄（D09 §3、§4）
WAIT_LONGER_AFTER = 8.0
GIVE_UP_AFTER = 15.0
# 這麼久沒說話就送一則不出聲的系統訊息，避開語音模型 180 秒沒回答就斷線（D21 預設 1）
KEEP_ALIVE_AFTER = 150.0
# 和語音模型斷線後重試 3 次，間隔 1、2、4 秒（spec §10.2）
RECONNECT_DELAYS = (1.0, 2.0, 4.0)
# 請主持人開口被拒，隔這麼久重送（spec §10.3）
SPEECH_RETRY_INTERVAL = 0.5

# 結束這個動作相信語音模型（spec §5.2 的例外）：那句話不是問句，而且去掉標點後在這麼多字以內
TRUSTED_END_MAX_CHARS = 8
_WINNERS = ("white_rose", "blood_blade")
_COMMAND_TOOLS = ("next_step", "previous_step", "pause_hosting", "resume_hosting", "end_hosting")
_QUESTION_TOOLS = {"lookup_rules": "lookup", "ask_thinking_model": "thinking"}
_NOT_A_COMMAND = "這不是指令，流程沒有動。請照一般情況處理這句話；如果不是在跟你說話，就不要出聲。"
_COMMAND_DONE = "已執行。請不要回話，後端會把接下來要說的內容交給你。"
_COMMAND_PENDING = "收到。後端會用辨識文字核對這句話是不是指令，請不要回話。"
_QUESTION_VOIDED = "這一題已經作廢，不用回答。"
_TEXTS_KEPT = 50


@dataclass(frozen=True)
class Timers:
    """時間的來源。測試換成假時鐘，不真的等。"""

    now: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


class Device(Protocol):
    """裝置那一端的連線（瀏覽器的 WebSocket）。"""

    async def send_json(self, message: dict[str, Any]) -> None: ...
    async def send_bytes(self, data: bytes) -> None: ...
    async def close(self) -> None: ...


@dataclass(eq=False)
class _Waiting:
    """正在等思考模型的那一題。"""

    question_id: int
    call_id: str
    # 收到工具請求的時間；8 秒與 15 秒從這裡起算
    asked_at: float
    timers: asyncio.Task[None] | None = None


@dataclass(eq=False)
class _PendingSpeech:
    """被拒、還在重送的那一段。"""

    text: str
    segment_id: int | None


class HostRelay:
    def __init__(
        self,
        *,
        service: HostService,
        provider: RealtimeVoiceProvider,
        session_id: uuid.UUID,
        device: Device,
        turn_taking_mode: str | None = None,
        timers: Timers | None = None,
    ) -> None:
        self._service = service
        self._provider = provider
        self._session_id = session_id
        self._device = device
        # 這張通行碼要切換成的接話方式；沒有要換就是 None
        self._turn_taking_mode = turn_taking_mode
        self._timers = timers or Timers()
        self.closed = False

        self._loop: asyncio.AbstractEventLoop | None = None
        self._device_token: object | None = None
        self._jobs: asyncio.Queue[Callable[[], Coroutine[Any, Any, None]]] = asyncio.Queue()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._conn: RealtimeVoiceConnection | None = None
        self._reconnecting = False
        self._last_spoke = 0.0
        self._reset_voice_state()

    # ------------------------------------------------------------------ 開始與結束

    async def start(self) -> bool:
        """連上語音模型並開始轉送。連不上或這場主持不在了就送錯誤、關連線，回傳 False。"""
        self._loop = asyncio.get_running_loop()
        try:
            self._device_token = self._service.attach_device(
                self._session_id, self._kick_from_any_thread
            )
            # 先讓圖知道裝置連上了（切換接話方式、已結束的變回進行中），
            # 這樣交給語音模型的指令與現況才是新的；要說的話等連上語音模型再交
            deferred: list[Effect] = []
            await asyncio.to_thread(
                self._service.handle_event,
                self._session_id,
                HostEvent.connected(self._turn_taking_mode),
                on_effect=deferred.append,
            )
        except AppError:
            await self._fail("HOST_SESSION_NOT_FOUND")
            return False
        try:
            await self._open_voice()
        except RealtimeVoiceError as exc:
            # 真正的原因（例如金鑰錯誤）只記在後端紀錄（D12 §7）
            logger.warning("主持 %s 連不上語音模型：%s", self._session_id, exc)
            await self._fail("HOST_REALTIME_UNAVAILABLE")
            return False
        snapshot = self._snapshot()
        await self._send_json(state_message(snapshot))
        self._spawn(self._work())
        self._spawn(self._keep_alive())
        spoke = False
        for effect in deferred:
            if isinstance(effect, StateChanged):
                continue
            spoke = spoke or isinstance(effect, Speak)
            await self._apply(effect, call_id=None)
        if not spoke:
            # 主持暫停中接著主持：圖不會請主持人開口，這裡補一句接回流程（spec §9 的 M-06）
            await self._request_speech(_back_to_text(snapshot), None)
        return True

    async def close(self) -> None:
        """裝置斷線了：關掉和語音模型的連線，這場主持保留。"""
        await self._shutdown()

    async def wait_idle(self) -> None:
        """等排隊的事都處理完（測試用）。"""
        await self._jobs.join()

    async def _fail(self, code: str) -> None:
        """送一則錯誤給裝置，然後關連線。"""
        if self.closed:
            return
        await self._send_json(error_message(code))
        await self._shutdown()
        try:
            await self._device.close()
        except Exception:  # noqa: BLE001 裝置可能已經先斷了
            logger.debug("主持 %s 關裝置連線時失敗", self._session_id, exc_info=True)

    async def _shutdown(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self._device_token is not None:
            self._service.detach_device(self._session_id, self._device_token)
        current = asyncio.current_task()
        for task in list(self._tasks):
            if task is not current:
                task.cancel()
        while not self._jobs.empty():
            self._jobs.get_nowait()
            self._jobs.task_done()
        conn, self._conn = self._conn, None
        if conn is not None:
            await _close_quietly(conn)

    def _kick_from_any_thread(self, code: str) -> None:
        """被別的裝置取代，或這場主持被清掉。可能從別的執行緒呼叫。"""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(lambda: self._spawn(self._fail(code)))

    # ------------------------------------------------------------------ 裝置送來的

    async def handle_device_audio(self, data: bytes) -> None:
        """玩家的聲音：原樣轉給語音模型，不轉檔。"""
        conn = self._conn
        if conn is None or self.closed:
            return
        try:
            await conn.send_audio(data)
        except RealtimeVoiceError as exc:
            self._lost(conn, f"送聲音失敗：{exc}")

    async def handle_device_text(self, raw: str) -> None:
        """裝置送的一則 JSON。看不懂就回 HOST_BAD_MESSAGE，連線不關。"""
        if self.closed:
            return
        try:
            message = parse_device_message(raw)
        except ValueError:
            await self._send_json(error_message("HOST_BAD_MESSAGE"))
            return
        if isinstance(message, CommandMessage):
            event = HostEvent.command(message.action)
            self._enqueue(lambda: self._button(event))
        elif isinstance(message, TalkMessage):
            self._enqueue(self._talk_down if message.state == "down" else self._talk_up)
        elif isinstance(message, PageHiddenMessage):
            self._enqueue(lambda: self._run_graph(HostEvent.page_hidden()))
        elif isinstance(message, PlaybackDoneMessage):
            segment_id = self._utterance_segments.pop(message.utterance_id, None)
            if segment_id is not None:
                self._enqueue(lambda: self._run_graph(HostEvent.playback_done(segment_id)))

    async def _button(self, event: HostEvent) -> None:
        self._cut_segment = None
        await self._run_graph(event)

    async def _talk_down(self) -> None:
        """按住說話：按下去主持人立刻停（D11 §1）。那一段不自動重講，留著等「繼續」。"""
        self._stop_pending_speech()
        conn = self._conn
        if conn is not None:
            await conn.press_talk()
        await self._cancel_response()
        self._cut_segment = None
        await self._send_json(flush_message())

    async def _talk_up(self) -> None:
        conn = self._conn
        if conn is not None:
            await conn.release_talk()

    # ------------------------------------------------------------------ 語音模型送來的

    async def _read(self, conn: RealtimeVoiceConnection) -> None:
        try:
            async for event in conn.events():
                if self.closed or self._conn is not conn:
                    return
                if isinstance(event, ConnectionLost):
                    self._lost(conn, event.reason)
                    return
                await self._on_voice_event(event)
        except RealtimeVoiceError as exc:
            self._lost(conn, str(exc))

    async def _on_voice_event(self, event: RealtimeVoiceEvent) -> None:
        if isinstance(event, HostAudio):
            await self._send_bytes(event.data)
        elif isinstance(event, HostUtteranceStarted):
            await self._on_utterance_started(event)
        elif isinstance(event, HostUtteranceEnded):
            await self._on_utterance_ended(event)
        elif isinstance(event, PlayerTranscript):
            self._on_transcript(event)
        elif isinstance(event, SpeechNotAddressed):
            self._enqueue(self._chatter)
        elif isinstance(event, ToolRequested):
            self._enqueue(lambda: self._on_tool(event))
        # 玩家開始說話：語音模型會自己取消正在產生的回答，這裡不用做事

    async def _on_utterance_started(self, event: HostUtteranceStarted) -> None:
        self._host_speaking = True
        self._last_spoke = self._timers.now()
        requested, self._expecting = self._expecting, False
        segment_id, self._expected_segment = self._expected_segment, None
        if requested and segment_id is not None:
            self._utterance_segments[event.utterance_id] = segment_id
        elif not requested and self._waiting is not None:
            # 等答案的時候主持人自己回了別的話（例如玩家說「算了」）：舊題作廢（spec §8.4）
            self._enqueue(self._drop_waiting_question)
        await self._send_json(utterance_message(event.utterance_id, "start"))

    async def _on_utterance_ended(self, event: HostUtteranceEnded) -> None:
        self._host_speaking = False
        self._last_spoke = self._timers.now()
        if event.usage is not None:
            logger.info("主持 %s 這一輪的用量：%s", self._session_id, event.usage)
        if event.cancelled:
            segment_id = self._utterance_segments.pop(event.utterance_id, None)
            if self._cancelled_by_us:
                self._cancelled_by_us = False
            else:
                # 有人開口把它切斷了。是不是閒聊，要等「不回應」或「不是在跟它說話」才知道
                self._cut_segment = segment_id
        await self._send_json(utterance_message(event.utterance_id, "end"))

    def _on_transcript(self, event: PlayerTranscript) -> None:
        """路 2：後端自己看辨識文字（spec §5.2）。片段要等 0.3 秒沒有新的片段才執行。"""
        speech_id, text = event.speech_id, event.text
        self._texts[speech_id] = text
        self._last_text = text
        while len(self._texts) > _TEXTS_KEPT:
            self._texts.pop(next(iter(self._texts)))
        waiting = self._partial_timers.pop(speech_id, None)
        if waiting is not None:
            waiting.cancel()
        if event.is_final:
            self._final_speech.add(speech_id)
            self._enqueue(lambda: self._final_transcript(speech_id, text))
        elif match_voice_command(text) is not None:
            self._partial_timers[speech_id] = self._spawn(self._partial_command(speech_id, text))

    async def _partial_command(self, speech_id: str, text: str) -> None:
        await self._timers.sleep(PARTIAL_COMMAND_DELAY)
        self._partial_timers.pop(speech_id, None)
        if self._texts.get(speech_id) == text:
            self._enqueue(lambda: self._voice_command(speech_id, text))

    async def _final_transcript(self, speech_id: str, text: str) -> None:
        """一句話完整的辨識文字到了：先照一般的核對；沒過的話，看有沒有在等它的「結束」。"""
        waiting_end = speech_id in self._pending_ends
        winner = self._pending_ends.pop(speech_id, None)
        if await self._voice_command(speech_id, text) is None and waiting_end:
            await self._trusted_end(speech_id, text, winner)

    async def _trusted_end(self, speech_id: str | None, text: str, winner: str | None) -> bool:
        """語音模型呼叫了「結束」，但辨識文字不是清單上的說法。

        辨識文字常常認不出「血刃」這種遊戲裡的詞（實測「血刃贏了」30 句只有 2 句辨識正確），
        語音模型自己聽聲音卻大多聽得懂。所以結束這個動作相信模型：那句話不是問句、
        而且夠短就執行，誰贏用模型說的。結束後 30 分鐘內可以接著主持，誤判的傷害有限。
        其他指令仍然要整句等於清單上的說法。
        """
        core = spoken_core(text)
        if core is None or not 0 < len(core) <= TRUSTED_END_MAX_CHARS:
            return False
        if self._first_time(speech_id, "end"):
            self._cut_segment = None
            await self._run_graph(
                HostEvent.command("end", winner=winner if winner in _WINNERS else None)  # type: ignore[arg-type]
            )
        return True

    async def _voice_command(self, speech_id: str | None, text: str) -> bool | None:
        """核對並執行語音指令。回傳 None：不是指令；True：這次執行了；False：同一句已經執行過。"""
        command = match_voice_command(text)
        if command is None:
            return None
        if not self._first_time(speech_id, command.action):
            return False
        self._cut_segment = None
        await self._run_graph(HostEvent.voice_text(text))
        return True

    def _first_time(self, speech_id: str | None, action: str) -> bool:
        """同一句話只執行一次：用那句話的編號判斷；編號帶不出來就看 3 秒內有沒有做過同一個動作。"""
        now = self._timers.now()
        recent = self._recent_actions.get(action)
        if speech_id is None:
            if recent is not None and now - recent < SAME_ACTION_WINDOW:
                return False
        elif (speech_id, action) in self._executed:
            return False
        else:
            self._executed.add((speech_id, action))
        self._recent_actions[action] = now
        return True

    async def _chatter(self) -> None:
        """閒聊：那一段因此被切斷的話，圖會決定要不要自動重講（spec §6.5）。"""
        cut, self._cut_segment = self._cut_segment, None
        await self._run_graph(HostEvent.chatter(cut))

    async def _on_tool(self, event: ToolRequested) -> None:
        name = event.name
        if name in _COMMAND_TOOLS:
            await self._on_command_tool(event)
        elif name == "no_reply":
            await self._tool_result(event.call_id, "", respond=False)
            await self._chatter()
        elif name in _QUESTION_TOOLS:
            await self._on_question_tool(event)
        else:
            logger.warning("主持 %s 收到不認得的工具請求：%s", self._session_id, name)
            await self._tool_result(event.call_id, "沒有這個工具。", respond=False)

    async def _on_command_tool(self, event: ToolRequested) -> None:
        """路 1：模型呼叫指令工具。核對用後端自己的辨識文字，不用模型填的字（spec §5.2）。"""
        text = self._texts.get(event.speech_id) if event.speech_id else self._last_text
        is_end = event.name == "end_hosting"
        winner = event.arguments.get("winner") if is_end else None
        complete = event.speech_id is None or event.speech_id in self._final_speech
        if text is None or (is_end and not complete and match_voice_command(text) is None):
            # 辨識文字還沒到（或只有片段）：等它到了走路 2；「結束」另外記著，到時候再判斷
            if is_end and event.speech_id is not None:
                self._pending_ends[event.speech_id] = winner
            await self._tool_result(event.call_id, _COMMAND_PENDING, respond=False)
            return
        if match_voice_command(text) is None:
            if is_end and await self._trusted_end(event.speech_id, text, winner):
                await self._tool_result(event.call_id, _COMMAND_DONE, respond=False)
                return
            await self._tool_result(event.call_id, _NOT_A_COMMAND, respond=False)
            return
        await self._tool_result(event.call_id, _COMMAND_DONE, respond=False)
        await self._voice_command(event.speech_id, text)

    async def _on_question_tool(self, event: ToolRequested) -> None:
        asked_at = self._timers.now()
        question = str(event.arguments.get("question") or "").strip()
        if not question and event.speech_id:
            question = self._texts.get(event.speech_id, "")
        self._cut_segment = None
        # 新的一題取代還在等的舊題：舊的工具請求收掉，答案晚到也不唸（spec §8.4）
        await self._close_waiting()
        await self._run_graph(
            HostEvent.ask(question, kind=_QUESTION_TOOLS[event.name]),  # type: ignore[arg-type]
            call_id=event.call_id,
            asked_at=asked_at,
        )

    # ------------------------------------------------------------------ 跑圖並執行結果

    async def _run_graph(
        self, event: HostEvent, *, call_id: str | None = None, asked_at: float | None = None
    ) -> Outcome | None:
        """把一件事交給圖（在另一條執行緒跑），圖每交出一件要做的事就馬上去做。"""
        loop = asyncio.get_running_loop()
        effects: asyncio.Queue[Effect | None] = asyncio.Queue()

        def work() -> Outcome | None:
            try:
                return self._service.handle_event(
                    self._session_id,
                    event,
                    on_effect=lambda effect: loop.call_soon_threadsafe(effects.put_nowait, effect),
                )
            except AppError:
                # 這場主持在排隊的時候被清掉了
                return None
            finally:
                loop.call_soon_threadsafe(effects.put_nowait, None)

        running = asyncio.ensure_future(asyncio.to_thread(work))
        while (effect := await effects.get()) is not None:
            await self._apply(effect, call_id=call_id, asked_at=asked_at)
        return await running

    async def _apply(
        self, effect: Effect, *, call_id: str | None, asked_at: float | None = None
    ) -> None:
        if isinstance(effect, StateChanged):
            await self._send_json(state_message(effect.snapshot))
        elif isinstance(effect, Flush):
            self._stop_pending_speech()
            await self._cancel_response()
            self._cut_segment = None
            await self._send_json(flush_message())
        elif isinstance(effect, Speak):
            self._cut_segment = None
            await self._request_speech(effect.text, effect.segment_id)
        elif isinstance(effect, ToolOutput):
            if call_id is None:
                logger.warning("主持 %s 有一題的結果找不到對應的工具請求", self._session_id)
                return
            await self._tool_result(call_id, effect.output, respond=effect.respond)
            if effect.respond:
                self._expect(effect.segment_id)
        elif isinstance(effect, StartThinking):
            if call_id is not None:
                self._start_thinking(effect, call_id, asked_at)

    # ------------------------------------------------------------------ 請主持人開口

    def _expect(self, segment_id: int | None) -> None:
        """下一段主持人的話是後端要求的；segment_id 是圖替那一段編的號（沒有就是 None）。"""
        self._expecting = True
        self._expected_segment = segment_id

    async def _ask_to_speak(self, text: str) -> bool:
        conn = self._conn
        if conn is None:
            return False
        try:
            result = await conn.request_speech(text)
        except RealtimeVoiceError as exc:
            self._lost(conn, f"請主持人開口失敗：{exc}")
            return False
        return result.accepted

    async def _request_speech(self, text: str, segment_id: int | None) -> None:
        """請主持人開口。被拒就每 0.5 秒重送，直到送出、被新的內容取代、或進入主持暫停。"""
        self._stop_pending_speech()
        if await self._ask_to_speak(text):
            self._expect(segment_id)
            return
        pending = _PendingSpeech(text, segment_id)
        self._pending_speech = pending
        self._spawn(self._resend(pending))

    async def _resend(self, pending: _PendingSpeech) -> None:
        while self._pending_speech is pending and not self.closed:
            await self._timers.sleep(SPEECH_RETRY_INTERVAL)
            if self._pending_speech is not pending:
                return
            if await self._ask_to_speak(pending.text):
                self._pending_speech = None
                self._expect(pending.segment_id)
                return

    def _stop_pending_speech(self) -> None:
        self._pending_speech = None

    async def _cancel_response(self) -> None:
        conn = self._conn
        if conn is None:
            return
        if self._host_speaking:
            # 接下來那一段「被取消」是我們自己取消的，不算被人切斷
            self._cancelled_by_us = True
        self._expecting = False
        self._expected_segment = None
        try:
            await conn.cancel_response()
        except RealtimeVoiceError as exc:
            self._lost(conn, f"取消回答失敗：{exc}")

    async def _tool_result(self, call_id: str, output: str, *, respond: bool) -> None:
        conn = self._conn
        if conn is None:
            return
        try:
            await conn.send_tool_result(call_id, output, respond=respond)
        except RealtimeVoiceError as exc:
            self._lost(conn, f"回工具結果失敗：{exc}")

    # ------------------------------------------------------------------ 思考模型的計時

    def _start_thinking(self, effect: StartThinking, call_id: str, asked_at: float | None) -> None:
        waiting = _Waiting(
            question_id=effect.question_id,
            call_id=call_id,
            asked_at=self._timers.now() if asked_at is None else asked_at,
        )
        self._waiting = waiting
        waiting.timers = self._spawn(self._thinking_timers(waiting))
        self._spawn(self._think(waiting, effect))

    async def _think(self, waiting: _Waiting, effect: StartThinking) -> None:
        """在圖的排隊之外請思考模型回答：等它的那幾秒，暫停與下一步都照常處理。"""
        try:
            answer = await asyncio.to_thread(
                self._service.graph.think, effect.question, effect.chunks
            )
        except Exception as exc:  # noqa: BLE001 思考模型回任何錯誤都走放棄那條路（D09 §4）
            logger.warning(
                "主持 %s 的思考模型失敗，改交查到的片段：%s", self._session_id, type(exc).__name__
            )
            self._enqueue(lambda: self._finish_waiting(waiting, None))
            return
        self._enqueue(lambda: self._finish_waiting(waiting, answer))

    async def _thinking_timers(self, waiting: _Waiting) -> None:
        elapsed = self._timers.now() - waiting.asked_at
        await self._timers.sleep(WAIT_LONGER_AFTER - elapsed)
        if self._waiting is not waiting:
            return
        # 整段等待只補一次；被拒就算了，不重送（spec §10.3）
        if await self._ask_to_speak(content.verbatim_request(content.fixed_line("wait_longer"))):
            self._expect(None)
        await self._timers.sleep(GIVE_UP_AFTER - WAIT_LONGER_AFTER)
        if self._waiting is waiting:
            self._enqueue(lambda: self._finish_waiting(waiting, None))

    async def _finish_waiting(self, waiting: _Waiting, answer: str | None) -> None:
        """答案回來了（answer 有值），或放棄（None）。已經作廢或放棄過的題目就丟掉。"""
        if self._waiting is not waiting:
            return
        self._waiting = None
        if waiting.timers is not None:
            waiting.timers.cancel()
        if answer is None:
            event = HostEvent.give_up(waiting.question_id)
        else:
            event = HostEvent.answer_ready(waiting.question_id, answer)
        await self._run_graph(event, call_id=waiting.call_id)

    async def _close_waiting(self) -> None:
        waiting, self._waiting = self._waiting, None
        if waiting is None:
            return
        if waiting.timers is not None:
            waiting.timers.cancel()
        await self._tool_result(waiting.call_id, _QUESTION_VOIDED, respond=False)

    async def _drop_waiting_question(self) -> None:
        if self._waiting is None:
            return
        await self._close_waiting()
        await self._run_graph(HostEvent.drop_question())

    # ------------------------------------------------------------------ 保持連線與重連

    async def _keep_alive(self) -> None:
        """主持人 150 秒沒說話，就送一則不出聲的系統訊息，順便帶現況（spec §10.1）。"""
        while not self.closed:
            remaining = KEEP_ALIVE_AFTER - (self._timers.now() - self._last_spoke)
            if remaining > 0:
                await self._timers.sleep(remaining)
                continue
            self._last_spoke = self._timers.now()
            conn = self._conn
            if conn is None:
                continue
            snapshot = self._snapshot()
            try:
                await conn.send_system_message(
                    content.status_text(
                        step=snapshot.step,
                        turn_number=snapshot.turn_number,
                        phase_number=snapshot.phase_number,
                        paused=snapshot.paused,
                    )
                )
            except RealtimeVoiceError as exc:
                self._lost(conn, f"送系統訊息失敗：{exc}")

    def _lost(self, conn: RealtimeVoiceConnection, reason: str) -> None:
        if self.closed or self._conn is not conn or self._reconnecting:
            return
        self._reconnecting = True
        self._conn = None
        logger.warning("主持 %s 和語音模型斷線：%s", self._session_id, reason)
        self._spawn(self._reconnect(conn))

    async def _reconnect(self, old: RealtimeVoiceConnection) -> None:
        """裝置那條連線不斷，後端自己重連（spec §10.2）。"""
        self._cancel_voice_timers()
        self._reset_voice_state()
        await _close_quietly(old)
        await self._send_json(connection_message("reconnecting"))
        for delay in RECONNECT_DELAYS:
            await self._timers.sleep(delay)
            if self.closed:
                return
            try:
                await self._open_voice()
            except RealtimeVoiceError as exc:
                logger.warning("主持 %s 重連語音模型失敗：%s", self._session_id, exc)
                continue
            break
        else:
            # 連不回來：這場主持照 30 分鐘保留
            await self._fail("HOST_REALTIME_UNAVAILABLE")
            return
        self._reconnecting = False
        await self._send_json(connection_message("ready"))
        # 交完整指令加現況之後，主持人只說接回流程那一句；主持暫停中就不說
        self._enqueue(lambda: self._run_graph(HostEvent.connected()))

    async def _open_voice(self) -> None:
        """開一條語音模型的連線，交完整指令加現況（spec §4.3、§9）。"""
        snapshot = self._snapshot()
        config = RealtimeVoiceConfig(
            instructions=content.build_instructions(
                player_count=snapshot.player_count,
                step=snapshot.step,
                turn_number=snapshot.turn_number,
                phase_number=snapshot.phase_number,
                paused=snapshot.paused,
            ),
            tools=content.host_tools(),
            voice=snapshot.voice,
            turn_taking_mode=snapshot.turn_taking_mode,  # type: ignore[arg-type]
            history_turns=HISTORY_TURNS,
            turn_sensitivity=TURN_SENSITIVITY if snapshot.turn_taking_mode == "auto" else None,
        )
        conn = await self._provider.connect(config)
        if self.closed:
            await _close_quietly(conn)
            return
        self._conn = conn
        self._last_spoke = self._timers.now()
        self._spawn(self._read(conn))

    # ------------------------------------------------------------------ 小工具

    def _reset_voice_state(self) -> None:
        """只對一條語音模型的連線有意義的狀態；重連時全部歸零。"""
        # 主持人是不是正在說；下一段是不是後端要求的、對應圖的哪一段
        self._host_speaking = False
        self._expecting = False
        self._expected_segment: int | None = None
        # 語音模型的每一段話對應圖的哪一段（裝置回報播完時用）
        self._utterance_segments: dict[str, int] = {}
        # 剛被人開口切斷的那一段；我們自己取消的不算
        self._cut_segment: int | None = None
        self._cancelled_by_us = False
        self._pending_speech: _PendingSpeech | None = None
        self._waiting: _Waiting | None = None
        # 每句話的辨識文字（只留在記憶體，不寫進紀錄）
        self._texts: dict[str, str] = {}
        self._last_text: str | None = None
        self._partial_timers: dict[str, asyncio.Task[None]] = {}
        # 已經執行過的（那句話的編號, 動作）；每個動作最近執行的時間
        self._executed: set[tuple[str, str]] = set()
        self._recent_actions: dict[str, float] = {}
        # 完整的辨識文字已經到了的那些話；語音模型呼叫了「結束」、還在等辨識文字的那些話
        self._final_speech: set[str] = set()
        self._pending_ends: dict[str, str | None] = {}

    def _cancel_voice_timers(self) -> None:
        for task in self._partial_timers.values():
            task.cancel()
        if self._waiting is not None and self._waiting.timers is not None:
            self._waiting.timers.cancel()

    def _snapshot(self) -> HostSnapshot:
        return self._service.graph.snapshot(str(self._session_id))

    def _enqueue(self, job: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        if not self.closed:
            self._jobs.put_nowait(job)

    async def _work(self) -> None:
        """同一場主持一次只處理一件事，其他的排隊（spec §8.1）。"""
        while True:
            job = await self._jobs.get()
            try:
                await job()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 一件事出錯不能讓整場主持停下來
                logger.exception("主持 %s 處理一件事時出錯", self._session_id)
            finally:
                self._jobs.task_done()

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _send_json(self, message: dict[str, Any]) -> None:
        if self.closed:
            return
        try:
            await self._device.send_json(message)
        except Exception:  # noqa: BLE001 裝置斷線由收訊息那一側處理
            logger.debug("主持 %s 送訊息給裝置失敗", self._session_id, exc_info=True)

    async def _send_bytes(self, data: bytes) -> None:
        if self.closed:
            return
        try:
            await self._device.send_bytes(data)
        except Exception:  # noqa: BLE001
            logger.debug("主持 %s 送聲音給裝置失敗", self._session_id, exc_info=True)


def _back_to_text(snapshot: HostSnapshot) -> str:
    return content.verbatim_request(
        content.back_to_line(
            step=snapshot.step,
            turn_number=snapshot.turn_number,
            phase_number=snapshot.phase_number,
        )
    )


async def _close_quietly(conn: RealtimeVoiceConnection) -> None:
    try:
        await conn.close()
    except Exception:  # noqa: BLE001 反正要關了
        logger.debug("關語音模型的連線時失敗", exc_info=True)
