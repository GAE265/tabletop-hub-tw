"""揪團與候補的資料表（AGENTS.md §10.3）。

shop_id、organizer_id、user_id、game_id 參照共用資料表 booking_shops、auth_users、games
（AGENTS.md 第 3 節），groups 只讀不改它們的結構。
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

GROUP_STATUSES = ("open", "cancelled")
MEMBER_STATUSES = ("member", "waitlisted")


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("capacity >= 2", name="ck_groups_capacity"),
        CheckConstraint("fee IS NULL OR fee >= 0", name="ck_groups_fee"),
        CheckConstraint("end_at > start_at", name="ck_groups_time"),
        # ended 不儲存，由 end_at 計算（design.md D2）
        CheckConstraint("status IN ('open', 'cancelled')", name="ck_groups_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("booking_shops.id"), index=True)
    organizer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("auth_users.id"), index=True)
    # 遊戲是選填；共用桌遊同步刪掉遊戲時設為空值，不擋住刪除
    game_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("games.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    # 新台幣，每人；空值代表沒有填寫
    fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroupMember(Base):
    """成員與候補放同一張表，用 status 區分；候補順位依 joined_at 計算（design.md D1）。"""

    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
        CheckConstraint("status IN ('member', 'waitlisted')", name="ck_group_members_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("auth_users.id"))
    status: Mapped[str] = mapped_column(Text)
    # 報名時間；遞補成成員時不改，名單才會維持報名先後
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
