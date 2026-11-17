import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, TypeVar

from app.core.auth import CurrentUser, require_role
from app.core.errors import AppError, PermissionDenied
from app.domains.booking import pricing
from app.domains.booking.allocation import allocate, is_conflict
from app.domains.booking.errors import BookingRuleError, NoTableAvailable, TableConflict
from app.domains.booking.records import ReservationRecord
from app.domains.booking.repository import BookingRepository
from app.domains.booking.rules import Slot, to_local, validate_slot
from app.domains.booking.schemas import (
    BookingCreate,
    BookingList,
    BookingOut,
    BookingPatch,
    BookingQuote,
    BookingQuoteRequest,
    FeeOut,
    ShopList,
    ShopOut,
    TableOut,
)

T = TypeVar("T")

REPLACED_REASON = "被新訂位取代"
MERGED_REASON = "與其他訂位合併"
MODIFIED_NOTICE = "訂位已修改，請確認新的時間與桌位。"


def _status_invalid(current: str) -> AppError:
    return AppError(
        409, "BOOKING_STATUS_INVALID", "目前的訂位狀態不允許此操作", {"status": current}
    )


class BookingService:
    def __init__(
        self,
        repository: BookingRepository,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.repo = repository
        self.now = now

    # --- 共用 ---

    def _atomic(self, work: Callable[[], T]) -> T:
        """單一交易。同桌時間重疊（exclusion constraint）就整筆回滾並重做一次，仍失敗回桌位不足。"""
        for attempt in (1, 2):
            try:
                with self.repo.transaction():
                    return work()
            except TableConflict:
                if attempt == 2:
                    raise NoTableAvailable() from None
        raise AssertionError("unreachable")

    def _load(self, booking_id: int) -> ReservationRecord:
        record = self.repo.get_reservation(booking_id)
        if record is None:
            raise AppError(404, "BOOKING_NOT_FOUND", "找不到訂位")
        return record

    @staticmethod
    def _assert_access(user: CurrentUser, record: ReservationRecord) -> None:
        """玩家只能動自己的訂位；店員只能動自己店家的訂位；管理員不受限。"""
        if user.role == "admin":
            return
        if user.role == "shop_staff" and user.shop_id == record.shop_id:
            return
        if user.role == "player" and user.id == record.user_id:
            return
        raise PermissionDenied()

    @staticmethod
    def _assert_shop(user: CurrentUser, shop_id: uuid.UUID) -> None:
        if user.role == "shop_staff" and user.shop_id != shop_id:
            raise PermissionDenied()

    def _validate(self, shop_id: uuid.UUID, slots: list[Slot], rules: pricing.PricingRules) -> None:
        days = {to_local(s.start_at).date() for s in slots} | {
            to_local(s.end_at).date() for s in slots
        }
        hours = self.repo.get_business_hours(shop_id)
        closings = self.repo.get_closings(shop_id, days)
        now = self.now()
        for slot in slots:
            validate_slot(
                slot,
                now=now,
                min_hours=rules.min_hours,
                business_hours=hours,
                closings=closings,
            )

    def _fee(self, start_at: datetime, end_at: datetime, party: int, rules) -> FeeOut:
        q = pricing.quote(start_at, end_at, party, rules)
        cents = Decimal("0.01")
        return FeeOut(
            billable_hours=q.billable_hours,
            hourly_fee=q.hourly_fee.quantize(cents),
            venue_fee=q.venue_fee.quantize(cents),
            drink_reminder=q.drink_reminder,
        )

    def _out(
        self, record: ReservationRecord, rules: pricing.PricingRules, notice: str | None = None
    ) -> BookingOut:
        return BookingOut(
            id=record.id,
            reservation_code=record.reservation_code,
            shop_id=record.shop_id,
            user_id=record.user_id,
            start_at=record.start_at,
            end_at=record.end_at,
            party_size=record.party_size,
            status=record.status,
            source=record.source,
            special_requests=record.special_requests,
            tables=[TableOut(id=t.id, table_code=t.table_code) for t in record.tables],
            estimated_fee=self._fee(record.start_at, record.end_at, record.party_size, rules),
            seated_at=record.seated_at,
            completed_at=record.completed_at,
            final_fee=record.final_fee,
            cancelled_at=record.cancelled_at,
            cancel_reason=record.cancel_reason,
            notice=notice,
        )

    def _log(
        self,
        user: CurrentUser,
        record: ReservationRecord,
        action: str,
        old: dict[str, Any] | None,
        new: dict[str, Any] | None,
    ) -> None:
        info = self.repo.get_user(user.id)
        self.repo.add_log(
            reservation=record,
            action=action,
            old_data=old,
            new_data=new,
            operator_type="customer" if user.role == "player" else "staff",
            operator_id=user.id,
            operator_name=info.display_name if info else None,
        )

    @staticmethod
    def _snapshot(record: ReservationRecord) -> dict[str, Any]:
        return {
            "status": record.status,
            "start_at": record.start_at.isoformat(),
            "end_at": record.end_at.isoformat(),
            "party_size": record.party_size,
            "tables": [t.table_code for t in record.tables],
        }

    def _release(
        self,
        user: CurrentUser,
        record: ReservationRecord,
        status: str,
        reason: str | None,
        action: str,
    ) -> ReservationRecord:
        """取消或 no_show：立即釋放桌位。"""
        self.repo.set_tables_active(record.id, False)
        updated = self.repo.update_reservation(
            record.id, status=status, cancelled_at=self.now(), cancel_reason=reason
        )
        self._log(user, updated, action, self._snapshot(record), self._snapshot(updated))
        return updated

    # --- 預估費用 ---

    def quote(self, user: CurrentUser, req: BookingQuoteRequest) -> BookingQuote:
        if not self.repo.shop_exists(req.shop_id):
            raise AppError(404, "BOOKING_SHOP_NOT_FOUND", "找不到店家")
        rules = self.repo.get_pricing_rules(req.shop_id)
        slot = Slot(req.start_at, req.end_at)
        self._validate(req.shop_id, [slot], rules)
        tables = self.repo.list_tables(req.shop_id)
        links = self.repo.list_links(req.shop_id)
        occupancies = self.repo.list_occupancies(req.shop_id, slot.start_at, slot.end_at)
        try:
            chosen = allocate(
                req.party_size,
                tables,
                links,
                occupancies,
                user_id=user.id,
                start_at=slot.start_at,
                end_at=slot.end_at,
            )
        except NoTableAvailable:
            chosen = []
        return BookingQuote(
            start_at=req.start_at,
            end_at=req.end_at,
            fee=self._fee(req.start_at, req.end_at, req.party_size, rules),
            table_codes=[t.table_code for t in chosen],
        )

    # --- 建立（含批次） ---

    def create(self, user: CurrentUser, req: BookingCreate) -> BookingOut:
        require_role(user, "player", "admin")
        if not self.repo.shop_exists(req.shop_id):
            raise AppError(404, "BOOKING_SHOP_NOT_FOUND", "找不到店家")
        info = self.repo.get_user(user.id)
        if info is None:
            raise AppError(404, "BOOKING_USER_NOT_FOUND", "找不到使用者")
        if not info.phone:
            raise BookingRuleError("BOOKING_PHONE_REQUIRED", "請先在個人資料填寫電話才能訂位")

        rules = self.repo.get_pricing_rules(req.shop_id)
        slot = Slot(req.start_at, req.end_at)
        self._validate(req.shop_id, [slot], rules)

        def work() -> ReservationRecord:
            overlaps = self.repo.find_overlapping_by_phone(
                req.shop_id, info.phone, slot.start_at, slot.end_at
            )
            if overlaps and not req.confirm_overlap:
                raise AppError(
                    409,
                    "BOOKING_OVERLAP_CONFIRM_REQUIRED",
                    "與您電話下既有的訂位時間重疊，確認後會取消舊訂位",
                    {"overlaps": [self._summary(o) for o in overlaps]},
                )
            for old in overlaps:
                self._release(user, old, "cancelled", REPLACED_REASON, "cancel")

            tables = self.repo.list_tables(req.shop_id)
            links = self.repo.list_links(req.shop_id)
            occupancies = self.repo.list_occupancies(req.shop_id, slot.start_at, slot.end_at)
            chosen = allocate(
                req.party_size,
                tables,
                links,
                occupancies,
                user_id=user.id,
                start_at=slot.start_at,
                end_at=slot.end_at,
            )
            record = self.repo.create_reservation(
                shop_id=req.shop_id,
                user_id=user.id,
                start_at=slot.start_at,
                end_at=slot.end_at,
                party_size=req.party_size,
                special_requests=req.special_requests,
                table_ids=[t.id for t in chosen],
            )
            self._log(user, record, "create", None, self._snapshot(record))
            return record

        record = self._atomic(work)
        record = self._load(record.id)
        return self._out(record, rules)

    @staticmethod
    def _summary(record: ReservationRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "reservation_code": record.reservation_code,
            "start_at": record.start_at.isoformat(),
            "end_at": record.end_at.isoformat(),
        }

    # --- 查詢 ---

    def get(self, user: CurrentUser, booking_id: int) -> BookingOut:
        record = self._load(booking_id)
        self._assert_access(user, record)
        return self._out(record, self.repo.get_pricing_rules(record.shop_id))

    def list_mine(
        self,
        user: CurrentUser,
        page: int,
        page_size: int,
        *,
        status: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> BookingList:
        require_role(user, "player", "admin")
        from_dt = date.fromisoformat(from_date) if from_date else None
        to_dt = date.fromisoformat(to_date) if to_date else None
        records, total = self.repo.list_for_user(
            user.id, page, page_size, status=status, from_date=from_dt, to_date=to_dt
        )
        return self._list(records, total)

    def list_for_shop(
        self,
        user: CurrentUser,
        shop_id: uuid.UUID,
        start_at: datetime,
        end_at: datetime,
        page: int,
        page_size: int,
    ) -> BookingList:
        require_role(user, "shop_staff", "admin")
        self._assert_shop(user, shop_id)
        if not self.repo.shop_exists(shop_id):
            raise AppError(404, "BOOKING_SHOP_NOT_FOUND", "找不到店家")
        records, total = self.repo.list_for_shop(shop_id, start_at, end_at, page, page_size)
        return self._list(records, total)

    def list_shops(self, user: CurrentUser) -> ShopList:
        require_role(user, "player", "shop_staff", "admin")
        shops = self.repo.list_shops()
        return ShopList(
            items=[ShopOut(id=s.id, name=s.name) for s in shops],
            total=len(shops),
        )

    def _list(self, records: list[ReservationRecord], total: int) -> BookingList:
        rules_cache: dict[uuid.UUID, pricing.PricingRules] = {}
        items = []
        for record in records:
            if record.shop_id not in rules_cache:
                rules_cache[record.shop_id] = self.repo.get_pricing_rules(record.shop_id)
            items.append(self._out(record, rules_cache[record.shop_id]))
        return BookingList(items=items, total=total)

    # --- 修改與合併 ---

    def modify(self, user: CurrentUser, booking_id: int, patch: BookingPatch) -> BookingOut:
        require_role(user, "player", "admin")
        record = self._load(booking_id)
        self._assert_access(user, record)
        if record.status != "confirmed":
            raise _status_invalid(record.status)

        start_at = patch.start_at or record.start_at
        end_at = patch.end_at or record.end_at
        party = patch.party_size or record.party_size
        notes = (
            patch.special_requests
            if patch.special_requests is not None
            else record.special_requests
        )
        rules = self.repo.get_pricing_rules(record.shop_id)
        self._validate(record.shop_id, [Slot(start_at, end_at)], rules)

        def work() -> ReservationRecord:
            overlaps = self.repo.find_overlapping_by_user(
                record.shop_id, record.user_id, start_at, end_at, exclude=[record.id]
            )
            if overlaps:
                return self._merge(user, record, overlaps, start_at, end_at, patch, notes, rules)
            tables = self.repo.list_tables(record.shop_id)
            links = self.repo.list_links(record.shop_id)
            occupancies = self.repo.list_occupancies(
                record.shop_id, start_at, end_at, exclude_reservation_ids=[record.id]
            )
            chosen = allocate(
                party,
                tables,
                links,
                occupancies,
                user_id=record.user_id,
                start_at=start_at,
                end_at=end_at,
                preferred_ids=record.table_ids,
            )
            self.repo.replace_tables(record.id, [t.id for t in chosen], start_at, end_at)
            updated = self.repo.update_reservation(
                record.id,
                start_at=start_at,
                end_at=end_at,
                party_size=party,
                special_requests=notes,
            )
            updated = self._load(updated.id)
            self._log(user, updated, "modify", self._snapshot(record), self._snapshot(updated))
            return updated

        result = self._atomic(work)
        return self._out(self._load(result.id), rules, MODIFIED_NOTICE)

    def _merge(
        self,
        user: CurrentUser,
        record: ReservationRecord,
        overlaps: list[ReservationRecord],
        start_at: datetime,
        end_at: datetime,
        patch: BookingPatch,
        notes: str | None,
        rules: pricing.PricingRules,
    ) -> ReservationRecord:
        if not patch.merge:
            raise AppError(
                409,
                "BOOKING_MERGE_CONFIRM_REQUIRED",
                "修改後與您的其他訂位重疊，是否合併為一筆？",
                {"overlaps": [self._summary(o) for o in overlaps]},
            )
        if patch.party_size is None:
            raise BookingRuleError("BOOKING_PARTY_SIZE_REQUIRED", "合併時需要重新輸入人數")
        merged_start = min([start_at, *(o.start_at for o in overlaps)])
        merged_end = max([end_at, *(o.end_at for o in overlaps)])
        self._validate(record.shop_id, [Slot(merged_start, merged_end)], rules)
        for old in [record, *overlaps]:
            self._release(user, old, "cancelled", MERGED_REASON, "cancel")
        chosen = allocate(
            patch.party_size,
            self.repo.list_tables(record.shop_id),
            self.repo.list_links(record.shop_id),
            self.repo.list_occupancies(record.shop_id, merged_start, merged_end),
            user_id=record.user_id,
            start_at=merged_start,
            end_at=merged_end,
        )
        created = self.repo.create_reservation(
            shop_id=record.shop_id,
            user_id=record.user_id,
            start_at=merged_start,
            end_at=merged_end,
            party_size=patch.party_size,
            special_requests=notes,
            table_ids=[t.id for t in chosen],
        )
        created = self._load(created.id)
        self._log(user, created, "merge", None, self._snapshot(created))
        return created

    # --- 狀態變更 ---

    def change_status(self, user: CurrentUser, booking_id: int, patch: BookingPatch) -> BookingOut:
        record = self._load(booking_id)
        self._assert_access(user, record)
        target = patch.status
        if target != "cancelled":
            require_role(user, "shop_staff", "admin")
        rules = self.repo.get_pricing_rules(record.shop_id)

        def work() -> ReservationRecord:
            if target == "cancelled":
                return self._cancel(user, record, patch.cancel_reason)
            if target == "seated":
                return self._seat(user, record)
            if target == "completed":
                return self._complete(user, record, rules)
            if target == "no_show":
                if record.status != "confirmed":
                    raise _status_invalid(record.status)
                return self._release(user, record, "no_show", patch.cancel_reason, "no_show")
            raise _status_invalid(record.status)  # confirmed 不能手動設定

        return self._out(self._load(self._atomic(work).id), rules)

    def _cancel(
        self, user: CurrentUser, record: ReservationRecord, reason: str | None
    ) -> ReservationRecord:
        if record.status != "confirmed":
            raise _status_invalid(record.status)
        late_customer = user.role == "player" and self.now() >= record.start_at
        status = "no_show" if late_customer else "cancelled"
        return self._release(
            user, record, status, reason, "cancel" if not late_customer else "no_show"
        )

    def _seat(self, user: CurrentUser, record: ReservationRecord) -> ReservationRecord:
        if record.status not in ("confirmed", "no_show"):
            raise _status_invalid(record.status)
        if record.status == "no_show":
            # 桌位在 no_show 時已釋放，改回入座前要確認沒被別人訂走
            occupancies = self.repo.list_occupancies(
                record.shop_id, record.start_at, record.end_at, exclude_reservation_ids=[record.id]
            )
            taken = [
                o
                for o in occupancies
                if o.table_id in record.table_ids
                and is_conflict(
                    o, user_id=record.user_id, start_at=record.start_at, end_at=record.end_at
                )
            ]
            if taken:
                raise AppError(409, "BOOKING_TABLE_TAKEN", "原桌位已被其他訂位占用")
            try:
                self.repo.set_tables_active(record.id, True)
            except TableConflict:
                raise AppError(409, "BOOKING_TABLE_TAKEN", "原桌位已被其他訂位占用") from None
        updated = self.repo.update_reservation(
            record.id, status="seated", seated_at=self.now(), cancelled_at=None, cancel_reason=None
        )
        self._log(user, updated, "seat", self._snapshot(record), self._snapshot(updated))
        return updated

    def _complete(
        self, user: CurrentUser, record: ReservationRecord, rules: pricing.PricingRules
    ) -> ReservationRecord:
        if record.status != "seated" or record.seated_at is None:
            raise _status_invalid(record.status)
        completed_at = self.now()
        final_fee = pricing.quote(
            record.seated_at, completed_at, record.party_size, rules
        ).venue_fee
        self.repo.set_tables_active(record.id, False)
        updated = self.repo.update_reservation(
            record.id, status="completed", completed_at=completed_at, final_fee=final_fee
        )
        self._log(user, updated, "complete", self._snapshot(record), self._snapshot(updated))
        return updated

    # --- 店員改桌 ---

    def change_tables(self, user: CurrentUser, booking_id: int, table_ids: list[int]) -> BookingOut:
        require_role(user, "shop_staff", "admin")
        record = self._load(booking_id)
        self._assert_access(user, record)
        if record.status not in ("confirmed", "seated"):
            raise _status_invalid(record.status)
        rules = self.repo.get_pricing_rules(record.shop_id)
        valid = {t.id for t in self.repo.list_tables(record.shop_id)}
        wanted = list(dict.fromkeys(table_ids))
        if not set(wanted) <= valid:
            raise BookingRuleError("BOOKING_TABLE_INVALID", "指定的桌位不存在或未啟用")

        def work() -> ReservationRecord:
            occupancies = self.repo.list_occupancies(
                record.shop_id, record.start_at, record.end_at, exclude_reservation_ids=[record.id]
            )
            for o in occupancies:
                if o.table_id in wanted and is_conflict(
                    o, user_id=record.user_id, start_at=record.start_at, end_at=record.end_at
                ):
                    raise AppError(409, "BOOKING_TABLE_TAKEN", "該桌位在此時段已被訂走")
            self.repo.replace_tables(record.id, wanted, record.start_at, record.end_at)
            updated = self._load(record.id)
            self._log(
                user, updated, "change_tables", self._snapshot(record), self._snapshot(updated)
            )
            return updated

        try:
            result = self._atomic(work)
        except NoTableAvailable:
            raise AppError(409, "BOOKING_TABLE_TAKEN", "該桌位在此時段已被訂走") from None
        return self._out(result, rules)
