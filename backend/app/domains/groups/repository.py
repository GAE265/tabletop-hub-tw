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
from app.domains.groups.models import Group, GroupGame, GroupMember, GroupNotification


@dataclass(frozen=True)
class GroupRecord:
    """鎖定揪團後，service 判斷狀態與權限需要的欄位。"""

    id: uuid.UUID
    organizer_id: uuid.UUID
    capacity: int
    start_at: datetime
    end_at: datetime
    status: str
    confirmed_at: datetime | None = None


@dataclass(frozen=True)
class GameItem:
    id: int
    name: str


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
    member_count: int
    waitlist_count: int
    my_status: str | None
    created_at: datetime
    confirmed_at: datetime | None = None
    # 依選擇的順序
    games: tuple[GameItem, ...] = ()


@dataclass(frozen=True)
class MemberRecord:
    user_id: uuid.UUID
    status: str
    joined_at: datetime


@dataclass(frozen=True)
class NotificationRecord:
    """標成已讀前，service 判斷擁有者需要的欄位。"""

    id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class NotificationView:
    """通知與揪團目前的名稱、開始時間。"""

    id: uuid.UUID
    type: str
    group_id: uuid.UUID
    group_title: str
    group_start_at: datetime
    read_at: datetime | None
    created_at: datetime


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

    def missing_games(self, game_ids: list[int]) -> list[int]:
        """game_ids 中不在 games 的編號，依輸入的順序。"""
        if not game_ids:
            return []
        found = set(self.session.scalars(select(Game.id).where(Game.id.in_(game_ids))))
        return [game_id for game_id in game_ids if game_id not in found]

    # --- 揪團的遊戲 ---

    def set_group_games(self, group_id: uuid.UUID, game_ids: list[int]) -> None:
        """整份取代揪團的遊戲，position 依 game_ids 的順序從 1 開始。"""
        self.session.execute(delete(GroupGame).where(GroupGame.group_id == group_id))
        if game_ids:
            self.session.execute(
                insert(GroupGame),
                [
                    {"group_id": group_id, "game_id": game_id, "position": position}
                    for position, game_id in enumerate(game_ids, start=1)
                ],
            )

    def _games_by_group(self, group_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[GameItem, ...]]:
        """一次查出多個揪團的遊戲，避免每個揪團各查一次。"""
        result: dict[uuid.UUID, list[GameItem]] = {}
        if group_ids:
            rows = self.session.execute(
                select(GroupGame.group_id, Game.id, Game.name)
                .join(Game, Game.id == GroupGame.game_id)
                .where(GroupGame.group_id.in_(group_ids))
                .order_by(GroupGame.group_id, GroupGame.position)
            )
            for group_id, game_id, name in rows:
                result.setdefault(group_id, []).append(GameItem(id=game_id, name=name))
        return {group_id: tuple(games) for group_id, games in result.items()}

    def _to_views(self, rows: Any) -> list[GroupView]:
        mappings = [dict(row._mapping) for row in rows]
        games = self._games_by_group([m["id"] for m in mappings])
        return [GroupView(**m, games=games.get(m["id"], ())) for m in mappings]

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
                Group.confirmed_at,
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

    def promote_waitlisted(self, group_id: uuid.UUID, count: int) -> list[uuid.UUID]:
        """把最早報名的 count 位候補改成成員，回傳被遞補的玩家（依報名先後）。"""
        if count <= 0:
            return []
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
            .returning(GroupMember.user_id, GroupMember.joined_at, GroupMember.id)
        )
        rows = sorted(result.all(), key=lambda row: (row.joined_at, row.id))
        return [row.user_id for row in rows]

    def list_member_user_ids(
        self, group_id: uuid.UUID, statuses: tuple[str, ...]
    ) -> list[uuid.UUID]:
        """依報名先後列出指定狀態（member、waitlisted）的玩家。"""
        return list(
            self.session.scalars(
                select(GroupMember.user_id)
                .where(GroupMember.group_id == group_id, GroupMember.status.in_(statuses))
                .order_by(*_waitlist_order())
            )
        )

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
                _count(Group.id, "member").label("member_count"),
                _count(Group.id, "waitlisted").label("waitlist_count"),
                mine.label("my_status"),
                Group.created_at,
                Group.confirmed_at,
            )
            .join(BookingShop, BookingShop.id == Group.shop_id)
            .join(organizer, organizer.id == Group.organizer_id)
        )

    def get_group(self, group_id: uuid.UUID, viewer_id: uuid.UUID) -> GroupView | None:
        rows = self.session.execute(self._view_statement(viewer_id).where(Group.id == group_id))
        views = self._to_views(rows)
        return views[0] if views else None

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
        return self._to_views(rows), total

    # --- 通知 ---

    def add_notifications(
        self,
        group_id: uuid.UUID,
        user_ids: list[uuid.UUID],
        type_: str,
        created_at: datetime,
    ) -> None:
        if user_ids:
            self.session.execute(
                insert(GroupNotification),
                [
                    {"user_id": u, "group_id": group_id, "type": type_, "created_at": created_at}
                    for u in user_ids
                ],
            )

    def list_notifications(
        self, user_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[NotificationView], int, int]:
        """回傳（這一頁的通知，總數，未讀數），新的在前。"""
        mine = GroupNotification.user_id == user_id
        total = self.session.scalar(select(func.count()).where(mine)) or 0
        unread = (
            self.session.scalar(
                select(func.count()).where(mine, GroupNotification.read_at.is_(None))
            )
            or 0
        )
        rows = self.session.execute(
            _notification_statement()
            .where(mine)
            .order_by(GroupNotification.created_at.desc(), GroupNotification.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [NotificationView(**row._mapping) for row in rows], total, unread

    def find_notification(self, notification_id: uuid.UUID) -> NotificationRecord | None:
        row = self.session.execute(
            select(GroupNotification.id, GroupNotification.user_id).where(
                GroupNotification.id == notification_id
            )
        ).one_or_none()
        return None if row is None else NotificationRecord(**row._mapping)

    def mark_read(self, notification_id: uuid.UUID, read_at: datetime) -> None:
        """只在未讀時寫入，重複標成已讀不改時間。"""
        self.session.execute(
            update(GroupNotification)
            .where(GroupNotification.id == notification_id, GroupNotification.read_at.is_(None))
            .values(read_at=read_at)
        )

    def get_notification(self, notification_id: uuid.UUID) -> NotificationView | None:
        row = self.session.execute(
            _notification_statement().where(GroupNotification.id == notification_id)
        ).one_or_none()
        return None if row is None else NotificationView(**row._mapping)


def _notification_statement() -> Select[Any]:
    """通知加上揪團目前的名稱與開始時間。"""
    return select(
        GroupNotification.id,
        GroupNotification.type,
        GroupNotification.group_id,
        Group.title.label("group_title"),
        Group.start_at.label("group_start_at"),
        GroupNotification.read_at,
        GroupNotification.created_at,
    ).join(Group, Group.id == GroupNotification.group_id)


def _count_statement(group_id: uuid.UUID, status: str) -> Select[Any]:
    return select(func.count()).where(
        GroupMember.group_id == group_id, GroupMember.status == status
    )
