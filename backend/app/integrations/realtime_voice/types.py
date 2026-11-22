"""即時語音整合層的型別（host spec §13.3）。

這裡不出現任何廠商的事件名稱，也不知道任何 domain 與任何一款遊戲。
"""

from dataclasses import dataclass
from typing import Any, Literal

TurnTakingMode = Literal["auto", "push_to_talk"]
# 「請主持人開口」被拒的兩種原因：玩家正在說話、另一個回答還在進行
SpeechRejectedReason = Literal["player_speaking", "response_in_progress"]


@dataclass(frozen=True)
class VoiceToolSpec:
    """語音模型可以呼叫的一個工具；parameters 是 JSON Schema。"""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class RealtimeVoiceConfig:
    """開連線時由呼叫端給的設定。

    voice 是呼叫端的聲線代號，對應到廠商的聲線名稱由各實作負責。
    turn_sensitivity 只在 turn_taking_mode 為 auto 時使用。
    """

    instructions: str
    tools: list[VoiceToolSpec]
    voice: str
    turn_taking_mode: TurnTakingMode
    history_turns: int
    turn_sensitivity: float | None = None


@dataclass(frozen=True)
class SpeechRequestResult:
    """「請主持人開口」的回報：有沒有送出；被拒時帶原因。"""

    accepted: bool
    rejected_reason: SpeechRejectedReason | None = None


# --- 呼叫端會收到的事 ---


@dataclass(frozen=True)
class HostUtteranceStarted:
    """主持人的一段話開始。"""

    utterance_id: str


@dataclass(frozen=True)
class HostAudio:
    """主持人的聲音（24 kHz、單聲道、16 位元 PCM），屬於 utterance_id 那一段。"""

    utterance_id: str
    data: bytes


@dataclass(frozen=True)
class HostUtteranceEnded:
    """主持人的一段話結束。cancelled 為真代表被取消，不是正常說完。usage 是這一輪的用量。"""

    utterance_id: str
    cancelled: bool
    usage: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlayerSpeechStarted:
    """玩家開始說話。"""


@dataclass(frozen=True)
class PlayerTranscript:
    """玩家的辨識文字。speech_id 是那句話的編號；is_final 為假代表還是片段。"""

    speech_id: str
    text: str
    is_final: bool


@dataclass(frozen=True)
class SpeechNotAddressed:
    """這句話被判定成不是在跟主持人說話。"""

    speech_id: str


@dataclass(frozen=True)
class ToolRequested:
    """語音模型要呼叫工具。speech_id 是觸發它的那句話；廠商帶不出來時是 None。"""

    call_id: str
    name: str
    arguments: dict[str, Any]
    speech_id: str | None = None


@dataclass(frozen=True)
class ConnectionLost:
    """連線斷了。之後不會再有事件。"""

    reason: str


RealtimeVoiceEvent = (
    HostUtteranceStarted
    | HostAudio
    | HostUtteranceEnded
    | PlayerSpeechStarted
    | PlayerTranscript
    | SpeechNotAddressed
    | ToolRequested
    | ConnectionLost
)
