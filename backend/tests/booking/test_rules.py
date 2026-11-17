from datetime import date, time
from decimal import Decimal

import pytest

from app.domains.booking.errors import BookingRuleError
from app.domains.booking.rules import (
    BusinessHours,
    ClosingHours,
    Slot,
    add_months,
    db_weekday,
    validate_batch,
    validate_slot,
)
from tests.booking.support import local

NOW = local("2026-11-16", "10:00")  # 星期一
# 0=星期日；週二（2）未設定＝公休
HOURS = [BusinessHours(w, time(13), time(22)) for w in (0, 1, 3, 4, 5, 6)]


def slot(day: str, start: str, end: str) -> Slot:
    return Slot(local(day, start), local(day, end))


def check(s: Slot, *, now=NOW, closings=()) -> None:
    validate_slot(s, now=now, min_hours=Decimal(1), business_hours=HOURS, closings=closings)


def code_of(s: Slot, **kw) -> str:
    with pytest.raises(BookingRuleError) as exc:
        check(s, **kw)
    return exc.value.code


def test_weekday_sunday_is_zero():
    assert db_weekday(local("2026-11-22", "14:00")) == 0  # 星期日
    assert db_weekday(local("2026-11-17", "14:00")) == 2  # 星期二


def test_closed_day():
    assert code_of(slot("2026-11-17", "14:00", "16:00")) == "BOOKING_CLOSED_DAY"


def test_outside_business_hours():
    assert code_of(slot("2026-11-18", "12:00", "14:00")) == "BOOKING_OUTSIDE_BUSINESS_HOURS"
    assert code_of(slot("2026-11-18", "21:00", "23:00")) == "BOOKING_OUTSIDE_BUSINESS_HOURS"


def test_within_business_hours():
    check(slot("2026-11-18", "14:00", "16:00"))


CLOSING = [ClosingHours(date(2026, 11, 18), time(12), time(14))]


def test_closing_overlap():
    assert (
        code_of(slot("2026-11-18", "13:00", "15:00"), closings=CLOSING) == "BOOKING_CLOSING_PERIOD"
    )


def test_closing_spanned():
    closing = [ClosingHours(date(2026, 11, 18), time(15), time(17))]
    assert (
        code_of(slot("2026-11-18", "14:00", "18:00"), closings=closing) == "BOOKING_CLOSING_PERIOD"
    )


def test_closing_adjacent_is_allowed():
    check(slot("2026-11-18", "14:00", "16:00"), closings=CLOSING)


def test_closing_whole_day():
    whole = [ClosingHours(date(2026, 11, 18), None, None)]
    assert code_of(slot("2026-11-18", "14:00", "16:00"), closings=whole) == "BOOKING_CLOSED_DAY"


def test_too_short():
    assert code_of(slot("2026-11-18", "14:00", "14:45")) == "BOOKING_TOO_SHORT"


def test_non_round_start_rejected():
    assert code_of(slot("2026-11-18", "14:10", "16:40")) == "BOOKING_TIME_GRANULARITY"


def test_cross_day_rejected():
    s = Slot(local("2026-11-18", "20:00"), local("2026-11-19", "01:00"))
    assert code_of(s) == "BOOKING_CROSS_DAY"


def test_start_in_past():
    now = local("2026-11-18", "13:20")
    assert code_of(slot("2026-11-18", "13:00", "15:00"), now=now) == "BOOKING_IN_PAST"


def test_later_today_allowed():
    check(slot("2026-11-18", "13:30", "15:00"), now=local("2026-11-18", "13:20"))


def test_three_calendar_month_limit():
    assert code_of(slot("2027-02-17", "14:00", "16:00")) == "BOOKING_TOO_FAR"
    check(slot("2027-02-15", "14:00", "16:00"))  # 上限當天（2027-02-16）前一日的營業日


def test_add_months_clamps_month_end():
    assert add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)


def test_round_start_end_accepted():
    check(slot("2026-11-18", "14:00", "16:00"))


def test_half_hour_accepted():
    check(slot("2026-11-18", "14:30", "17:00"))


def test_end_minute_not_round_rejected():
    assert code_of(slot("2026-11-18", "14:00", "16:15")) == "BOOKING_TIME_GRANULARITY"


def test_batch_ok():
    validate_batch(
        [slot("2026-11-18", "14:00", "16:00"), slot("2026-11-18", "18:00", "20:00")], [4, 4]
    )


def test_batch_overlap_rejected():
    with pytest.raises(BookingRuleError) as exc:
        validate_batch(
            [slot("2026-11-18", "14:00", "16:00"), slot("2026-11-18", "15:00", "17:00")], [4, 4]
        )
    assert exc.value.code == "BOOKING_SLOTS_OVERLAP"


def test_batch_party_size_must_match():
    with pytest.raises(BookingRuleError) as exc:
        validate_batch(
            [slot("2026-11-18", "14:00", "16:00"), slot("2026-11-18", "18:00", "20:00")], [4, 5]
        )
    assert exc.value.code == "BOOKING_PARTY_SIZE_MISMATCH"
