"""groups service 單元測試用的手寫 fake（AGENTS.md 7.5），照 GroupsRepository 的介面在記憶體中運作。

只在 fixture 裡 import 這個模組：程式還沒寫的時候，每個測試各自失敗，不會整個資料夾收集失敗。
"""

import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from app.domains.groups.repository import GroupRecord, GroupView, MemberRecord, MemberView


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
    game_id: int | None
    status: str
    created_at: datetime


class FakeGroupsRepository:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.shops: dict[uuid.UUID, str] = {}
        self.users: dict[uuid.UUID, str] = {}
        self.games: dict[int, str] = {}
        self.groups: dict[uuid.UUID, _Group] = {}
        # 依寫入順序；同一團的順序就是報名先後
        self.members: list[MemberRecord] = []
        self._member_group: list[uuid.UUID] = []
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

    def game_exists(self, game_id: int) -> bool:
        return game_id in self.games

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

    def promote_waitlisted(self, group_id: uuid.UUID, count: int) -> int:
        promoted = self._waitlisted(group_id)[: max(count, 0)]
        for i, m in promoted:
            self.members[i] = replace(m, status="member")
        return len(promoted)

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
            game_id=group.game_id,
            game_name=self.games.get(group.game_id) if group.game_id is not None else None,
            member_count=sum(1 for m in rows if m.status == "member"),
            waitlist_count=sum(1 for m in rows if m.status == "waitlisted"),
            my_status=mine,
            created_at=group.created_at,
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
