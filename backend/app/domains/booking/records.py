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
