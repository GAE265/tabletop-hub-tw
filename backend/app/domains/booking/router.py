import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_session
from app.domains.booking.repository import BookingRepository
from app.domains.booking.schemas import (
    BookingCreate,
    BookingList,
    BookingNotificationList,
    BookingNotificationOut,
    BookingNotificationUpdate,
    BookingOut,
    BookingPatch,
    BookingQuote,
    BookingQuoteRequest,
    SeatingPlanOut,
    ShopList,
    TablesPut,
)
from app.domains.booking.service import BookingService

router = APIRouter(tags=["booking"])

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def get_booking_service(session: Annotated[Session, Depends(get_session)]) -> BookingService:
    return BookingService(BookingRepository(session))


ServiceDep = Annotated[BookingService, Depends(get_booking_service)]


@router.get("/shops", response_model=ShopList)
def list_shops(user: CurrentUserDep, service: ServiceDep):
    return service.list_shops(user)


@router.post("/booking-quotes", response_model=BookingQuote)
def create_quote(body: BookingQuoteRequest, user: CurrentUserDep, service: ServiceDep):
    return service.quote(user, body)


@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_bookings(body: BookingCreate, user: CurrentUserDep, service: ServiceDep):
    return service.create(user, body)


@router.get("/bookings", response_model=BookingList)
def list_my_bookings(
    user: CurrentUserDep,
    service: ServiceDep,
    page: Page = 1,
    page_size: PageSize = 20,
    status: str | None = Query(None, description="訂位狀態篩選"),
    from_date: str | None = Query(None, alias="from", description="開始日期 YYYY-MM-DD"),
    to_date: str | None = Query(None, alias="to", description="結束日期 YYYY-MM-DD"),
):
    return service.list_mine(
        user, page, page_size, status=status, from_date=from_date, to_date=to_date
    )


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, user: CurrentUserDep, service: ServiceDep):
    return service.get(user, booking_id)


@router.patch("/bookings/{booking_id}", response_model=BookingOut)
def patch_booking(booking_id: int, body: BookingPatch, user: CurrentUserDep, service: ServiceDep):
    if body.status is not None:
        return service.change_status(user, booking_id, body)
    return service.modify(user, booking_id, body)


@router.put("/bookings/{booking_id}/tables", response_model=BookingOut)
def put_booking_tables(booking_id: int, body: TablesPut, user: CurrentUserDep, service: ServiceDep):
    return service.change_tables(user, booking_id, body.table_ids)


@router.get("/shops/{shop_id}/bookings", response_model=BookingList)
def list_shop_bookings(
    shop_id: uuid.UUID,
    user: CurrentUserDep,
    service: ServiceDep,
    start_at: Annotated[datetime, Query(alias="from")],
    end_at: Annotated[datetime, Query(alias="to")],
    page: Page = 1,
    page_size: PageSize = 20,
):
    return service.list_for_shop(user, shop_id, start_at, end_at, page, page_size)


@router.get("/shops/{shop_id}/tables/status", response_model=list[SeatingPlanOut])
def get_tables_status(
    shop_id: uuid.UUID,
    user: CurrentUserDep,
    service: ServiceDep,
    start_at: Annotated[datetime | None, Query(alias="from")] = None,
    end_at: Annotated[datetime | None, Query(alias="to")] = None,
    floor: int | None = None,
):
    """查詢桌子狀態（座位圖）。

    未帶 from/to 時預設查詢當天 Asia/Taipei 的 00:00–23:59:59。
    回傳各樓層的座位圖（依 floor 分組）。
    """
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Asia/Taipei"))
    if start_at is None:
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if end_at is None:
        end_at = now.replace(hour=23, minute=59, second=59, microsecond=0)

    statuses = service.get_tables_status(user, shop_id, start_at, end_at, floor)

    # 依 floor 分組
    from collections import defaultdict

    from app.domains.booking.schemas import BookingSummaryOut, TableStatusOut

    by_floor: dict[int, list[TableStatusOut]] = defaultdict(list)
    for s in statuses:
        booking_out = None
        if s.booking:
            booking_out = BookingSummaryOut(
                id=s.booking.id,
                reservation_code=s.booking.reservation_code,
                user_id=s.booking.user_id,
                start_at=s.booking.start_at,
                end_at=s.booking.end_at,
                party_size=s.booking.party_size,
                status=s.booking.status,
            )
        by_floor[s.floor].append(
            TableStatusOut(
                id=s.id,
                table_code=s.table_code,
                name=s.name,
                max_capacity=s.max_capacity,
                x=s.x,
                y=s.y,
                width=s.width,
                height=s.height,
                shape=s.shape,
                status=s.status,
                booking=booking_out,
            )
        )

    return [
        SeatingPlanOut(floor=floor, tables=tables) for floor, tables in sorted(by_floor.items())
    ]


# --- 通知（add-booking-notifications）---


@router.get("/booking-notifications", response_model=BookingNotificationList)
def list_notifications(
    user: CurrentUserDep, service: ServiceDep, page: Page = 1, page_size: PageSize = 20
):
    """自己的訂位通知，新的在前；附全部未讀數。"""
    return service.list_notifications(user, page=page, page_size=page_size)


@router.patch("/booking-notifications/{notification_id}", response_model=BookingNotificationOut)
def update_notification(
    notification_id: uuid.UUID,
    body: BookingNotificationUpdate,
    user: CurrentUserDep,
    service: ServiceDep,
):
    """標成已讀（body 只能是 {"read": true}）。"""
    return service.mark_notification_read(user, notification_id)
