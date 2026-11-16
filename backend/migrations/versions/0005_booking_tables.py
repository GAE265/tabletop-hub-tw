"""booking tables: 訂位系統的 8 張資料表，並在 auth_users 加上 phone

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _shop() -> sa.Column:
    return sa.Column("shop_id", sa.Uuid(), sa.ForeignKey("booking_shops.id"), nullable=False)


def _ts(name: str, nullable: bool = False, default_now: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.func.now() if default_now else None,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.add_column("auth_users", sa.Column("phone", sa.Text(), nullable=True))

    op.create_table(
        "booking_business_hours",
        _pk(),
        _shop(),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.UniqueConstraint("shop_id", "weekday", name="uq_booking_business_hours_shop_weekday"),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_booking_business_hours_weekday"),
        sa.CheckConstraint("open_time < close_time", name="ck_booking_business_hours_range"),
    )
    op.create_table(
        "booking_closing_hours",
        _pk(),
        _shop(),
        sa.Column("closing_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(start_time IS NULL AND end_time IS NULL) OR "
            "(start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)",
            name="ck_booking_closing_hours_range",
        ),
    )
    op.create_table(
        "booking_tables",
        _pk(),
        _shop(),
        sa.Column("table_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("min_capacity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("max_capacity", sa.Integer(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("shop_id", "table_code", name="uq_booking_tables_shop_code"),
        sa.CheckConstraint(
            "min_capacity >= 1 AND max_capacity >= min_capacity", name="ck_booking_tables_capacity"
        ),
    )
    op.create_table(
        "booking_table_links",
        _pk(),
        _shop(),
        sa.Column("table_a_id", sa.Uuid(), sa.ForeignKey("booking_tables.id"), nullable=False),
        sa.Column("table_b_id", sa.Uuid(), sa.ForeignKey("booking_tables.id"), nullable=False),
        sa.Column("is_combinable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("table_a_id <> table_b_id", name="ck_booking_table_links_distinct"),
    )
    op.create_index(
        "uq_booking_table_links_pair",
        "booking_table_links",
        [
            "shop_id",
            sa.text("LEAST(table_a_id, table_b_id)"),
            sa.text("GREATEST(table_a_id, table_b_id)"),
        ],
        unique=True,
    )
    op.create_table(
        "booking_pricing_rules",
        _pk(),
        _shop(),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column("rule_name", sa.Text(), nullable=False),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.UniqueConstraint("shop_id", "rule_code", name="uq_booking_pricing_rules_shop_code"),
        sa.CheckConstraint("price >= 0", name="ck_booking_pricing_rules_price"),
    )
    op.create_table(
        "booking_reservations",
        _pk(),
        _shop(),
        sa.Column("reservation_code", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("auth_users.id"), nullable=False),
        _ts("start_at"),
        _ts("end_at"),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        _ts("seated_at", nullable=True),
        _ts("completed_at", nullable=True),
        sa.Column("final_fee", sa.Numeric(10, 2), nullable=True),
        _ts("cancelled_at", nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        _ts("created_at", default_now=True),
        _ts("updated_at", default_now=True),
        sa.UniqueConstraint("shop_id", "reservation_code", name="uq_booking_reservations_code"),
        sa.CheckConstraint("end_at > start_at", name="ck_booking_reservations_range"),
        sa.CheckConstraint("party_size >= 1", name="ck_booking_reservations_party_size"),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'seated', 'completed', 'cancelled', 'no_show')",
            name="ck_booking_reservations_status",
        ),
        sa.CheckConstraint(
            "source IN ('customer_service', 'phone', 'walk_in', 'online')",
            name="ck_booking_reservations_source",
        ),
    )
    op.create_index(
        "ix_booking_reservations_shop_start", "booking_reservations", ["shop_id", "start_at"]
    )
    op.create_index("ix_booking_reservations_user", "booking_reservations", ["user_id"])
    op.create_table(
        "booking_reservation_tables",
        _pk(),
        _shop(),
        sa.Column(
            "reservation_id", sa.Uuid(), sa.ForeignKey("booking_reservations.id"), nullable=False
        ),
        sa.Column("table_id", sa.Uuid(), sa.ForeignKey("booking_tables.id"), nullable=False),
        _ts("start_at"),
        _ts("end_at"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        postgresql.ExcludeConstraint(
            ("shop_id", "="),
            ("table_id", "="),
            (sa.text("tstzrange(start_at, end_at, '[)')"), "&&"),
            using="gist",
            where=sa.text("is_active"),
            name="ex_booking_reservation_tables_no_overlap",
        ),
        sa.CheckConstraint("end_at > start_at", name="ck_booking_reservation_tables_range"),
    )
    op.create_index(
        "ix_booking_reservation_tables_reservation",
        "booking_reservation_tables",
        ["reservation_id"],
    )
    op.create_table(
        "booking_reservation_logs",
        _pk(),
        _shop(),
        sa.Column(
            "reservation_id", sa.Uuid(), sa.ForeignKey("booking_reservations.id"), nullable=False
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("old_data", postgresql.JSONB(), nullable=True),
        sa.Column("new_data", postgresql.JSONB(), nullable=True),
        sa.Column("operator_type", sa.Text(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("operator_name", sa.Text(), nullable=True),
        _ts("created_at", default_now=True),
        sa.CheckConstraint(
            "operator_type IN ('customer', 'staff', 'ai', 'system')",
            name="ck_booking_reservation_logs_operator_type",
        ),
    )
    op.create_index(
        "ix_booking_reservation_logs_reservation", "booking_reservation_logs", ["reservation_id"]
    )


def downgrade() -> None:
    for table in (
        "booking_reservation_logs",
        "booking_reservation_tables",
        "booking_reservations",
        "booking_pricing_rules",
        "booking_table_links",
        "booking_tables",
        "booking_closing_hours",
        "booking_business_hours",
    ):
        op.drop_table(table)
    op.drop_column("auth_users", "phone")
