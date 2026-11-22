"""手寫的假連線：取代阿里雲即時語音的 WebSocket（AGENTS.md §7.5）。

事件的形狀照 2026-11-19 到 11-21 原型實際收到的事件寫（只留用得到的欄位）。
"""

import asyncio
import base64
import json
from typing import Any

_END = object()


class FakeUpstream:
    """記下後端送出的每一則訊息；測試用 feed 讓後端收到事件。"""

    def __init__(self, *, ack_session: bool = True) -> None:
        self.sent: list[dict[str, Any]] = []
        self.closed = False
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self._incoming: asyncio.Queue[Any] = asyncio.Queue()
        # 收到某一種訊息時自動回的事件
        self._replies: dict[str, list[dict[str, Any]]] = {}
        if ack_session:
            self.reply_to("session.update", {"type": "session.updated", "session": {}})

    # --- 測試用 ---

    def reply_to(self, message_type: str, *events: dict[str, Any]) -> None:
        """之後每次收到這一種訊息，都自動回這些事件（取代之前的設定）。"""
        self._replies[message_type] = list(events)

    def feed(self, *events: dict[str, Any]) -> None:
        for event in events:
            self._incoming.put_nowait(json.dumps(event, ensure_ascii=False))

    def drop(self, code: int = 1007, reason: str = "response idle timeout") -> None:
        """對方把連線關掉。"""
        self.close_code = code
        self.close_reason = reason
        self._incoming.put_nowait(_END)

    def sent_types(self) -> list[str]:
        return [message["type"] for message in self.sent]

    def last(self, message_type: str) -> dict[str, Any]:
        return [m for m in self.sent if m["type"] == message_type][-1]

    # --- 連線的介面 ---

    async def send(self, raw: str) -> None:
        assert not self.closed, "連線關掉之後還送訊息"
        message = json.loads(raw)
        self.sent.append(message)
        self.feed(*self._replies.get(message["type"], []))

    async def close(self) -> None:
        if not self.closed:
            self.closed = True
            self._incoming.put_nowait(_END)

    def __aiter__(self) -> "FakeUpstream":
        return self

    async def __anext__(self) -> str:
        item = await self._incoming.get()
        if item is _END:
            raise StopAsyncIteration
        return item


class FakeConnector:
    """取代「開一條 WebSocket」：記下網址與標頭，回傳 FakeUpstream。"""

    def __init__(self, upstream: FakeUpstream | None = None, error: Exception | None = None):
        self.upstream = upstream or FakeUpstream()
        self.error = error
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def __call__(self, url: str, headers: dict[str, str]) -> FakeUpstream:
        self.calls.append((url, headers))
        if self.error is not None:
            raise self.error
        return self.upstream


# --- 事件樣本 ---


def response_created(response_id: str) -> dict[str, Any]:
    return {
        "type": "response.created",
        "response": {"id": response_id, "object": "realtime.response", "status": "in_progress"},
    }


def audio_delta(response_id: str, pcm: bytes) -> dict[str, Any]:
    return {
        "type": "response.audio.delta",
        "response_id": response_id,
        "item_id": "item_assistant",
        "delta": base64.b64encode(pcm).decode(),
    }


def response_done(
    response_id: str, *, status: str = "completed", reason: str | None = None
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "id": response_id,
        "object": "realtime.response",
        "status": status,
        "usage": {"total_tokens": 496, "input_tokens": 409, "output_tokens": 87},
    }
    if status == "cancelled":
        response["status_details"] = {"type": "cancelled", "reason": reason or "turn_detected"}
    return {"type": "response.done", "response": response}


def function_call(response_id: str, call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "type": "response.function_call_arguments.done",
        "response_id": response_id,
        "item_id": "item_function",
        "output_index": 1,
        "name": name,
        "call_id": call_id,
        "arguments": arguments,
    }


def speech_started(item_id: str) -> dict[str, Any]:
    return {"type": "input_audio_buffer.speech_started", "audio_start_ms": 3640, "item_id": item_id}


def speech_stopped(item_id: str, reason: str | None = None) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": "input_audio_buffer.speech_stopped",
        "audio_end_ms": 8672,
        "item_id": item_id,
    }
    if reason is not None:
        event["reason"] = reason
    return event


def committed(item_id: str) -> dict[str, Any]:
    return {"type": "input_audio_buffer.committed", "item_id": item_id}


def transcript_delta(item_id: str, text: str, stash: str, *, ambient: bool = False):
    kind = "ambient_audio_transcription" if ambient else "input_audio_transcription"
    return {
        "type": f"conversation.item.{kind}.delta",
        "item_id": item_id,
        "content_index": 0,
        "text": text,
        "stash": stash,
    }


def transcript_completed(item_id: str, transcript: str, *, ambient: bool = False):
    kind = "ambient_audio_transcription" if ambient else "input_audio_transcription"
    return {
        "type": f"conversation.item.{kind}.completed",
        "item_id": item_id,
        "content_index": 0,
        "transcript": transcript,
    }


def create_rejected(message: str) -> dict[str, Any]:
    return {
        "type": "error",
        "error": {
            "type": "invalid_request_error",
            "code": "invalid_value",
            "message": message,
            "param": "response.create",
        },
    }
