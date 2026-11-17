import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

Status = Literal["confirmed", "seated", "completed", "cancelled", "no_show"]


class SlotIn(BaseModel):
    start_at: AwareDatetime
    end_at: AwareDatetime


class BookingQuoteRequest(BaseModel):
    shop_id: uuid.UUID
    party_size: Annotated[int, Field(ge=1)]
    start_at: AwareDatetime
    end_at: AwareDatetime


class BookingCreate(BaseModel):
    shop_id: uuid.UUID
    party_size: Annotated[int, Field(ge=1)]
    start_at: AwareDatetime
    end_at: AwareDatetime
    special_requests: str | None = None
    # 與自己同電話的有效訂位重疊時，帶 true 代表確認取代舊訂位
    confirm_overlap: bool = False


class BookingPatch(BaseModel):
    """修改訂位內容，或變更狀態（兩者不能同時帶）。"""

    status: Status | None = None
    cancel_reason: str | None = None
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    party_size: Annotated[int, Field(ge=1)] | None = None
    special_requests: str | None = None
    # 修改後與自己的其他訂位重疊時，帶 true 代表合併（需同時帶 party_size）
    merge: bool = False

    @model_validator(mode="after")
    def _status_or_fields(self) -> "BookingPatch":
        edits = (self.start_at, self.end_at, self.party_size, self.special_requests)
        if self.status is not None and any(v is not None for v in edits):
            raise ValueError("status 不可與修改欄位同時送出")
        if self.status is None and not any(v is not None for v in edits):
            raise ValueError("沒有任何要修改的欄位")
        return self


class TablesPut(BaseModel):
    table_ids: Annotated[list[int], Field(min_length=1)]


class TableOut(BaseModel):
    id: int
    table_code: str


class FeeOut(BaseModel):
    billable_hours: Decimal
    hourly_fee: Decimal
    venue_fee: Decimal
    drink_reminder: str | None


class BookingOut(BaseModel):
    id: int
    reservation_code: str
    shop_id: uuid.UUID
    user_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    party_size: int
    status: str
    source: str
    special_requests: str | None
    tables: list[TableOut]
    estimated_fee: FeeOut
    seated_at: datetime | None
    completed_at: datetime | None
    final_fee: Decimal | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    notice: str | None = None


class BookingList(BaseModel):
    items: list[BookingOut]
    total: int


class BookingQuote(BaseModel):
    start_at: datetime
    end_at: datetime
    fee: FeeOut
    table_codes: list[str] = []


class ShopOut(BaseModel):
    id: uuid.UUID
    name: str


class ShopList(BaseModel):
    items: list[ShopOut]
    total: int
