from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.integrations.realtime_voice.types import (
    RealtimeVoiceConfig,
    RealtimeVoiceEvent,
    SpeechRequestResult,
)


class RealtimeVoiceConnection(ABC):
    """一條即時語音連線，從開到關（host spec §13.3、ADR 0004）。

    和 integrations/llm 的單次呼叫不同：連線開著的期間，呼叫端一邊送動作、一邊收事件。
    """

    @abstractmethod
    async def send_audio(self, data: bytes) -> None:
        """送玩家的聲音（16 kHz、單聲道、16 位元 PCM）。"""

    @abstractmethod
    async def press_talk(self) -> None:
        """按住說話：按下。"""

    @abstractmethod
    async def release_talk(self) -> None:
        """按住說話：放開，請語音模型回答剛剛那一段。"""

    @abstractmethod
    async def send_system_message(self, text: str) -> None:
        """送一則不出聲的系統訊息（保持連線用，順便帶現況）。"""

    @abstractmethod
    async def request_speech(self, text: str) -> SpeechRequestResult:
        """請主持人開口，text 是要它說的內容或指示。被拒時回報原因，由呼叫端決定要不要重送。"""

    @abstractmethod
    async def send_tool_result(self, call_id: str, output: str, *, respond: bool = True) -> None:
        """回工具結果。respond 為假時只把結果記進對話，不請主持人接著回答。"""

    @abstractmethod
    async def cancel_response(self) -> None:
        """取消正在產生的回答。沒有回答在進行時不做事。"""

    @abstractmethod
    async def close(self) -> None:
        """關連線。可以重複呼叫。"""

    @abstractmethod
    def events(self) -> AsyncIterator[RealtimeVoiceEvent]:
        """依序收到事件。連線關掉或斷線（ConnectionLost）之後結束。"""


class RealtimeVoiceProvider(ABC):
    """即時語音的唯一入口；domain 不得直接 import 廠商的 SDK。"""

    @abstractmethod
    async def connect(self, config: RealtimeVoiceConfig) -> RealtimeVoiceConnection:
        """開一條連線。連不上或金鑰錯誤時拋 RealtimeVoiceUnavailable。"""
