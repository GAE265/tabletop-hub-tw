"""groups service 單元測試用的手寫 fake（AGENTS.md 7.5），照 GroupsRepository 的介面在記憶體中運作。

只在 fixture 裡 import 這個模組：程式還沒寫的時候，每個測試各自失敗，不會整個資料夾收集失敗。
"""

import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from app.domains.groups.repository import (
    GameItem,
    GroupRecord,
    GroupView,
    MemberRecord,
    MemberView,
    NotificationRecord,
    NotificationView,
)


@dataclass
class _Group:
    id: uuid.UUID
    shop_id: uuid.UUID
    organizer_id: uuid.UUID
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    capacity: int
    fee: int | None
    status: str
    created_at: datetime
    confirmed_at: datetime | None = None


@dataclass
class _Notification:
    id: uuid.UUID
    user_id: uuid.UUID
    group_id: uuid.UUID
    type: str
    created_at: datetime
    read_at: datetime | None = None


class FakeGroupsRepository:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.shops: dict[uuid.UUID, str] = {}
        self.users: dict[uuid.UUID, str] = {}
        self.games: dict[int, str] = {}
        self.groups: dict[uuid.UUID, _Group] = {}
        # 揪團的遊戲，依選擇的順序
        self.group_games: dict[uuid.UUID, list[int]] = {}
        # 依寫入順序；同一團的順序就是報名先後
        self.members: list[MemberRecord] = []
        self._member_group: list[uuid.UUID] = []
        # 依建立順序
        self.notifications: list[_Notification] = []
        self.committed = 0
        self.rolled_back = 0

    # --- 測試準備資料用 ---

    def add_shop(self, name: str = "測試店") -> uuid.UUID:
        shop_id = uuid.uuid4()
        self.shops[shop_id] = name
        return shop_id

    def add_user(self, user_id: uuid.UUID, name: str) -> uuid.UUID:
        self.users[user_id] = name
        return user_id

    def add_game_row(self, game_id: int, name: str) -> int:
        self.games[game_id] = name
        return game_id

    # --- GroupsRepository 介面 ---

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
        except BaseException:
            self.rolled_back += 1
            raise
        self.committed += 1

    def shop_exists(self, shop_id: uuid.UUID) -> bool:
        return shop_id in self.shops

    def missing_games(self, game_ids: list[int]) -> list[int]:
        return [game_id for game_id in game_ids if game_id not in self.games]

    def set_group_games(self, group_id: uuid.UUID, game_ids: list[int]) -> None:
        self.group_games[group_id] = list(game_ids)

    def add_group(self, **values: Any) -> uuid.UUID:
        group = _Group(id=uuid.uuid4(), status="open", created_at=self.now, **values)
        self.groups[group.id] = group
        return group.id

    def lock_group(self, group_id: uuid.UUID) -> GroupRecord | None:
        group = self.groups.get(group_id)
        if group is None:
            return None
        return GroupRecord(
            id=group.id,
            organizer_id=group.organizer_id,
            capacity=group.capacity,
            start_at=group.start_at,
            end_at=group.end_at,
            status=group.status,
            confirmed_at=group.confirmed_at,
        )

    def update_group(self, group_id: uuid.UUID, values: Mapping[str, Any]) -> None:
        group = self.groups[group_id]
        for key, value in values.items():
            setattr(group, key, value)

    def _rows(self, group_id: uuid.UUID) -> list[tuple[int, MemberRecord]]:
        return [
            (i, m)
            for i, (m, g) in enumerate(zip(self.members, self._member_group, strict=True))
            if g == group_id
        ]

    def count_members(self, group_id: uuid.UUID) -> int:
        return sum(1 for _, m in self._rows(group_id) if m.status == "member")

    def find_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> MemberRecord | None:
        return next((m for _, m in self._rows(group_id) if m.user_id == user_id), None)

    def add_member(
        self, group_id: uuid.UUID, user_id: uuid.UUID, status: str, joined_at: datetime
    ) -> None:
        self.members.append(MemberRecord(user_id=user_id, status=status, joined_at=joined_at))
        self._member_group.append(group_id)

    def delete_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> None:
        for i, m in self._rows(group_id):
            if m.user_id == user_id:
                del self.members[i]
                del self._member_group[i]
                return

    def _waitlisted(self, group_id: uuid.UUID) -> list[tuple[int, MemberRecord]]:
        rows = [(i, m) for i, m in self._rows(group_id) if m.status == "waitlisted"]
        return sorted(rows, key=lambda row: (row[1].joined_at, row[0]))

    def promote_waitlisted(self, group_id: uuid.UUID, count: int) -> list[uuid.UUID]:
        promoted = self._waitlisted(group_id)[: max(count, 0)]
        for i, m in promoted:
            self.members[i] = replace(m, status="member")
        return [m.user_id for _, m in promoted]

    def list_member_user_ids(
        self, group_id: uuid.UUID, statuses: tuple[str, ...]
    ) -> list[uuid.UUID]:
        rows = sorted(self._rows(group_id), key=lambda row: (row[1].joined_at, row[0]))
        return [m.user_id for _, m in rows if m.status in statuses]

    def waitlist_position(self, group_id: uuid.UUID, user_id: uuid.UUID) -> int | None:
        for position, (_, m) in enumerate(self._waitlisted(group_id), start=1):
            if m.user_id == user_id:
                return position
        return None

    def _view(self, group: _Group, viewer_id: uuid.UUID) -> GroupView:
        rows = [m for _, m in self._rows(group.id)]
        mine = next((m.status for m in rows if m.user_id == viewer_id), None)
        return GroupView(
            id=group.id,
            title=group.title,
            description=group.description,
            start_at=group.start_at,
            end_at=group.end_at,
            capacity=group.capacity,
            fee=group.fee,
            status=group.status,
            shop_id=group.shop_id,
            shop_name=self.shops[group.shop_id],
            organizer_id=group.organizer_id,
            organizer_name=self.users.get(group.organizer_id, ""),
            games=tuple(
                GameItem(id=game_id, name=self.games[game_id])
                for game_id in self.group_games.get(group.id, [])
            ),
            member_count=sum(1 for m in rows if m.status == "member"),
            waitlist_count=sum(1 for m in rows if m.status == "waitlisted"),
            my_status=mine,
            created_at=group.created_at,
            confirmed_at=group.confirmed_at,
        )

    def get_group(self, group_id: uuid.UUID, viewer_id: uuid.UUID) -> GroupView | None:
        group = self.groups.get(group_id)
        return None if group is None else self._view(group, viewer_id)

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
        groups = [
            g
            for g in self.groups.values()
            if g.status != "cancelled"
            and (start_from is None or g.start_at >= start_from)
            and (start_before is None or g.start_at < start_before)
            and (shop_id is None or g.shop_id == shop_id)
            and (organizer_id is None or g.organizer_id == organizer_id)
        ]
        groups.sort(key=lambda g: (g.start_at, str(g.id)))
        page = groups[offset : offset + limit]
        return [self._view(g, viewer_id) for g in page], len(groups)

    def list_members(self, group_id: uuid.UUID) -> list[MemberView]:
        rows = self._rows(group_id)
        members = sorted(
            [(i, m) for i, m in rows if m.status == "member"],
            key=lambda row: (row[1].joined_at, row[0]),
        )
        ordered = members + self._waitlisted(group_id)
        return [
            MemberView(
                user_id=m.user_id,
                display_name=self.users.get(m.user_id, ""),
                status=m.status,
                joined_at=m.joined_at,
            )
            for _, m in ordered
        ]

    # --- 通知 ---

    def add_notifications(
        self,
        group_id: uuid.UUID,
        user_ids: list[uuid.UUID],
        type_: str,
        created_at: datetime,
    ) -> None:
        for user_id in user_ids:
            self.notifications.append(
                _Notification(uuid.uuid4(), user_id, group_id, type_, created_at)
            )

    def _notification_view(self, n: _Notification) -> NotificationView:
        group = self.groups[n.group_id]
        return NotificationView(
            id=n.id,
            type=n.type,
            group_id=group.id,
            group_title=group.title,
            group_start_at=group.start_at,
            read_at=n.read_at,
            created_at=n.created_at,
        )

    def list_notifications(
        self, user_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[NotificationView], int, int]:
        # 新的在前；同一時間建立的，後寫入的在前
        mine = [n for n in reversed(self.notifications) if n.user_id == user_id]
        mine.sort(key=lambda n: n.created_at, reverse=True)
        unread = sum(1 for n in mine if n.read_at is None)
        page = mine[offset : offset + limit]
        return [self._notification_view(n) for n in page], len(mine), unread

    def find_notification(self, notification_id: uuid.UUID) -> NotificationRecord | None:
        n = next((n for n in self.notifications if n.id == notification_id), None)
        return None if n is None else NotificationRecord(id=n.id, user_id=n.user_id)

    def mark_read(self, notification_id: uuid.UUID, read_at: datetime) -> None:
        for n in self.notifications:
            if n.id == notification_id and n.read_at is None:
                n.read_at = read_at

    def get_notification(self, notification_id: uuid.UUID) -> NotificationView | None:
        n = next((n for n in self.notifications if n.id == notification_id), None)
        return None if n is None else self._notification_view(n)
