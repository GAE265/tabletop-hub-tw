import secrets
import uuid
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

from psycopg.errors import ExclusionViolation
from sqlalchemy import Select, delete, func, insert, select, update
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
    BookingNotification,
    BookingPricingRule,
    BookingReservation,
    BookingReservationLog,
    BookingReservationTable,
    BookingShop,
    BookingTable,
    BookingTableLink,
)
from app.domains.booking.pricing import PricingRules
from app.domains.booking.records import (
    BookingSummary,
    NotificationRecord,
    NotificationView,
    ReservationRecord,
    ShopRef,
    TableRef,
    TableStatus,
    UserInfo,
)
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

    def get_shop_name(self, shop_id: uuid.UUID) -> str:
        name = self.session.scalar(select(BookingShop.name).where(BookingShop.id == shop_id))
        return name or ""

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
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[list[ReservationRecord], int]:
        conds = [BookingReservation.user_id == user_id]
        if status is not None:
            conds.append(BookingReservation.status == status)
        if from_date is not None:
            conds.append(BookingReservation.end_at > from_date)
        if to_date is not None:
            conds.append(BookingReservation.start_at < to_date)
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

    # --- 座位圖 ---

    def get_tables_with_status(
        self,
        shop_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
        floor: int | None = None,
    ) -> list["TableStatus"]:
        """查詢指定店家的桌子及其在時間範圍內的佔用狀態。

        回傳所有啟用中的桌子（可選過濾樓層），
        並附上該時段內 confirmed/seated 訂位的摘要（含 user_id 供權限過濾）。
        """

        # 子查詢：時間範圍內有效佔用的 reservation_tables
        occupied_sub = (
            select(
                BookingReservationTable.table_id,
                BookingReservation.id,
                BookingReservation.reservation_code,
                BookingReservation.user_id,
                BookingReservation.start_at,
                BookingReservation.end_at,
                BookingReservation.party_size,
                BookingReservation.status,
            )
            .join(
                BookingReservation,
                (BookingReservation.shop_id == BookingReservationTable.shop_id)
                & (BookingReservation.id == BookingReservationTable.reservation_id),
            )
            .where(
                BookingReservationTable.shop_id == shop_id,
                BookingReservationTable.is_active,
                BookingReservationTable.start_at < end_at,
                BookingReservationTable.end_at > start_at,
                BookingReservation.status.in_(ACTIVE_STATUSES),
            )
            .subquery()
        )

        # 主查詢：所有啟用中的桌子 LEFT JOIN 佔用資訊
        base_query = (
            select(
                BookingTable.id,
                BookingTable.table_code,
                BookingTable.name,
                BookingTable.max_capacity,
                BookingTable.floor,
                BookingTable.x,
                BookingTable.y,
                BookingTable.width,
                BookingTable.height,
                BookingTable.shape,
                occupied_sub.c.id,
                occupied_sub.c.reservation_code,
                occupied_sub.c.user_id,
                occupied_sub.c.start_at,
                occupied_sub.c.end_at,
                occupied_sub.c.party_size,
                occupied_sub.c.status,
            )
            .outerjoin(
                occupied_sub,
                BookingTable.id == occupied_sub.c.table_id,
            )
            .where(
                BookingTable.shop_id == shop_id,
                BookingTable.is_active,
            )
        )

        if floor is not None:
            base_query = base_query.where(BookingTable.floor == floor)

        base_query = base_query.order_by(BookingTable.floor, BookingTable.table_code)

        rows = self.session.execute(base_query).all()

        # 一個桌子可能關聯多筆訂位（LEFT JOIN），只取第一筆
        results: list[TableStatus] = []
        seen: set[int] = set()
        for row in rows:
            tid = row[0]
            if tid in seen:
                continue
            seen.add(tid)
            booking = None
            if row[10] is not None:
                booking = BookingSummary(
                    id=row[10],
                    reservation_code=row[11],
                    user_id=row[12],
                    start_at=row[13],
                    end_at=row[14],
                    party_size=row[15],
                    status=row[16],
                )
            results.append(
                TableStatus(
                    id=tid,
                    table_code=row[1],
                    name=row[2],
                    max_capacity=row[3],
                    floor=row[4],
                    x=row[5],
                    y=row[6],
                    width=row[7],
                    height=row[8],
                    shape=row[9],
                    status="unavailable" if booking else "available",
                    booking=booking,
                )
            )

        return results

    # --- 通知（add-booking-notifications）---

    def list_shop_staff_ids(self, shop_id: uuid.UUID) -> list[uuid.UUID]:
        """該店所有店家人員的 id（讀共用表 auth_users，不改結構）。"""
        return list(
            self.session.scalars(
                select(AuthUser.id)
                .where(AuthUser.role == "shop_staff", AuthUser.shop_id == shop_id)
                .order_by(AuthUser.id)
            )
        )

    def add_notifications(
        self,
        reservation_id: int,
        recipients: Sequence[tuple[uuid.UUID, str]],
        created_at: datetime,
    ) -> None:
        """在目前的交易裡寫入通知；recipients 為（使用者 id，通知種類）。"""
        if recipients:
            self.session.execute(
                insert(BookingNotification),
                [
                    {
                        "user_id": user_id,
                        "reservation_id": reservation_id,
                        "type": type_,
                        "created_at": created_at,
                    }
                    for user_id, type_ in recipients
                ],
            )

    def list_notifications(
        self, user_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[NotificationView], int, int]:
        """回傳（這一頁的通知，總數，未讀數），新的在前。"""
        mine = BookingNotification.user_id == user_id
        total = self.session.scalar(select(func.count()).where(mine)) or 0
        unread = (
            self.session.scalar(
                select(func.count()).where(mine, BookingNotification.read_at.is_(None))
            )
            or 0
        )
        rows = self.session.execute(
            _notification_statement()
            .where(mine)
            .order_by(BookingNotification.created_at.desc(), BookingNotification.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [NotificationView(**row._mapping) for row in rows], total, unread

    def find_notification(self, notification_id: uuid.UUID) -> NotificationRecord | None:
        row = self.session.execute(
            select(BookingNotification.id, BookingNotification.user_id).where(
                BookingNotification.id == notification_id
            )
        ).one_or_none()
        return None if row is None else NotificationRecord(**row._mapping)

    def mark_read(self, notification_id: uuid.UUID, read_at: datetime) -> None:
        """只在未讀時寫入，重複標成已讀不改時間。"""
        self.session.execute(
            update(BookingNotification)
            .where(
                BookingNotification.id == notification_id,
                BookingNotification.read_at.is_(None),
            )
            .values(read_at=read_at)
        )

    def get_notification(self, notification_id: uuid.UUID) -> NotificationView | None:
        row = self.session.execute(
            _notification_statement().where(BookingNotification.id == notification_id)
        ).one_or_none()
        return None if row is None else NotificationView(**row._mapping)


def _notification_statement() -> Select:
    """通知加上訂位目前的代碼、店名、時間與人數。"""
    return (
        select(
            BookingNotification.id,
            BookingNotification.type,
            BookingNotification.reservation_id,
            BookingReservation.reservation_code,
            BookingShop.name.label("shop_name"),
            BookingReservation.start_at,
            BookingReservation.end_at,
            BookingReservation.party_size,
            BookingNotification.read_at,
            BookingNotification.created_at,
        )
        .join(BookingReservation, BookingReservation.id == BookingNotification.reservation_id)
        .join(BookingShop, BookingShop.id == BookingReservation.shop_id)
    )
