"""揪團的資料存取。交易範圍由 service 用 transaction() 決定。

讀取共用資料表 booking_shops、auth_users、games 的名稱與是否存在，只讀不寫
（design.md D7；擁有者若之後提供讀取方法，改成呼叫該方法即可）。
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, delete, exists, func, insert, select, update
from sqlalchemy.orm import aliased

from app.core.db import SessionRepository
from app.core.games.models import Game
from app.domains.auth.models import AuthUser
from app.domains.booking.models import BookingShop
from app.domains.groups.models import Group, GroupMember


@dataclass(frozen=True)
class GroupRecord:
    """鎖定揪團後，service 判斷狀態與權限需要的欄位。"""

    id: uuid.UUID
    organizer_id: uuid.UUID
    capacity: int
    start_at: datetime
    end_at: datetime
    status: str


@dataclass(frozen=True)
class GroupView:
    """回應需要的揪團資料，含店家、開團主、遊戲名稱與人數統計。status 是儲存的值。"""

    id: uuid.UUID
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    capacity: int
    fee: int | None
    status: str
    shop_id: uuid.UUID
    shop_name: str
    organizer_id: uuid.UUID
    organizer_name: str
    game_id: int | None
    game_name: str | None
    member_count: int
    waitlist_count: int
    my_status: str | None
    created_at: datetime


@dataclass(frozen=True)
class MemberRecord:
    user_id: uuid.UUID
    status: str
    joined_at: datetime


@dataclass(frozen=True)
class MemberView:
    user_id: uuid.UUID
    display_name: str
    status: str
    joined_at: datetime


def _count(group_id_column: Any, status: str) -> Any:
    return (
        select(func.count())
        .where(GroupMember.group_id == group_id_column, GroupMember.status == status)
        .scalar_subquery()
    )


def _waitlist_order() -> tuple[Any, Any]:
    return GroupMember.joined_at, GroupMember.id


class GroupsRepository(SessionRepository):
    # --- 共用資料表（只讀） ---

    def shop_exists(self, shop_id: uuid.UUID) -> bool:
        return bool(self.session.scalar(select(exists().where(BookingShop.id == shop_id))))

    def game_exists(self, game_id: int) -> bool:
        return bool(self.session.scalar(select(exists().where(Game.id == game_id))))

    # --- 揪團 ---

    def add_group(self, **values: Any) -> uuid.UUID:
        return self.session.execute(insert(Group).values(**values).returning(Group.id)).scalar_one()

    def lock_group(self, group_id: uuid.UUID) -> GroupRecord | None:
        """以 SELECT ... FOR UPDATE 鎖住揪團，同一團的報名、退出、改人數依序執行（D3）。"""
        row = self.session.execute(
            select(
                Group.id,
                Group.organizer_id,
                Group.capacity,
                Group.start_at,
                Group.end_at,
                Group.status,
            )
            .where(Group.id == group_id)
            .with_for_update()
        ).one_or_none()
        return None if row is None else GroupRecord(**row._mapping)

    def update_group(self, group_id: uuid.UUID, values: Mapping[str, Any]) -> None:
        if values:
            self.session.execute(update(Group).where(Group.id == group_id).values(**values))

    # --- 成員與候補 ---

    def count_members(self, group_id: uuid.UUID) -> int:
        return self.session.scalar(_count_statement(group_id, "member")) or 0

    def find_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> MemberRecord | None:
        row = self.session.execute(
            select(GroupMember.user_id, GroupMember.status, GroupMember.joined_at).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        ).one_or_none()
        return None if row is None else MemberRecord(**row._mapping)

    def add_member(
        self, group_id: uuid.UUID, user_id: uuid.UUID, status: str, joined_at: datetime
    ) -> None:
        self.session.execute(
            insert(GroupMember).values(
                group_id=group_id, user_id=user_id, status=status, joined_at=joined_at
            )
        )

    def delete_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.session.execute(
            delete(GroupMember).where(
                GroupMember.group_id == group_id, GroupMember.user_id == user_id
            )
        )

    def promote_waitlisted(self, group_id: uuid.UUID, count: int) -> int:
        """把最早報名的 count 位候補改成成員，回傳實際遞補的人數。"""
        if count <= 0:
            return 0
        ids = (
            select(GroupMember.id)
            .where(GroupMember.group_id == group_id, GroupMember.status == "waitlisted")
            .order_by(*_waitlist_order())
            .limit(count)
            .scalar_subquery()
        )
        result = self.session.execute(
            update(GroupMember)
            .where(GroupMember.id.in_(ids))
            .values(status="member")
            .returning(GroupMember.id)
        )
        return len(result.all())

    def waitlist_position(self, group_id: uuid.UUID, user_id: uuid.UUID) -> int | None:
        ranked = (
            select(
                GroupMember.user_id,
                func.row_number().over(order_by=_waitlist_order()).label("position"),
            )
            .where(GroupMember.group_id == group_id, GroupMember.status == "waitlisted")
            .subquery()
        )
        return self.session.scalar(select(ranked.c.position).where(ranked.c.user_id == user_id))

    def list_members(self, group_id: uuid.UUID) -> list[MemberView]:
        """先列成員（依報名先後），再列候補（依候補順位）。"""
        rows = self.session.execute(
            select(
                GroupMember.user_id,
                AuthUser.display_name,
                GroupMember.status,
                GroupMember.joined_at,
            )
            .join(AuthUser, AuthUser.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id)
            .order_by((GroupMember.status == "waitlisted"), *_waitlist_order())
        )
        return [MemberView(**row._mapping) for row in rows]

    # --- 回應用的揪團資料 ---

    def _view_statement(self, viewer_id: uuid.UUID) -> Select[Any]:
        organizer = aliased(AuthUser)
        mine = (
            select(GroupMember.status)
            .where(GroupMember.group_id == Group.id, GroupMember.user_id == viewer_id)
            .scalar_subquery()
        )
        return (
            select(
                Group.id,
                Group.title,
                Group.description,
                Group.start_at,
                Group.end_at,
                Group.capacity,
                Group.fee,
                Group.status,
                Group.shop_id,
                BookingShop.name.label("shop_name"),
                Group.organizer_id,
                organizer.display_name.label("organizer_name"),
                Group.game_id,
                Game.name.label("game_name"),
                _count(Group.id, "member").label("member_count"),
                _count(Group.id, "waitlisted").label("waitlist_count"),
                mine.label("my_status"),
                Group.created_at,
            )
            .join(BookingShop, BookingShop.id == Group.shop_id)
            .join(organizer, organizer.id == Group.organizer_id)
            .outerjoin(Game, Game.id == Group.game_id)
        )

    def get_group(self, group_id: uuid.UUID, viewer_id: uuid.UUID) -> GroupView | None:
        row = self.session.execute(
            self._view_statement(viewer_id).where(Group.id == group_id)
        ).one_or_none()
        return None if row is None else GroupView(**row._mapping)

    def list_groups(
        self,
        *,
        viewer_id: uuid.UUID,
        start_from: datetime | None,
        start_before: datetime | None,
        shop_id: uuid.UUID | None,
        organizer_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> tuple[list[GroupView], int]:
        """已取消的揪團不列出（design.md D5），依開始時間排序。"""
        conditions = [Group.status != "cancelled"]
        if start_from is not None:
            conditions.append(Group.start_at >= start_from)
        if start_before is not None:
            conditions.append(Group.start_at < start_before)
        if shop_id is not None:
            conditions.append(Group.shop_id == shop_id)
        if organizer_id is not None:
            conditions.append(Group.organizer_id == organizer_id)
        where = and_(*conditions)

        total = self.session.scalar(select(func.count()).select_from(Group).where(where)) or 0
        rows = self.session.execute(
            self._view_statement(viewer_id)
            .where(where)
            .order_by(Group.start_at, Group.id)
            .offset(offset)
            .limit(limit)
        )
        return [GroupView(**row._mapping) for row in rows], total


def _count_statement(group_id: uuid.UUID, status: str) -> Select[Any]:
    return select(func.count()).where(
        GroupMember.group_id == group_id, GroupMember.status == status
    )
