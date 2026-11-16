"""並發搶桌：兩個請求同時搶最後一張桌，只能有一個成功（資料庫 exclusion constraint 保護）。"""

import threading
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser
from app.core.errors import AppError
from app.domains.booking.repository import BookingRepository
from app.domains.booking.schemas import BookingCreate, SlotIn
from app.domains.booking.service import BookingService
from tests.booking.conftest import NOW, PLAYER, PLAYER2, SHOP

TZ = ZoneInfo("Asia/Taipei")


class RacingRepository(BookingRepository):
    """第一次查桌位占用時等另一個請求也查完，確保兩邊都看到「桌位是空的」才開始寫入。"""

    def __init__(self, session: Session, barrier: threading.Barrier) -> None:
        super().__init__(session)
        self.barrier = barrier
        self.waited = False

    def list_occupancies(self, *args, **kwargs):
        result = super().list_occupancies(*args, **kwargs)
        if not self.waited:
            self.waited = True
            self.barrier.wait(timeout=10)
        return result


def request() -> BookingCreate:
    return BookingCreate(
        shop_id=SHOP,
        party_size=4,
        slots=[
            SlotIn(
                start_at=datetime(2026, 11, 25, 14, tzinfo=TZ),
                end_at=datetime(2026, 11, 25, 16, tzinfo=TZ),
            )
        ],
    )


def race(db: Engine) -> list[object]:
    """兩個使用者同時訂同一時段，回傳各自的結果（成功是 BookingList，失敗是 AppError）。"""
    barrier = threading.Barrier(2)
    outcomes: dict[uuid.UUID, object] = {}

    def attempt(user_id: uuid.UUID) -> None:
        with Session(db) as session:
            service = BookingService(RacingRepository(session, barrier), now=lambda: NOW)
            try:
                outcomes[user_id] = service.create(CurrentUser(user_id, "player"), request())
            except AppError as error:
                outcomes[user_id] = error

    threads = [threading.Thread(target=attempt, args=(u,)) for u in (PLAYER, PLAYER2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return list(outcomes.values())


def only_table_g(db: Engine) -> None:
    with db.begin() as conn:
        conn.execute(text("UPDATE booking_tables SET is_active = false WHERE table_code <> 'G'"))


def test_only_one_of_two_simultaneous_requests_gets_the_last_table(db: Engine, seeded):
    only_table_g(db)
    outcomes = race(db)
    errors = [o for o in outcomes if isinstance(o, AppError)]
    assert len(outcomes) == 2 and len(errors) == 1
    assert errors[0].status_code == 409 and errors[0].code == "BOOKING_NO_TABLE_AVAILABLE"
    with db.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM booking_reservations")).scalar_one() == 1
        assert (
            conn.execute(text("SELECT count(*) FROM booking_reservation_tables")).scalar_one() == 1
        )


def test_repeated_races_never_double_book(db: Engine, seeded):
    """多跑幾輪：不管誰先搶到，結果都是一個成功、一個桌位不足。"""
    only_table_g(db)
    for _ in range(3):
        with db.begin() as conn:
            conn.execute(
                text(
                    "TRUNCATE booking_reservation_logs, booking_reservation_tables, "
                    "booking_reservations CASCADE"
                )
            )
        outcomes = race(db)
        assert sum(isinstance(o, AppError) for o in outcomes) == 1 and len(outcomes) == 2
