import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


def _shop_fk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey("booking_shops.id"), nullable=False)


class BookingShop(Base):
    __tablename__ = "booking_shops"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)


class BookingBusinessHours(Base):
    __tablename__ = "booking_business_hours"
    __table_args__ = (
        UniqueConstraint("shop_id", "weekday", name="uq_booking_business_hours_shop_weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_booking_business_hours_weekday"),
        CheckConstraint("open_time < close_time", name="ck_booking_business_hours_range"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0=星期日
    open_time: Mapped[time] = mapped_column(Time)
    close_time: Mapped[time] = mapped_column(Time)


class BookingClosingHours(Base):
    __tablename__ = "booking_closing_hours"
    __table_args__ = (
        CheckConstraint(
            "(start_time IS NULL AND end_time IS NULL) OR "
            "(start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)",
            name="ck_booking_closing_hours_range",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    closing_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class BookingTable(Base):
    __tablename__ = "booking_tables"
    __table_args__ = (
        UniqueConstraint("shop_id", "table_code", name="uq_booking_tables_shop_code"),
        CheckConstraint(
            "min_capacity >= 1 AND max_capacity >= min_capacity", name="ck_booking_tables_capacity"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    table_code: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_capacity: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    max_capacity: Mapped[int] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class BookingTableLink(Base):
    __tablename__ = "booking_table_links"
    __table_args__ = (
        CheckConstraint("table_a_id <> table_b_id", name="ck_booking_table_links_distinct"),
        Index(
            "uq_booking_table_links_pair",
            "shop_id",
            text("LEAST(table_a_id, table_b_id)"),
            text("GREATEST(table_a_id, table_b_id)"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    table_a_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("booking_tables.id"))
    table_b_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("booking_tables.id"))
    is_combinable: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class BookingPricingRule(Base):
    __tablename__ = "booking_pricing_rules"
    __table_args__ = (
        UniqueConstraint("shop_id", "rule_code", name="uq_booking_pricing_rules_shop_code"),
        CheckConstraint("price >= 0", name="ck_booking_pricing_rules_price"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    rule_code: Mapped[str] = mapped_column(Text)
    rule_name: Mapped[str] = mapped_column(Text)
    rule_type: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class BookingReservation(Base):
    __tablename__ = "booking_reservations"
    __table_args__ = (
        UniqueConstraint("shop_id", "reservation_code", name="uq_booking_reservations_code"),
        CheckConstraint("end_at > start_at", name="ck_booking_reservations_range"),
        CheckConstraint("party_size >= 1", name="ck_booking_reservations_party_size"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'seated', 'completed', 'cancelled', 'no_show')",
            name="ck_booking_reservations_status",
        ),
        CheckConstraint(
            "source IN ('customer_service', 'phone', 'walk_in', 'online')",
            name="ck_booking_reservations_source",
        ),
        Index("ix_booking_reservations_shop_start", "shop_id", "start_at"),
        Index("ix_booking_reservations_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    reservation_code: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("auth_users.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    party_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    special_requests: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    seated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BookingReservationTable(Base):
    """訂位占用的桌位。start_at/end_at 與訂位同步，供 exclusion constraint 防止同桌重疊。"""

    __tablename__ = "booking_reservation_tables"
    __table_args__ = (
        ExcludeConstraint(
            ("shop_id", "="),
            ("table_id", "="),
            (text("tstzrange(start_at, end_at, '[)')"), "&&"),
            using="gist",
            where=text("is_active"),
            name="ex_booking_reservation_tables_no_overlap",
        ),
        CheckConstraint("end_at > start_at", name="ck_booking_reservation_tables_range"),
        Index("ix_booking_reservation_tables_reservation", "reservation_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("booking_reservations.id"), nullable=False
    )
    table_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("booking_tables.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class BookingReservationLog(Base):
    __tablename__ = "booking_reservation_logs"
    __table_args__ = (
        CheckConstraint(
            "operator_type IN ('customer', 'staff', 'ai', 'system')",
            name="ck_booking_reservation_logs_operator_type",
        ),
        Index("ix_booking_reservation_logs_reservation", "reservation_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("booking_reservations.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text)
    old_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    operator_type: Mapped[str] = mapped_column(Text)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    operator_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
