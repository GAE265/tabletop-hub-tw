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
    BookingOut,
    BookingPatch,
    BookingQuote,
    BookingQuoteRequest,
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


@router.post("/booking-quotes", response_model=BookingQuote)
def create_quote(body: BookingQuoteRequest, user: CurrentUserDep, service: ServiceDep):
    return service.quote(user, body)


@router.post("/bookings", response_model=BookingList, status_code=201)
def create_bookings(body: BookingCreate, user: CurrentUserDep, service: ServiceDep):
    return service.create(user, body)


@router.get("/bookings", response_model=BookingList)
def list_my_bookings(
    user: CurrentUserDep, service: ServiceDep, page: Page = 1, page_size: PageSize = 20
):
    return service.list_mine(user, page, page_size)


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
