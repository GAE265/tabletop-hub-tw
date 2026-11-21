"""AI 語音主持 API 的請求與回應格式（host spec §11）。時間一律 ISO 8601、UTC。"""

import uuid
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.domains.host.content import MAX_PLAYERS, MIN_PLAYERS

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
