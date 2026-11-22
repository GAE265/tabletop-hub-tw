"""阿里雲即時語音模型（Qwen-Audio Realtime）的實作。

用 WebSocket 連線：把對方的事件轉成介面定義的事件，把介面的動作轉成對方的訊息。
事件名稱與欄位照 2026-11-19 到 11-21 原型實際收到的事件寫，樣本在
tests/integrations/fake_realtime_upstream.py。

這裡不知道任何 domain、任何一款遊戲：指令、工具、聲線代號都由呼叫端傳進來。
金鑰不寫進例外訊息與紀錄；玩家說的話也不寫進紀錄。
"""

import asyncio
import base64
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from app.integrations.realtime_voice.base import RealtimeVoiceConnection, RealtimeVoiceProvider
from app.integrations.realtime_voice.errors import RealtimeVoiceUnavailable
from app.integrations.realtime_voice.types import (
    ConnectionLost,
    HostAudio,
    HostUtteranceEnded,
    HostUtteranceStarted,
    PlayerSpeechStarted,
    PlayerTranscript,
    RealtimeVoiceConfig,
    RealtimeVoiceEvent,
    SpeechNotAddressed,
    SpeechRejectedReason,
    SpeechRequestResult,
    ToolRequested,
)

logger = logging.getLogger(__name__)

# 聲線代號 → 阿里雲的聲線名稱。一條連線開始之後不能換聲線
VOICES: dict[str, str] = {
    "male": "xunanchuan_v3.1",
    "female": "longyuan_v3.1",
}
# 自動接話用的判斷方式。不用 server_vad：附和也會讓主持人停下來
AUTO_TURN_DETECTION = "smart_turn_v2"
# 請主持人開口時，放進對話的那一則訊息的開頭，讓模型知道這不是玩家說的話
_BACKEND_PREFIX = "（這是主持後端給你的指示，不是玩家說的話，照著做就好，不用回覆這一句）\n"
_OPEN_TIMEOUT = 15.0
_END = object()


class _Socket(Protocol):
    async def send(self, message: str) -> None: ...
    async def close(self) -> None: ...
    def __aiter__(self) -> AsyncIterator[str | bytes]: ...


Connector = Callable[[str, dict[str, str]], Awaitable[_Socket]]


async def _open_websocket(url: str, headers: dict[str, str]) -> _Socket:
    """真的開一條 WebSocket。握手失敗（例如金鑰錯誤是 HTTP 401）轉成介面的例外。"""
    from websockets.asyncio.client import connect
    from websockets.exceptions import InvalidStatus

    try:
        return await connect(
            url, additional_headers=headers, max_size=None, open_timeout=_OPEN_TIMEOUT
        )
    except InvalidStatus as exc:
        raise RealtimeVoiceUnavailable(f"握手失敗 HTTP {exc.response.status_code}") from exc


def _host_only(api_host: str) -> str:
    """主控台的 API Host 可能連同 https:// 或路徑一起貼進來，只留主機名稱。"""
    host = api_host.strip()
    for scheme in ("https://", "http://", "wss://", "ws://"):
        host = host.removeprefix(scheme)
    return host.split("/")[0]


class CloudRealtimeVoiceProvider(RealtimeVoiceProvider):
    def __init__(
        self,
        *,
        api_key: str,
        api_host: str,
        model: str,
        connector: Connector | None = None,
        session_timeout: float = 10.0,
        create_timeout: float = 3.0,
        retry_interval: float = 0.5,
    ) -> None:
        self._api_key = api_key
        self._url = f"wss://{_host_only(api_host)}/api-ws/v1/realtime?model={model}"
        self._connector = connector or _open_websocket
        self._session_timeout = session_timeout
        self._create_timeout = create_timeout
        self._retry_interval = retry_interval

    async def connect(self, config: RealtimeVoiceConfig) -> RealtimeVoiceConnection:
        session = _session_settings(config)
        try:
            socket = await self._connector(self._url, {"Authorization": f"Bearer {self._api_key}"})
        except RealtimeVoiceUnavailable:
            raise
        except Exception as exc:
            detail = str(exc).replace(self._api_key, "***")
            raise RealtimeVoiceUnavailable(
                f"連不上即時語音：{type(exc).__name__} {detail}".strip()
            ) from exc
        connection = CloudRealtimeVoiceConnection(
            socket, create_timeout=self._create_timeout, retry_interval=self._retry_interval
        )
        try:
            await connection.configure(session, timeout=self._session_timeout)
        except RealtimeVoiceUnavailable:
            await connection.close()
            raise
        return connection


def _session_settings(config: RealtimeVoiceConfig) -> dict[str, Any]:
    if config.voice not in VOICES:
        raise ValueError(f"未知的聲線代號：{config.voice}（支援 {'、'.join(VOICES)}）")
    turn_detection: dict[str, Any] | None = None
    if config.turn_taking_mode == "auto":
        turn_detection = {"type": AUTO_TURN_DETECTION}
        if config.turn_sensitivity is not None:
            turn_detection["threshold"] = config.turn_sensitivity
    return {
        "modalities": ["text", "audio"],
        "voice": VOICES[config.voice],
        "instructions": config.instructions,
        "input_audio_format": "pcm",
        "output_audio_format": "pcm",
        "input_audio_transcription": {"language": "zh"},
        "enable_speech_emotion": True,
        "max_history_turns": config.history_turns,
        # 按住說話：整個 turn_detection 設成 null，由呼叫端送出「放開」時才請它回答
        "turn_detection": turn_detection,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in config.tools
        ],
    }


class CloudRealtimeVoiceConnection(RealtimeVoiceConnection):
    def __init__(self, socket: _Socket, *, create_timeout: float, retry_interval: float) -> None:
        self._socket = socket
        self._create_timeout = create_timeout
        self._retry_interval = retry_interval
        self._events: asyncio.Queue[Any] = asyncio.Queue()
        self._closed = False
        self._lost = False
        self._session_ready: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        # 玩家是不是正在說話；有沒有回答正在產生；我們是不是剛送出「請回答」還在等結果
        self._player_speaking = False
        self._active_response: str | None = None
        self._creating = False
        self._create_waiter: asyncio.Future[str] | None = None
        self._quiet = asyncio.Event()
        self._quiet.set()
        # 已經開始出聲的回答
        self._speaking: set[str] = set()
        # 最近一句收進對話的玩家的話；每個回答是被哪一句話引出來的
        self._last_committed: str | None = None
        self._answer_last_committed = False
        self._response_speech: dict[str, str | None] = {}
        # 工具結果之後的「請回答」可能要等一下才送得出去
        self._tool_response: asyncio.Task[None] | None = None
        self._reader = asyncio.ensure_future(self._read())

    async def configure(self, session: dict[str, Any], *, timeout: float) -> None:
        """送出連線設定，等對方確認。被拒或等不到都當成連不上。"""
        await self._send({"type": "session.update", "session": session})
        try:
            await asyncio.wait_for(asyncio.shield(self._session_ready), timeout)
        except TimeoutError:
            raise RealtimeVoiceUnavailable("即時語音沒有確認連線設定") from None

    # ------------------------------------------------------------------ 動作

    async def send_audio(self, data: bytes) -> None:
        await self._send(
            {"type": "input_audio_buffer.append", "audio": base64.b64encode(data).decode()}
        )

    async def press_talk(self) -> None:
        await self._send({"type": "input_audio_buffer.clear"})

    async def release_talk(self) -> None:
        await self._send({"type": "input_audio_buffer.commit"})
        self._answer_last_committed = True
        await self._create_response()

    async def send_system_message(self, text: str) -> None:
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )

    async def request_speech(self, text: str) -> SpeechRequestResult:
        self._ensure_open()
        # 先看自己知道的狀態：這兩種情況送出去一定被拒，而且對話裡會多一則沒人回的訊息
        if self._player_speaking:
            return SpeechRequestResult(accepted=False, rejected_reason="player_speaking")
        if self._active_response is not None or self._creating:
            return SpeechRequestResult(accepted=False, rejected_reason="response_in_progress")
        self._drop_tool_response()
        # 對話裡沒有玩家的訊息時，「請回答」會被拒；所以把要說的內容放成一則玩家角色的訊息
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": _BACKEND_PREFIX + text}],
                },
            }
        )
        return await self._create_response()

    async def send_tool_result(self, call_id: str, output: str, *, respond: bool = True) -> None:
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {"type": "function_call_output", "call_id": call_id, "output": output},
            }
        )
        if respond:
            self._drop_tool_response()
            self._tool_response = asyncio.ensure_future(self._respond_when_quiet())

    async def cancel_response(self) -> None:
        self._drop_tool_response()
        if self._active_response is not None:
            # 沒有回答在進行時送取消，對方會回錯誤，所以只在有的時候送
            await self._send({"type": "response.cancel"})

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._drop_tool_response()
        try:
            await self._socket.close()
        except Exception:  # noqa: BLE001 反正要關了
            logger.debug("關即時語音的連線時失敗", exc_info=True)
        self._events.put_nowait(_END)

    async def events(self) -> AsyncIterator[RealtimeVoiceEvent]:
        while True:
            item = await self._events.get()
            if item is _END:
                # 放回去，讓之後再呼叫 events() 的人也馬上結束
                self._events.put_nowait(_END)
                return
            yield item

    # ------------------------------------------------------------------ 請回答

    async def _create_response(self) -> SpeechRequestResult:
        """送「請回答」，等對方說開始了或拒絕。等不到就當成送出了（對方沒有回確認的習慣）。"""
        waiter: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._create_waiter = waiter
        self._creating = True
        self._update_quiet()
        try:
            await self._send({"type": "response.create"})
            try:
                rejected = await asyncio.wait_for(waiter, self._create_timeout)
            except TimeoutError:
                rejected = ""
        finally:
            self._create_waiter = None
            self._creating = False
            self._update_quiet()
        if not rejected:
            return SpeechRequestResult(accepted=True)
        reason: SpeechRejectedReason = (
            "player_speaking" if "user is speaking" in rejected else "response_in_progress"
        )
        return SpeechRequestResult(accepted=False, rejected_reason=reason)

    async def _respond_when_quiet(self) -> None:
        """工具結果已經放進對話；等玩家講完、也沒有回答在進行，再請它回答。被拒就重送。"""
        while not self._closed and not self._lost:
            await self._quiet.wait()
            try:
                result = await self._create_response()
            except RealtimeVoiceUnavailable:
                return
            if result.accepted:
                return
            await asyncio.sleep(self._retry_interval)

    def _drop_tool_response(self) -> None:
        task, self._tool_response = self._tool_response, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def _update_quiet(self) -> None:
        if self._player_speaking or self._active_response is not None or self._creating:
            self._quiet.clear()
        else:
            self._quiet.set()

    # ------------------------------------------------------------------ 收事件

    async def _read(self) -> None:
        reason = "連線結束"
        try:
            async for raw in self._socket:
                self._on_event(json.loads(raw))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 不管對方怎麼斷的，都回報成斷線
            reason = f"{type(exc).__name__}: {exc}"
        if not self._closed:
            self._lost = True
            code = getattr(self._socket, "close_code", None)
            close_reason = getattr(self._socket, "close_reason", None)
            if code is not None:
                reason = f"{code} {close_reason or ''}".strip()
            if not self._session_ready.done():
                self._session_ready.set_exception(RealtimeVoiceUnavailable(reason))
            self._events.put_nowait(ConnectionLost(reason=reason))
            self._events.put_nowait(_END)

    def _on_event(self, event: dict[str, Any]) -> None:
        kind = event.get("type", "")
        if kind == "response.audio.delta":
            self._on_audio(event)
        elif kind == "response.created":
            self._on_response_created(event)
        elif kind == "response.done":
            self._on_response_done(event)
        elif kind == "response.function_call_arguments.done":
            self._on_function_call(event)
        elif kind == "input_audio_buffer.speech_started":
            self._player_speaking = True
            self._update_quiet()
            self._events.put_nowait(PlayerSpeechStarted())
        elif kind == "input_audio_buffer.speech_stopped":
            self._player_speaking = False
            self._update_quiet()
            if event.get("reason") == "turn_invalid":
                # 被判定成不是在跟它說話
                self._events.put_nowait(SpeechNotAddressed(speech_id=str(event.get("item_id"))))
        elif kind == "input_audio_buffer.committed":
            self._last_committed = event.get("item_id")
        elif kind.endswith("audio_transcription.delta"):
            # 被當成環境音的話（ambient）也有辨識文字，一樣交出去。
            # text 是已經確定的前半，stash 是還沒確定的尾巴
            text = str(event.get("text") or "") + str(event.get("stash") or "")
            self._emit_transcript(event, text, is_final=False)
        elif kind.endswith("audio_transcription.completed"):
            self._emit_transcript(event, str(event.get("transcript") or ""), is_final=True)
        elif kind == "session.updated":
            if not self._session_ready.done():
                self._session_ready.set_result(None)
        elif kind == "error":
            self._on_error(event)

    def _on_response_created(self, event: dict[str, Any]) -> None:
        response_id = str(event.get("response", {}).get("id"))
        self._active_response = response_id
        self._update_quiet()
        waiter = self._create_waiter
        if waiter is not None and not waiter.done():
            # 我們自己要求的回答。按住說話放開之後的那一個，是在回答剛收進去的那句話
            self._response_speech[response_id] = (
                self._last_committed if self._answer_last_committed else None
            )
            waiter.set_result("")
        else:
            # 對方自己開始的回答：是在回答最近收進對話的那句話
            self._response_speech[response_id] = self._last_committed
        self._answer_last_committed = False

    def _on_audio(self, event: dict[str, Any]) -> None:
        response_id = str(event.get("response_id"))
        if response_id not in self._speaking:
            self._speaking.add(response_id)
            self._events.put_nowait(HostUtteranceStarted(utterance_id=response_id))
        data = base64.b64decode(event.get("delta") or "")
        if data:
            self._events.put_nowait(HostAudio(utterance_id=response_id, data=data))

    def _on_response_done(self, event: dict[str, Any]) -> None:
        response = event.get("response", {})
        response_id = str(response.get("id"))
        if self._active_response == response_id:
            self._active_response = None
        self._update_quiet()
        self._response_speech.pop(response_id, None)
        if response_id in self._speaking:
            self._speaking.discard(response_id)
            self._events.put_nowait(
                HostUtteranceEnded(
                    utterance_id=response_id,
                    cancelled=response.get("status") == "cancelled",
                    usage=response.get("usage"),
                )
            )

    def _on_function_call(self, event: dict[str, Any]) -> None:
        try:
            arguments = json.loads(event.get("arguments") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        # 事件本身沒有帶是哪一句話；用「這個回答是被哪一句話引出來的」對出來
        speech_id = self._response_speech.get(str(event.get("response_id")))
        self._events.put_nowait(
            ToolRequested(
                call_id=str(event.get("call_id")),
                name=str(event.get("name")),
                arguments=arguments,
                speech_id=speech_id,
            )
        )

    def _emit_transcript(self, event: dict[str, Any], text: str, *, is_final: bool) -> None:
        if not text.strip():
            return
        self._events.put_nowait(
            PlayerTranscript(speech_id=str(event.get("item_id")), text=text, is_final=is_final)
        )

    def _on_error(self, event: dict[str, Any]) -> None:
        error = event.get("error") or {}
        message = str(error.get("message") or "")
        if not self._session_ready.done():
            self._session_ready.set_exception(
                RealtimeVoiceUnavailable(f"即時語音拒絕連線設定：{message}")
            )
            return
        waiter = self._create_waiter
        if error.get("param") == "response.create" and waiter is not None and not waiter.done():
            waiter.set_result(message or "rejected")
            return
        logger.warning("即時語音回報錯誤：%s %s", error.get("code"), message)

    # ------------------------------------------------------------------ 小工具

    def _ensure_open(self) -> None:
        if self._closed or self._lost:
            raise RealtimeVoiceUnavailable("即時語音的連線已經關了")

    async def _send(self, message: dict[str, Any]) -> None:
        self._ensure_open()
        try:
            await self._socket.send(json.dumps(message, ensure_ascii=False))
        except Exception as exc:
            raise RealtimeVoiceUnavailable(f"送不出去：{type(exc).__name__}") from exc
