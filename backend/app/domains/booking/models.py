import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
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


def _id() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(always=True), primary_key=True)


def _shop_fk() -> Mapped[uuid.UUID]:
    """舊庫的 shop_id（店家）。程式內仍叫 shop_id，欄位名稱與舊庫相同。"""
    return mapped_column("shop_id", Uuid, ForeignKey("booking_shops.id"), nullable=False)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class BookingShop(Base):
    __tablename__ = "booking_shops"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), server_default=text("'Asia/Taipei'"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _created_at()


class BookingBusinessHours(Base):
    __tablename__ = "business_hours"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_business_hours_shop_id_id"),
        UniqueConstraint("shop_id", "weekday", name="uq_business_hours_shop_weekday"),
        CheckConstraint("open_time < close_time", name="chk_business_hours_time"),
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="chk_business_hours_weekday"),
    )

    id: Mapped[int] = _id()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0=星期日
    open_time: Mapped[time] = mapped_column(Time)
    close_time: Mapped[time] = mapped_column(Time)


class BookingClosingHours(Base):
    __tablename__ = "closing_hours"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_closing_hours_shop_id_id"),
        CheckConstraint(
            "(start_time IS NULL AND end_time IS NULL) OR "
            "(start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)",
            name="chk_closing_hours_time",
        ),
    )

    id: Mapped[int] = _id()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    closing_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class BookingTable(Base):
    __tablename__ = "seating_tables"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_seating_tables_shop_id_id"),
        UniqueConstraint("shop_id", "table_code", name="uq_seating_tables_shop_code"),
        CheckConstraint(
            "min_capacity >= 1 AND max_capacity >= min_capacity", name="chk_seating_tables_capacity"
        ),
    )

    id: Mapped[int] = _id()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    table_code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str | None] = mapped_column("table_name", String(100), nullable=True)
    min_capacity: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    max_capacity: Mapped[int] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    floor: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("1"), comment="樓層：1=1F，-1=B1"
    )
    x: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="桌子在座位圖畫布上的 X 座標（像素）",
    )
    y: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="桌子在座位圖畫布上的 Y 座標（像素）",
    )
    width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("100"),
        comment="桌子在座位圖上的寬度（像素）",
    )
    height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("100"),
        comment="桌子在座位圖上的高度（像素）",
    )
    shape: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'rectangle'"),
        comment="桌子形狀，目前固定為 rectangle",
    )
    created_at: Mapped[datetime] = _created_at()


class BookingTableLink(Base):
    __tablename__ = "seating_tables_rel"

    id: Mapped[int] = _id()
    table_a_id: Mapped[int] = mapped_column(
        "seating_tables_id_a", BigInteger, ForeignKey("seating_tables.id", ondelete="CASCADE")
    )
    table_b_id: Mapped[int] = mapped_column(
        "seating_tables_id_b", BigInteger, ForeignKey("seating_tables.id", ondelete="CASCADE")
    )
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    is_combinable: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class BookingPricingRule(Base):
    __tablename__ = "pricing_rules"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_pricing_rules_shop_id_id"),
        UniqueConstraint("shop_id", "rule_code", name="uq_pricing_rules_shop_code"),
        CheckConstraint("price >= 0", name="chk_pricing_rules_price"),
    )

    id: Mapped[int] = _id()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    rule_code: Mapped[str] = mapped_column(String(50))
    rule_name: Mapped[str] = mapped_column(String(100))
    rule_type: Mapped[str] = mapped_column(String(30))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = _created_at()


class BookingReservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint("shop_id", "id", name="uq_reservations_shop_id_id"),
        UniqueConstraint("shop_id", "reservation_code", name="uq_reservations_shop_code"),
        CheckConstraint("end_at > start_at", name="chk_reservations_time"),
        CheckConstraint("party_size >= 1", name="chk_reservations_party_size"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'seated', 'completed', 'cancelled', 'no_show')",
            name="chk_reservations_status",
        ),
        CheckConstraint(
            "source IN ('customer_service', 'phone', 'walk_in', 'online')",
            name="chk_reservations_source",
        ),
    )

    id: Mapped[int] = _id()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    reservation_code: Mapped[str] = mapped_column(String(30))
    # 舊庫的 customers 由 auth_users 取代
    user_id: Mapped[uuid.UUID] = mapped_column(
        "customer_id", Uuid, ForeignKey("auth_users.id", ondelete="RESTRICT")
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    party_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), server_default=text("'pending'"))
    source: Mapped[str] = mapped_column(String(30), server_default=text("'customer_service'"))
    special_requests: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _created_at()
    # 擴充欄位（舊庫沒有）
    seated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class BookingReservationTable(Base):
    """訂位占用的桌位。start_at、end_at、is_active 是擴充欄位，用來防止同桌時間重疊。"""

    __tablename__ = "reservation_tables"
    __table_args__ = (
        ForeignKeyConstraint(
            ["shop_id", "reservation_id"],
            ["reservations.shop_id", "reservations.id"],
            name="fk_reservation_tables_reservation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shop_id", "table_id"],
            ["seating_tables.shop_id", "seating_tables.id"],
            name="fk_reservation_tables_table",
            ondelete="RESTRICT",
        ),
        ExcludeConstraint(
            ("shop_id", "="),
            ("table_id", "="),
            (text("tstzrange(start_at, end_at, '[)')"), "&&"),
            using="gist",
            where=text("is_active"),
            name="ex_reservation_tables_no_overlap",
        ),
        CheckConstraint("end_at > start_at", name="chk_reservation_tables_time"),
    )

    shop_id: Mapped[uuid.UUID] = mapped_column("shop_id", Uuid, primary_key=True)
    reservation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    table_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class BookingReservationLog(Base):
    __tablename__ = "reservation_logs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["shop_id", "reservation_id"],
            ["reservations.shop_id", "reservations.id"],
            name="fk_reservation_logs_reservation",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "operator_type IN ('customer', 'staff', 'ai', 'system')",
            name="chk_reservation_logs_operator_type",
        ),
        Index(
            "idx_reservation_logs_shop_reservation",
            "shop_id",
            "reservation_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[int] = _id()
    shop_id: Mapped[uuid.UUID] = _shop_fk()
    reservation_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(50))
    old_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    operator_type: Mapped[str] = mapped_column(String(30))
    operator_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = _created_at()
