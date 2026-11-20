"""repository 與 service 之間傳遞的資料（不是 ORM 物件，也不是 API schema）。"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class UserInfo:
    id: uuid.UUID
    display_name: str
    role: str
    shop_id: uuid.UUID | None
    phone: str | None


@dataclass(frozen=True)
class TableRef:
    id: int
    table_code: str


@dataclass(frozen=True)
class ShopRef:
    id: uuid.UUID
    name: str


@dataclass
class ReservationRecord:
    id: int
    shop_id: uuid.UUID
    reservation_code: str
    user_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    party_size: int
    status: str
    source: str
    special_requests: str | None = None
    seated_at: datetime | None = None
    completed_at: datetime | None = None
    final_fee: Decimal | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    created_at: datetime | None = None
    tables: list[TableRef] = field(default_factory=list)

    @property
    def table_ids(self) -> list[int]:
        return [t.id for t in self.tables]


@dataclass(frozen=True)
class TableStatus:
    """桌位狀態記錄：桌子資訊 + 佔用狀態 + 可選的訂位摘要（權限控制）。"""

    id: int
    table_code: str
    name: str | None
    max_capacity: int
    floor: int
    x: int
    y: int
    width: int
    height: int
    shape: str
    status: str  # "available" | "unavailable"
    booking: "BookingSummary | None" = None


@dataclass(frozen=True)
class BookingSummary:
    """訂位摘要（tables/status 回傳時附在桌位資訊上）。"""

    id: int
    reservation_code: str
    user_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    party_size: int
    status: str


@dataclass(frozen=True)
class NotificationRecord:
    """標成已讀前用來確認通知屬於誰。"""

    id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class NotificationView:
    """一則訂位通知，加上訂位目前的資料。"""

    id: uuid.UUID
    type: str
    reservation_id: int
    reservation_code: str
    shop_name: str
    start_at: datetime
    end_at: datetime
    party_size: int
    read_at: datetime | None
    created_at: datetime
