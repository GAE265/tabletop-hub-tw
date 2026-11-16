"""自動桌位分配（純函式）。

單桌優先；單桌放不下才列舉多桌組合，依（等級、桌數、總容量、桌號）排序。
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations

from app.domains.booking.errors import NoTableAvailable

BUFFER_MINUTES = 5


@dataclass(frozen=True)
class TableInfo:
    id: uuid.UUID
    table_code: str
    min_capacity: int
    max_capacity: int


@dataclass(frozen=True)
class TableLink:
    table_a_id: uuid.UUID
    table_b_id: uuid.UUID
    is_combinable: bool


@dataclass(frozen=True)
class Occupancy:
    """某張桌位上，其他有效訂位占用的區間。"""

    table_id: uuid.UUID
    user_id: uuid.UUID
    start_at: datetime
    end_at: datetime


def is_conflict(
    occupancy: Occupancy,
    *,
    user_id: uuid.UUID,
    start_at: datetime,
    end_at: datetime,
    buffer_minutes: int = BUFFER_MINUTES,
) -> bool:
    """同一使用者緩衝 0 分鐘，不同使用者前後各留緩衝。"""
    buffer = timedelta(minutes=0 if occupancy.user_id == user_id else buffer_minutes)
    return start_at < occupancy.end_at + buffer and occupancy.start_at < end_at + buffer


def free_tables(
    tables: Iterable[TableInfo],
    occupancies: Iterable[Occupancy],
    *,
    user_id: uuid.UUID,
    start_at: datetime,
    end_at: datetime,
    buffer_minutes: int = BUFFER_MINUTES,
) -> list[TableInfo]:
    by_table: dict[uuid.UUID, list[Occupancy]] = defaultdict(list)
    for occupancy in occupancies:
        by_table[occupancy.table_id].append(occupancy)
    return [
        t
        for t in tables
        if not any(
            is_conflict(
                o, user_id=user_id, start_at=start_at, end_at=end_at, buffer_minutes=buffer_minutes
            )
            for o in by_table[t.id]
        )
    ]


def _adjacency(
    links: Iterable[TableLink], *, combinable_only: bool
) -> dict[uuid.UUID, set[uuid.UUID]]:
    graph: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for link in links:
        if combinable_only and not link.is_combinable:
            continue
        graph[link.table_a_id].add(link.table_b_id)
        graph[link.table_b_id].add(link.table_a_id)
    return graph


def _connected(ids: Sequence[uuid.UUID], graph: dict[uuid.UUID, set[uuid.UUID]]) -> bool:
    members = set(ids)
    seen = {ids[0]}
    stack = [ids[0]]
    while stack:
        for nxt in graph[stack.pop()] & members - seen:
            seen.add(nxt)
            stack.append(nxt)
    return seen == members


def combination_grade(
    ids: Sequence[uuid.UUID],
    combinable_graph: dict[uuid.UUID, set[uuid.UUID]],
    all_graph: dict[uuid.UUID, set[uuid.UUID]],
) -> int:
    if _connected(ids, combinable_graph):
        return 1
    if _connected(ids, all_graph):
        return 2
    return 3


def pick_single(party_size: int, available: Iterable[TableInfo]) -> list[TableInfo] | None:
    fits = [t for t in available if t.min_capacity <= party_size <= t.max_capacity]
    if not fits:
        return None
    return [min(fits, key=lambda t: (t.max_capacity, t.table_code))]


def pick_combination(
    party_size: int, available: Sequence[TableInfo], links: Sequence[TableLink]
) -> list[TableInfo] | None:
    if sum(t.max_capacity for t in available) < party_size:
        return None
    combinable = _adjacency(links, combinable_only=True)
    everything = _adjacency(links, combinable_only=False)
    best: tuple | None = None
    for size in range(2, len(available) + 1):
        for subset in combinations(available, size):
            total = sum(t.max_capacity for t in subset)
            if total < party_size:
                continue
            grade = combination_grade([t.id for t in subset], combinable, everything)
            key = (grade, size, total, sorted(t.table_code for t in subset))
            if best is None or key < best[0]:
                best = (key, list(subset))
    return None if best is None else best[1]


def allocate(
    party_size: int,
    tables: Sequence[TableInfo],
    links: Sequence[TableLink],
    occupancies: Sequence[Occupancy],
    *,
    user_id: uuid.UUID,
    start_at: datetime,
    end_at: datetime,
    preferred_ids: Sequence[uuid.UUID] = (),
    buffer_minutes: int = BUFFER_MINUTES,
) -> list[TableInfo]:
    """回傳分配到的桌位；找不到時拋出 NoTableAvailable。

    preferred_ids 是修改訂位時的原桌位，仍可用且容量足夠就沿用。
    """
    available = free_tables(
        tables,
        occupancies,
        user_id=user_id,
        start_at=start_at,
        end_at=end_at,
        buffer_minutes=buffer_minutes,
    )
    if preferred_ids:
        keep = [t for t in available if t.id in set(preferred_ids)]
        if len(keep) == len(set(preferred_ids)):
            single_ok = (
                len(keep) == 1 and keep[0].min_capacity <= party_size <= keep[0].max_capacity
            )
            if single_ok or (len(keep) > 1 and sum(t.max_capacity for t in keep) >= party_size):
                return keep
    chosen = pick_single(party_size, available) or pick_combination(party_size, available, links)
    if chosen is None:
        raise NoTableAvailable()
    return chosen


def allocate_batch(
    slots: Sequence[tuple[datetime, datetime]],
    party_size: int,
    tables: Sequence[TableInfo],
    links: Sequence[TableLink],
    occupancies: Sequence[Occupancy],
    *,
    user_id: uuid.UUID,
    buffer_minutes: int = BUFFER_MINUTES,
) -> list[list[TableInfo]]:
    """依序分配每個時段；前面已分配的桌位也算占用。任一時段失敗就拋出 NoTableAvailable。"""
    taken = list(occupancies)
    result: list[list[TableInfo]] = []
    for start_at, end_at in slots:
        chosen = allocate(
            party_size,
            tables,
            links,
            taken,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
            buffer_minutes=buffer_minutes,
        )
        taken.extend(Occupancy(t.id, user_id, start_at, end_at) for t in chosen)
        result.append(chosen)
    return result
