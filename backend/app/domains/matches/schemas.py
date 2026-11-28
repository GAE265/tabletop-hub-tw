"""記錄一局遊戲 API 的請求與回應格式。時間一律帶時區，回應為 UTC（AGENTS.md 4.3）。"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

LocationType = Literal["shop", "home"]
MatchStatus = Literal["in_progress", "finished"]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


# --- 請求 ---


class MatchCreate(BaseModel):
    game_id: int
    played_on: date
    location_type: LocationType
    shop_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    progress: str | None = Field(default=None, max_length=100)
    # 開局者自己的座位；沒帶時使用最小的空位
    seat_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _shop_matches_location(self) -> Self:
        if self.location_type == "shop" and self.shop_id is None:
            raise ValueError("location_type 為 shop 時必須帶 shop_id")
        if self.location_type == "home" and self.shop_id is not None:
            raise ValueError("location_type 為 home（自家）時不可帶 shop_id")
        return self


class ParticipantCreate(BaseModel):
    """不帶 display_name＝自己加入；帶 display_name＝新增沒有帳號的參加者。不接受 user_id。"""

    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName | None = None
    seat_number: int | None = Field(default=None, ge=1)


class ParticipantConfirm(BaseModel):
    """只能確認（true），不能取消確認。"""

    model_config = ConfigDict(extra="forbid")

    is_confirmed: Literal[True]


class TurnCreate(BaseModel):
    turn_number: int = Field(ge=1)
    # 本回合首家的座位，選填；遊戲沒有這個概念或沒填時為空
    seat_number: int | None = Field(default=None, ge=1)
    game_data: dict[str, Any]


class SeatFaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seat_number: int = Field(ge=1)
    faction: str


class ResultRequest(BaseModel):
    """陣營勝負的結果。is_winner 由伺服器依陣營計算，不接受分數。"""

    model_config = ConfigDict(extra="forbid")

    winning_faction: str
    participants: list[SeatFaction] = Field(min_length=1)

    @model_validator(mode="after")
    def _seats_are_unique(self) -> Self:
        seats = [p.seat_number for p in self.participants]
        if len(set(seats)) != len(seats):
            raise ValueError("participants 的 seat_number 不可重複")
        return self


# --- 回應 ---


class UserRef(BaseModel):
    id: uuid.UUID
    display_name: str


class GameRef(BaseModel):
    id: int
    name: str


class ShopRef(BaseModel):
    id: uuid.UUID
    name: str


class ParticipantResponse(BaseModel):
    id: uuid.UUID
    seat_number: int
    user_id: uuid.UUID | None
    display_name: str
    faction: str | None
    score: int | None
    placement: int | None
    is_winner: bool | None
    is_confirmed: bool


class TurnResponse(BaseModel):
    id: uuid.UUID
    turn_number: int
    seat_number: int | None
    game_data: dict[str, Any]
    recorded_by: uuid.UUID
    updated_at: datetime


class MatchResponse(BaseModel):
    id: uuid.UUID
    game: GameRef
    played_on: date
    location_type: LocationType
    shop: ShopRef | None
    group_id: uuid.UUID | None
    created_by: UserRef
    status: MatchStatus
    result: dict[str, Any] | None
    progress: str | None
    participants: list[ParticipantResponse]
    turns: list[TurnResponse]
    participant_count: int
    account_count: int
    confirmed_count: int
    # 已記錄結果，且有帳號的參加者都已確認；查詢時計算，不存資料庫
    is_valid: bool
    created_at: datetime
    updated_at: datetime


class MatchListResponse(BaseModel):
    items: list[MatchResponse]
    total: int


# --- 通知 ---

MatchNotificationType = Literal[
    # 這一局的結果被記錄（第一次或帶 overwrite 覆蓋），收件人需要（重新）確認；
    # 例：玩家甲記錄白薔薇「薔薇陣營獲勝」，有帳號的玩家乙、丙各收到一則
    "match_result_recorded",
]


class NotificationMatchRef(BaseModel):
    id: uuid.UUID
    game_name: str
    played_on: date


class MatchNotificationResponse(BaseModel):
    id: uuid.UUID
    type: MatchNotificationType
    match: NotificationMatchRef
    # 記錄（或覆蓋）結果、觸發這則通知的人
    recorded_by: UserRef
    # null 代表未讀
    read_at: datetime | None
    created_at: datetime


class MatchNotificationListResponse(BaseModel):
    items: list[MatchNotificationResponse]
    total: int
    # 目前使用者全部未讀的數量，不受分頁影響
    unread_count: int


class MatchNotificationUpdate(BaseModel):
    # 只能標成已讀
    read: Literal[True]
