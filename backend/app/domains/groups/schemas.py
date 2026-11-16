"""揪團 API 的請求與回應格式。時間一律帶時區，回應為 UTC（AGENTS.md 4.3）。"""

import uuid
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, model_validator

MemberStatus = Literal["member", "waitlisted"]
GroupStatus = Literal["open", "cancelled", "ended"]


class GroupCreate(BaseModel):
    shop_id: uuid.UUID
    title: str = Field(min_length=1, max_length=100)
    start_at: AwareDatetime
    end_at: AwareDatetime
    capacity: int = Field(ge=2)
    fee: int | None = Field(default=None, ge=0)
    game_id: int | None = None
    description: str | None = Field(default=None, max_length=2000)


# 這些欄位可以省略，但不能改成空值
_REQUIRED_WHEN_SET = ("title", "start_at", "end_at", "capacity")


class GroupUpdate(BaseModel):
    """只更新有帶的欄位。fee、game_id、description 可以帶 null 清空。"""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    capacity: int | None = Field(default=None, ge=2)
    fee: int | None = Field(default=None, ge=0)
    game_id: int | None = None
    description: str | None = Field(default=None, max_length=2000)
    # 只能取消；其他狀態不能由使用者設定
    status: Literal["cancelled"] | None = None

    @model_validator(mode="after")
    def _no_null_for_required(self) -> Self:
        for name in _REQUIRED_WHEN_SET:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} 不能是 null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status 不能是 null")
        return self


class ShopRef(BaseModel):
    id: uuid.UUID
    name: str


class UserRef(BaseModel):
    id: uuid.UUID
    display_name: str


class GameRef(BaseModel):
    id: int
    name: str


class GroupResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    start_at: AwareDatetime
    end_at: AwareDatetime
    capacity: int
    fee: int | None
    status: GroupStatus
    shop: ShopRef
    organizer: UserRef
    game: GameRef | None
    member_count: int
    waitlist_count: int
    remaining_slots: int
    my_status: MemberStatus | None
    created_at: AwareDatetime


class GroupListResponse(BaseModel):
    items: list[GroupResponse]
    total: int


class JoinResponse(BaseModel):
    user_id: uuid.UUID
    status: MemberStatus
    waitlist_position: int | None


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str
    status: MemberStatus
    waitlist_position: int | None
    joined_at: AwareDatetime


class MemberListResponse(BaseModel):
    items: list[MemberResponse]
    total: int
