import uuid

import pytest

from app.domains.booking.allocation import (
    Occupancy,
    allocate,
    allocate_batch,
    is_conflict,
)
from app.domains.booking.errors import NoTableAvailable
from tests.booking.support import LINKS, TABLES, local, tables, tid

USER = uuid.UUID(int=1)
OTHER = uuid.UUID(int=2)
D = "2026-11-20"


def run(party, codes, occupancies=(), **kw):
    kw.setdefault("user_id", USER)
    kw.setdefault("start_at", local(D, "14:00"))
    kw.setdefault("end_at", local(D, "16:00"))
    got = allocate(party, tables(*codes), LINKS, list(occupancies), **kw)
    return sorted(t.table_code for t in got)


def test_single_smallest_fit():
    assert run(7, "CF") == ["F"]  # F max 8，比 C max 10 小


def test_single_tie_breaks_by_code():
    assert run(5, "BA") == ["A"]


def test_small_group():
    assert run(1, "ABCDEFGHI") == ["G"]  # 最小可容納桌


def test_prefers_combinable_and_fewest_tables():
    assert run(13, "BCEDHI") == ["B", "C"]  # 等級 1、桌數最少、總容量 16 最小


def test_chain_combination():
    assert run(25, "BCEDHI") == ["B", "C", "E"]  # H+I=24 不足，B+C+E=26


def test_fallback_adjacent_not_combinable():
    assert run(11, "AB") == ["A", "B"]


def test_fallback_not_adjacent():
    assert run(12, "FG") == ["F", "G"]


def test_not_enough_capacity():
    with pytest.raises(NoTableAvailable):
        run(100, "ABCDEFGHI")


def test_buffer_other_user():
    busy = [Occupancy(tid("F"), OTHER, local(D, "12:00"), local(D, "14:00"))]
    # 他人 14:00 結束，14:03 開始距離不足 5 分鐘
    assert run(7, "FC", busy, start_at=local(D, "14:03")) == ["C"]
    assert run(7, "FC", busy, start_at=local(D, "14:05")) == ["F"]


def test_buffer_before_next_booking():
    busy = [Occupancy(tid("F"), OTHER, local(D, "16:03"), local(D, "18:00"))]
    assert run(7, "FC", busy) == ["C"]  # 我方 16:00 結束，下一筆 16:03 開始


def test_same_user_no_buffer():
    busy = [Occupancy(tid("F"), USER, local(D, "12:00"), local(D, "14:00"))]
    assert run(7, "F", busy) == ["F"]
    assert not is_conflict(
        busy[0], user_id=USER, start_at=local(D, "14:00"), end_at=local(D, "16:00")
    )


def test_real_overlap_always_conflicts():
    busy = [Occupancy(tid("F"), USER, local(D, "15:00"), local(D, "17:00"))]
    with pytest.raises(NoTableAvailable):
        run(7, "F", busy)


def test_keep_preferred_table_when_still_free():
    assert run(3, "ABG", preferred_ids=[tid("B")]) == ["B"]  # 否則會選 G


def test_preferred_dropped_when_too_small():
    assert run(9, "AC", preferred_ids=[tid("A")]) == ["C"]


def test_batch_counts_previous_slot_as_busy():
    slots = [(local(D, "14:00"), local(D, "16:00")), (local(D, "15:00"), local(D, "17:00"))]
    got = allocate_batch(slots, 7, tables("F", "C"), LINKS, [], user_id=USER)
    assert [[t.table_code for t in g] for g in got] == [["F"], ["C"]]


def test_batch_fails_when_any_slot_has_no_table():
    slots = [(local(D, "14:00"), local(D, "16:00")), (local(D, "15:00"), local(D, "17:00"))]
    with pytest.raises(NoTableAvailable):
        allocate_batch(slots, 7, tables("F"), LINKS, [], user_id=USER)


def test_all_fixture_tables_exist():
    assert len(TABLES) == 9
