"""AI 語音主持 API 的請求與回應格式（host spec §11）。時間一律 ISO 8601、UTC。"""

import json
import uuid
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, TypeAdapter, ValidationError

from app.domains.host.content import MAX_PLAYERS, MIN_PLAYERS
from app.domains.host.graph import HostSnapshot

# 接話方式。auto：自動接話（預設）；push_to_talk：按住說話
TurnTakingMode = Literal["auto", "push_to_talk"]
# 聲線。male：男聲（預設）；female：女聲。開始後這場主持不能換
Voice = Literal["male", "female"]
# 一場主持的狀態。active：進行中；ended：已結束（30 分鐘內可以接著主持）
SessionStatus = Literal["active", "ended"]
# 流程節點。opening：開場；setup：開局準備；night_1、night_2：夜晚兩步；turn：回合內；ended：結束
Step = Literal["opening", "setup", "night_1", "night_2", "turn", "ended"]
# 贏的一方。white_rose：白薔薇陣營；blood_blade：血刃陣營
Winner = Literal["white_rose", "blood_blade"]


class HostingSessionCreate(BaseModel):
    player_count: int = Field(ge=MIN_PLAYERS, le=MAX_PLAYERS)
    turn_taking_mode: TurnTakingMode = "auto"
    voice: Voice = "male"


class ConnectionCreate(BaseModel):
    # 有帶而且和現在不同，就是切換接話方式
    turn_taking_mode: TurnTakingMode | None = None


class HostingSessionOut(BaseModel):
    """一場主持。三個端點都用同一個（spec §11.2）。"""

    id: uuid.UUID
    status: SessionStatus
    player_count: int
    turn_taking_mode: TurnTakingMode
    voice: Voice
    step: Step
    # 回合內才有值，從 1 開始；已結束時保留結束前的值
    turn_number: int | None
    phase_number: int | None
    paused: bool
    winner: Winner | None
    created_at: AwareDatetime


class ConnectionOut(BaseModel):
    # 一次性通行碼，60 秒內有效
    ticket: str
    expires_at: AwareDatetime


class HostingSessionWithConnection(BaseModel):
    session: HostingSessionOut
    connection: ConnectionOut


class HostingSessionList(BaseModel):
    items: list[HostingSessionOut]
    total: int


# --- WebSocket：裝置送的 JSON 訊息（spec §12.3） ---


class CommandMessage(BaseModel):
    """按鍵。效果和語音指令相同，不用核對。"""

    type: Literal["command"]
    # next：下一步；previous：上一步；pause：暫停；resume：繼續；end：結束主持（不帶贏的一方）
    action: Literal["next", "previous", "pause", "resume", "end"]


class TalkMessage(BaseModel):
    """按住說話的按下與放開。"""

    type: Literal["talk"]
    # down：按下；up：放開
    state: Literal["down", "up"]


class PageHiddenMessage(BaseModel):
    """頁面被切走或鎖屏。"""

    type: Literal["page_hidden"]


class PlaybackDoneMessage(BaseModel):
    """這一段在裝置上播完了。"""

    type: Literal["playback_done"]
    utterance_id: str = Field(min_length=1)


DeviceMessage = Annotated[
    CommandMessage | TalkMessage | PageHiddenMessage | PlaybackDoneMessage,
    Field(discriminator="type"),
]
_DEVICE_MESSAGE = TypeAdapter(DeviceMessage)


def parse_device_message(
    raw: str,
) -> CommandMessage | TalkMessage | PageHiddenMessage | PlaybackDoneMessage:
    """解析裝置送來的一則 JSON。看不懂就拋 ValueError。"""
    try:
        return _DEVICE_MESSAGE.validate_python(json.loads(raw))
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ValueError("看不懂的訊息") from exc


# --- WebSocket：後端送的 JSON 訊息（spec §12.4） ---

# 錯誤碼與給人看的說明。⚠️ 錯誤碼要和前端 host_stream.dart 同步
STREAM_ERRORS: dict[str, str] = {
    "HOST_TICKET_INVALID": "通行碼不對、過期，或已經用過了",
    "HOST_SESSION_NOT_FOUND": "找不到這場主持，可能已經被清掉了",
    "HOST_SESSION_TAKEN_OVER": "已在別的裝置接著主持",
    "HOST_REALTIME_UNAVAILABLE": "主持人暫時連不上，請稍後再試",
    "HOST_BAD_MESSAGE": "看不懂這一則訊息",
}


def state_message(snapshot: HostSnapshot) -> dict[str, Any]:
    """現況。連上時送一次，之後有變就送整份。"""
    return {
        "type": "state",
        "status": snapshot.status,
        "step": snapshot.step,
        "turn_number": snapshot.turn_number,
        "phase_number": snapshot.phase_number,
        "paused": snapshot.paused,
        "pause_reason": snapshot.pause_reason,
        "looking_up": snapshot.looking_up,
        "turn_taking_mode": snapshot.turn_taking_mode,
        "voice": snapshot.voice,
        "winner": snapshot.winner,
    }


def utterance_message(utterance_id: str, state: Literal["start", "end"]) -> dict[str, Any]:
    """主持人的一段話開始送、送完。之間的二進位訊息都屬於這一段。"""
    return {"type": "utterance", "utterance_id": utterance_id, "state": state}


def flush_message() -> dict[str, Any]:
    """立刻停播並清空待播內容。"""
    return {"type": "flush"}


def connection_message(state: Literal["reconnecting", "ready"]) -> dict[str, Any]:
    """後端和語音模型的連線。"""
    return {"type": "connection", "state": state}


def error_message(code: str) -> dict[str, Any]:
    return {
        "type": "error",
        "error": {"code": code, "message": STREAM_ERRORS[code], "details": {}},
    }
