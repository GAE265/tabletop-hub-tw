"""場地費計算（純函式）。費率與規則值由呼叫端從 booking_pricing_rules 讀出。"""

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domains.booking.rules import db_weekday

WEEKEND_DRINK_REMINDER = "週末每位客人至少需點一杯飲料，點心不能代替。"


@dataclass(frozen=True)
class PricingRules:
    weekday_hourly_fee: Decimal
    weekend_hourly_fee: Decimal
    rounding_unit_hours: Decimal
    max_hours: Decimal
    min_hours: Decimal


@dataclass(frozen=True)
class FeeQuote:
    billable_hours: Decimal
    hourly_fee: Decimal
    venue_fee: Decimal
    is_weekend: bool
    drink_reminder: str | None


def is_weekend(value: datetime) -> bool:
    return db_weekday(value) in (0, 6)


def billable_hours(start_at: datetime, end_at: datetime, rules: PricingRules) -> Decimal:
    minutes = Decimal(str((end_at - start_at).total_seconds())) / 60
    units = math.ceil(minutes / 60 / rules.rounding_unit_hours)
    return min(units * rules.rounding_unit_hours, rules.max_hours)


def quote(start_at: datetime, end_at: datetime, party_size: int, rules: PricingRules) -> FeeQuote:
    weekend = is_weekend(start_at)
    rate = rules.weekend_hourly_fee if weekend else rules.weekday_hourly_fee
    hours = billable_hours(start_at, end_at, rules)
    return FeeQuote(
        billable_hours=hours,
        hourly_fee=rate,
        venue_fee=party_size * hours * rate,
        is_weekend=weekend,
        drink_reminder=WEEKEND_DRINK_REMINDER if weekend else None,
    )
