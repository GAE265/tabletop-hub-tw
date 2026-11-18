import secrets
import uuid
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

from psycopg.errors import ExclusionViolation
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import SessionRepository
from app.core.errors import AppError
from app.domains.auth.models import AuthUser
from app.domains.booking.allocation import Occupancy, TableInfo, TableLink
from app.domains.booking.errors import TableConflict
from app.domains.booking.models import (
    BookingBusinessHours,
    BookingClosingHours,
    BookingPricingRule,
    BookingReservation,
    BookingReservationLog,
    BookingReservationTable,
    BookingShop,
    BookingTable,
    BookingTableLink,
)
from app.domains.booking.pricing import PricingRules
from app.domains.booking.records import ReservationRecord, ShopRef, TableRef, UserInfo
from app.domains.booking.rules import BusinessHours, ClosingHours

ACTIVE_STATUSES = ("confirmed", "seated")
# 查桌位占用時，往前後多看的範圍，涵蓋緩衝時間
OCCUPANCY_WINDOW = timedelta(hours=1)
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

_RULE_CODES = {
    "WEEKDAY_HOURLY_FEE": "weekday_hourly_fee",
    "WEEKEND_HOURLY_FEE": "weekend_hourly_fee",
    "BILLING_ROUNDING_UNIT_HOURS": "rounding_unit_hours",
    "BILLING_MAX_HOURS": "max_hours",
    "BOOKING_MIN_HOURS": "min_hours",
}


def _is_exclusion_violation(error: IntegrityError) -> bool:
    return isinstance(error.orig, ExclusionViolation)


class BookingRepository(SessionRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # --- 讀取設定資料 ---

    def get_user(self, user_id: uuid.UUID) -> UserInfo | None:
        row = self.session.get(AuthUser, user_id)
        if row is None:
            return None
        return UserInfo(row.id, row.display_name, row.role, row.shop_id, row.phone)

    def shop_exists(self, shop_id: uuid.UUID) -> bool:
        return self.session.get(BookingShop, shop_id) is not None

    def get_shop(self, shop_id: uuid.UUID) -> ShopRef | None:
        """依 id 讀一間店家的名稱（只讀，給其他 domain 使用）；不存在回 None。"""
        row = self.session.get(BookingShop, shop_id)
        return None if row is None else ShopRef(row.id, row.name)

    def list_shops(self) -> list[ShopRef]:
        rows = self.session.scalars(
            select(BookingShop).where(BookingShop.is_active).order_by(BookingShop.name)
        )
        return [ShopRef(r.id, r.name) for r in rows]

    def get_business_hours(self, shop_id: uuid.UUID) -> list[BusinessHours]:
        rows = self.session.scalars(
            select(BookingBusinessHours).where(BookingBusinessHours.shop_id == shop_id)
        )
        return [BusinessHours(r.weekday, r.open_time, r.close_time) for r in rows]

    def get_closings(self, shop_id: uuid.UUID, days: Iterable[date]) -> list[ClosingHours]:
        rows = self.session.scalars(
            select(BookingClosingHours).where(
                BookingClosingHours.shop_id == shop_id,
                BookingClosingHours.closing_date.in_(list(days)),
            )
        )
        return [ClosingHours(r.closing_date, r.start_time, r.end_time) for r in rows]

    def get_pricing_rules(self, shop_id: uuid.UUID) -> PricingRules:
        rows = self.session.scalars(
            select(BookingPricingRule).where(
                BookingPricingRule.shop_id == shop_id, BookingPricingRule.is_active
            )
        )
        values: dict[str, Decimal] = {
            _RULE_CODES[r.rule_code]: r.price for r in rows if r.rule_code in _RULE_CODES
        }
        missing = set(_RULE_CODES.values()) - values.keys()
        if missing:
            raise AppError(
                503,
                "BOOKING_PRICING_NOT_CONFIGURED",
                "店家尚未設定費率規則",
                {"missing": sorted(missing)},
            )
        return PricingRules(**values)

    def list_tables(self, shop_id: uuid.UUID) -> list[TableInfo]:
        rows = self.session.scalars(
            select(BookingTable).where(BookingTable.shop_id == shop_id, BookingTable.is_active)
        )
        return [TableInfo(r.id, r.table_code, r.min_capacity, r.max_capacity) for r in rows]

    def list_links(self, shop_id: uuid.UUID) -> list[TableLink]:
        rows = self.session.scalars(
            select(BookingTableLink).where(BookingTableLink.shop_id == shop_id)
        )
        # 舊庫的關係表沒有唯一限制，可能有重複或反向重複；同一對桌位只要有一筆可併桌就算可併桌
        merged: dict[frozenset[int], tuple[int, int, bool]] = {}
        for r in rows:
            if r.table_a_id == r.table_b_id:
                continue
            key = frozenset((r.table_a_id, r.table_b_id))
            a, b, combinable = merged.get(key, (r.table_a_id, r.table_b_id, False))
            merged[key] = (a, b, combinable or r.is_combinable)
        return [TableLink(a, b, c) for a, b, c in merged.values()]

    # --- 訂位查詢 ---

    def list_occupancies(
        self,
        shop_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_reservation_ids: Sequence[int] = (),
    ) -> list[Occupancy]:
        rt, res = BookingReservationTable, BookingReservation
        rows = self.session.execute(
            select(rt.table_id, res.user_id, rt.start_at, rt.end_at)
            .join(res, res.id == rt.reservation_id)
            .where(
                rt.shop_id == shop_id,
                rt.is_active,
                res.status.in_(ACTIVE_STATUSES),
                rt.start_at < end_at + OCCUPANCY_WINDOW,
                rt.end_at > start_at - OCCUPANCY_WINDOW,
                res.id.not_in(list(exclude_reservation_ids)),
            )
        )
        return [Occupancy(*row) for row in rows]

    def _overlapping(
        self, shop_id, start_at, end_at, exclude, *conditions
    ) -> list[ReservationRecord]:
        res = BookingReservation
        rows = self.session.scalars(
            select(res)
            .outerjoin(AuthUser, AuthUser.id == res.user_id)
            .where(
                res.shop_id == shop_id,
                res.status.in_(ACTIVE_STATUSES),
                res.start_at < end_at,
                res.end_at > start_at,
                res.id.not_in(list(exclude)),
                *conditions,
            )
            .order_by(res.start_at)
        )
        return [self._record(r) for r in rows]

    def find_overlapping_by_phone(
        self, shop_id, phone: str, start_at, end_at, exclude: Sequence[int] = ()
    ) -> list[ReservationRecord]:
        return self._overlapping(shop_id, start_at, end_at, exclude, AuthUser.phone == phone)

    def find_overlapping_by_user(
        self, shop_id, user_id: uuid.UUID, start_at, end_at, exclude: Sequence[int] = ()
    ) -> list[ReservationRecord]:
        return self._overlapping(
            shop_id, start_at, end_at, exclude, BookingReservation.user_id == user_id
        )

    def get_reservation(self, reservation_id: int) -> ReservationRecord | None:
        row = self.session.get(BookingReservation, reservation_id)
        return None if row is None else self._record(row)

    def list_for_user(
        self,
        user_id: uuid.UUID,
        page: int,
        page_size: int,
        *,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[list[ReservationRecord], int]:
        conds = [BookingReservation.user_id == user_id]
        if status is not None:
            conds.append(BookingReservation.status == status)
        if from_date is not None:
            conds.append(func.date(BookingReservation.start_at) >= from_date)
        if to_date is not None:
            conds.append(func.date(BookingReservation.start_at) <= to_date)
        return self._page(tuple(conds), page, page_size, newest=True)

    def list_for_shop(
        self, shop_id: uuid.UUID, start_at: datetime, end_at: datetime, page: int, page_size: int
    ) -> tuple[list[ReservationRecord], int]:
        cond = (
            BookingReservation.shop_id == shop_id,
            BookingReservation.start_at < end_at,
            BookingReservation.end_at > start_at,
        )
        return self._page(cond, page, page_size, newest=False)

    def _page(self, cond, page: int, page_size: int, *, newest: bool):
        conds = cond if isinstance(cond, tuple) else (cond,)
        total = self.session.scalar(
            select(func.count()).select_from(BookingReservation).where(*conds)
        )
        order = BookingReservation.start_at.desc() if newest else BookingReservation.start_at
        rows = self.session.scalars(
            select(BookingReservation)
            .where(*conds)
            .order_by(order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [self._record(r) for r in rows], total or 0

    # --- 寫入 ---

    def _new_code(self, shop_id: uuid.UUID) -> str:
        while True:
            code = "BK" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
            exists = self.session.scalar(
                select(func.count())
                .select_from(BookingReservation)
                .where(
                    BookingReservation.shop_id == shop_id,
                    BookingReservation.reservation_code == code,
                )
            )
            if not exists:
                return code

    def _flush(self) -> None:
        try:
            self.session.flush()
        except IntegrityError as error:
            if _is_exclusion_violation(error):
                raise TableConflict() from error
            raise

    def create_reservation(
        self,
        *,
        shop_id: uuid.UUID,
        user_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
        party_size: int,
        special_requests: str | None,
        table_ids: Sequence[int],
        source: str = "online",
    ) -> ReservationRecord:
        row = BookingReservation(
            shop_id=shop_id,
            reservation_code=self._new_code(shop_id),
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
            party_size=party_size,
            status="confirmed",
            source=source,
            special_requests=special_requests,
        )
        self.session.add(row)
        self.session.flush()
        for table_id in table_ids:
            self.session.add(
                BookingReservationTable(
                    shop_id=shop_id,
                    reservation_id=row.id,
                    table_id=table_id,
                    start_at=start_at,
                    end_at=end_at,
                )
            )
        self._flush()
        return self._record(row)

    def replace_tables(
        self,
        reservation_id: int,
        table_ids: Sequence[int],
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        """換成新的一組桌位（含時間）。先刪掉這筆訂位的桌位列，再寫入新的。"""
        row = self.session.get(BookingReservation, reservation_id)
        rt = BookingReservationTable
        self.session.execute(delete(rt).where(rt.reservation_id == reservation_id))
        for table_id in table_ids:
            self.session.add(
                rt(
                    shop_id=row.shop_id,
                    reservation_id=reservation_id,
                    table_id=table_id,
                    start_at=start_at,
                    end_at=end_at,
                )
            )
        self._flush()

    def set_tables_active(self, reservation_id: int, active: bool) -> None:
        rt = BookingReservationTable
        try:
            self.session.execute(
                update(rt).where(rt.reservation_id == reservation_id).values(is_active=active)
            )
            self.session.flush()
        except IntegrityError as error:
            if _is_exclusion_violation(error):
                raise TableConflict() from error
            raise

    def update_reservation(self, reservation_id: int, **fields: object) -> ReservationRecord:
        row = self.session.get(BookingReservation, reservation_id)
        for key, value in fields.items():
            setattr(row, key, value)
        row.updated_at = func.now()
        self._flush()
        self.session.refresh(row)
        return self._record(row)

    def add_log(
        self,
        *,
        reservation: ReservationRecord,
        action: str,
        old_data: dict | None,
        new_data: dict | None,
        operator_type: str,
        operator_id: uuid.UUID | None,
        operator_name: str | None,
    ) -> None:
        self.session.add(
            BookingReservationLog(
                shop_id=reservation.shop_id,
                reservation_id=reservation.id,
                action=action,
                old_data=old_data,
                new_data=new_data,
                operator_type=operator_type,
                operator_id=None if operator_id is None else str(operator_id),
                operator_name=operator_name,
            )
        )
        self.session.flush()

    def _record(self, row: BookingReservation) -> ReservationRecord:
        tables = self.session.execute(
            select(BookingTable.id, BookingTable.table_code)
            .join(BookingReservationTable, BookingReservationTable.table_id == BookingTable.id)
            .where(BookingReservationTable.reservation_id == row.id)
            .order_by(BookingTable.table_code)
        ).all()
        return ReservationRecord(
            id=row.id,
            shop_id=row.shop_id,
            reservation_code=row.reservation_code,
            user_id=row.user_id,
            start_at=row.start_at,
            end_at=row.end_at,
            party_size=row.party_size,
            status=row.status,
            source=row.source,
            special_requests=row.special_requests,
            seated_at=row.seated_at,
            completed_at=row.completed_at,
            final_fee=row.final_fee,
            cancelled_at=row.cancelled_at,
            cancel_reason=row.cancel_reason,
            created_at=row.created_at,
            tables=[TableRef(*t) for t in tables],
        )
