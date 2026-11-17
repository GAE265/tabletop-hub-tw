from decimal import Decimal

from app.domains.booking.pricing import PricingRules, billable_hours, quote
from tests.booking.support import local

RULES = PricingRules(Decimal(60), Decimal(80), Decimal(1), Decimal(5), Decimal(1))


def q(day, start, end, party):
    return quote(local(day, start), local(day, end), party, RULES)


def test_weekday_whole_hours():
    r = q("2026-11-18", "14:00", "16:00", 4)  # 星期三
    assert r.venue_fee == 480 and r.drink_reminder is None and not r.is_weekend


def test_round_up_partial_hour():
    r = q("2026-11-18", "14:00", "15:15", 2)
    assert r.billable_hours == 2 and r.venue_fee == 240


def test_capped_at_five_hours_on_weekend():
    r = q("2026-11-21", "13:00", "21:00", 3)  # 星期六
    assert r.billable_hours == 5 and r.venue_fee == 1200


def test_weekend_has_drink_reminder():
    assert q("2026-11-21", "14:00", "16:00", 2).drink_reminder
    assert q("2026-11-22", "14:00", "16:00", 2).is_weekend  # 星期日


def test_monday_no_reminder():
    assert q("2026-11-16", "14:00", "16:00", 2).drink_reminder is None


def test_actual_usage_differs_from_booked():
    hours = billable_hours(local("2026-11-18", "14:00"), local("2026-11-18", "16:20"), RULES)
    assert hours == 3
