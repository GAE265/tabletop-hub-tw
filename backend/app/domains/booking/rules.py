"""訂位時間規則（純函式，不連資料庫）。

所有判斷都先轉成公司時區（Asia/Taipei）。weekday 沿用資料庫的 0=星期日。
"""

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domains.booking.errors import BookingRuleError

COMPANY_TZ = ZoneInfo("Asia/Taipei")
MAX_ADVANCE_MONTHS = 3


@dataclass(frozen=True)
class BusinessHours:
    weekday: int  # 0=星期日
    open_time: time
    close_time: time


@dataclass(frozen=True)
class ClosingHours:
    closing_date: date
    start_time: time | None  # start_time 與 end_time 同為 None 代表整天公休
    end_time: time | None


@dataclass(frozen=True)
class Slot:
    start_at: datetime
    end_at: datetime


def to_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime 必須帶時區")
    return value.astimezone(COMPANY_TZ)


def db_weekday(value: datetime) -> int:
    """公司時區的星期，0=星期日。"""
    return to_local(value).isoweekday() % 7


def add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def validate_same_day(slot: Slot) -> None:
    if to_local(slot.start_at).date() != to_local(slot.end_at).date():
        raise BookingRuleError("BOOKING_CROSS_DAY", "訂位不可跨日")


def validate_duration(slot: Slot, min_hours: Decimal) -> None:
    if slot.end_at <= slot.start_at:
        raise BookingRuleError("BOOKING_INVALID_RANGE", "結束時間必須晚於開始時間")
    minutes = Decimal(str((slot.end_at - slot.start_at).total_seconds())) / 60
    if minutes < min_hours * 60:
        raise BookingRuleError("BOOKING_TOO_SHORT", f"訂位至少 {min_hours.normalize()} 小時")


def validate_lead_time(slot: Slot, now: datetime) -> None:
    if slot.start_at < now:
        raise BookingRuleError("BOOKING_IN_PAST", "開始時間不可早於現在")
    limit = add_months(to_local(now).date(), MAX_ADVANCE_MONTHS)
    if to_local(slot.start_at).date() > limit:
        raise BookingRuleError("BOOKING_TOO_FAR", f"最多只能預約 {MAX_ADVANCE_MONTHS} 個月內")


def validate_business_hours(slot: Slot, hours: Sequence[BusinessHours]) -> None:
    weekday = db_weekday(slot.start_at)
    today = next((h for h in hours if h.weekday == weekday), None)
    if today is None:
        raise BookingRuleError("BOOKING_CLOSED_DAY", "該日未營業")
    start, end = to_local(slot.start_at).time(), to_local(slot.end_at).time()
    if start < today.open_time or end > today.close_time:
        raise BookingRuleError(
            "BOOKING_OUTSIDE_BUSINESS_HOURS",
            "訂位時間超出營業時間",
            {"open_time": today.open_time.isoformat(), "close_time": today.close_time.isoformat()},
        )


def validate_closings(slot: Slot, closings: Sequence[ClosingHours]) -> None:
    local_start, local_end = to_local(slot.start_at), to_local(slot.end_at)
    for closing in closings:
        if closing.closing_date != local_start.date():
            continue
        if closing.start_time is None or closing.end_time is None:
            raise BookingRuleError("BOOKING_CLOSED_DAY", "該日公休")
        if local_start.time() < closing.end_time and local_end.time() > closing.start_time:
            raise BookingRuleError("BOOKING_CLOSING_PERIOD", "訂位時間與公休時段重疊")


def validate_slot(
    slot: Slot,
    *,
    now: datetime,
    min_hours: Decimal,
    business_hours: Sequence[BusinessHours],
    closings: Sequence[ClosingHours],
) -> None:
    validate_duration(slot, min_hours)
    validate_same_day(slot)
    validate_time_granularity(slot)
    validate_lead_time(slot, now)
    validate_business_hours(slot, business_hours)
    validate_closings(slot, closings)


def validate_time_granularity(slot: Slot) -> None:
    """開始與結束時間的分鐘數必須為 0 或 30。"""
    start_minute = to_local(slot.start_at).minute
    end_minute = to_local(slot.end_at).minute
    if start_minute not in (0, 30):
        raise BookingRuleError(
            "BOOKING_TIME_GRANULARITY",
            f"開始時間的分鐘必須為 0 或 30，目前為 {start_minute}",
        )
    if end_minute not in (0, 30):
        raise BookingRuleError(
            "BOOKING_TIME_GRANULARITY",
            f"結束時間的分鐘必須為 0 或 30，目前為 {end_minute}",
        )


def validate_batch(slots: Sequence[Slot], party_sizes: Sequence[int]) -> None:
    if not slots:
        raise BookingRuleError("BOOKING_EMPTY_BATCH", "至少要有一個時段")
    if len(set(party_sizes)) > 1:
        raise BookingRuleError("BOOKING_PARTY_SIZE_MISMATCH", "各時段人數必須相同")
    ordered = sorted(slots, key=lambda s: s.start_at)
    for prev, nxt in zip(ordered, ordered[1:], strict=False):
        if nxt.start_at < prev.end_at:
            raise BookingRuleError("BOOKING_SLOTS_OVERLAP", "批次內的時段不可互相重疊")
