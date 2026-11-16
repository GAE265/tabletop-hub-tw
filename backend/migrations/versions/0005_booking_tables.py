"""booking tables: 依舊訂位資料庫的表名、欄位、型別與約束建立訂位相關資料表

與舊庫的差異（刻意的）：
- companies 由共用表 booking_shops 取代：所有 shop_id 改為 uuid，參照 booking_shops.id，
  並在 booking_shops 補上 companies 的資訊欄位。
- customers 由 auth_users 取代：customer_id 改為 uuid，參照 auth_users.id；auth_users 新增 phone。
- 擴充欄位（舊庫沒有）：reservations 的 seated_at、completed_at、final_fee、cancelled_at、
  cancel_reason；reservation_tables 的 start_at、end_at、is_active 與防止同桌重疊的
  exclusion constraint。

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

NOW = sa.text("now()")


def _id() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False)


def _company() -> sa.Column:
    return sa.Column("shop_id", sa.Uuid(), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW)


def _company_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["shop_id"], ["booking_shops.id"], name=f"fk_{table}_company", ondelete="RESTRICT"
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # 共用表：auth_users 加 phone；booking_shops 補上 companies 的資訊欄位
    op.add_column("auth_users", sa.Column("phone", sa.String(30), nullable=True))
    op.add_column("booking_shops", sa.Column("phone", sa.String(30), nullable=True))
    op.add_column("booking_shops", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("booking_shops", sa.Column("facebook_url", sa.Text(), nullable=True))
    op.add_column(
        "booking_shops",
        sa.Column(
            "timezone", sa.String(64), nullable=False, server_default=sa.text("'Asia/Taipei'")
        ),
    )
    op.add_column(
        "booking_shops",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "booking_shops",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.add_column(
        "booking_shops",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )

    op.create_table(
        "business_hours",
        _id(),
        _company(),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="business_hours_pkey"),
        sa.UniqueConstraint("shop_id", "id", name="uq_business_hours_shop_id_id"),
        sa.UniqueConstraint("shop_id", "weekday", name="uq_business_hours_company_weekday"),
        sa.CheckConstraint("open_time < close_time", name="chk_business_hours_time"),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6", name="chk_business_hours_weekday"),
        _company_fk("business_hours"),
    )

    op.create_table(
        "closing_hours",
        _id(),
        _company(),
        sa.Column("closing_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="closing_hours_pkey"),
        sa.UniqueConstraint("shop_id", "id", name="uq_closing_hours_shop_id_id"),
        sa.CheckConstraint(
            "(start_time IS NULL AND end_time IS NULL) OR "
            "(start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)",
            name="chk_closing_hours_time",
        ),
        _company_fk("closing_hours"),
    )
    op.create_index(
        "idx_closing_hours_company_date", "closing_hours", ["shop_id", "closing_date"]
    )

    op.create_table(
        "seating_tables",
        _id(),
        _company(),
        sa.Column("table_code", sa.String(30), nullable=False),
        sa.Column("table_name", sa.String(100), nullable=True),
        sa.Column("min_capacity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("max_capacity", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="seating_tables_pkey"),
        sa.UniqueConstraint("shop_id", "id", name="uq_seating_tables_shop_id_id"),
        sa.UniqueConstraint("shop_id", "table_code", name="uq_seating_tables_company_code"),
        sa.CheckConstraint(
            "min_capacity >= 1 AND max_capacity >= min_capacity",
            name="chk_seating_tables_capacity",
        ),
        _company_fk("seating_tables"),
    )
    op.create_index(
        "idx_seating_tables_company_capacity",
        "seating_tables",
        ["shop_id", "max_capacity"],
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "seating_tables_rel",
        _id(),
        sa.Column("seating_tables_id_a", sa.BigInteger(), nullable=False),
        sa.Column("seating_tables_id_b", sa.BigInteger(), nullable=False),
        _company(),
        sa.Column("is_combinable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id", name="seating_tables_groups_pk"),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["booking_shops.id"],
            name="combinable_seating_tables_companies_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seating_tables_id_a"],
            ["seating_tables.id"],
            name="combinable_seating_tables_seating_tables_fk",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seating_tables_id_b"],
            ["seating_tables.id"],
            name="combinable_seating_tables_seating_tables_fk_1",
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "pricing_rules",
        _id(),
        _company(),
        sa.Column("rule_code", sa.String(50), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pricing_rules_pkey"),
        sa.UniqueConstraint("shop_id", "id", name="uq_pricing_rules_shop_id_id"),
        sa.UniqueConstraint("shop_id", "rule_code", name="uq_pricing_rules_company_code"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="chk_pricing_rules_effective_date",
        ),
        sa.CheckConstraint("price >= 0", name="chk_pricing_rules_price"),
        sa.CheckConstraint(
            "rule_type IN ('hourly', 'teaching', 'minimum_charge', 'cleaning', 'other')",
            name="chk_pricing_rules_type",
        ),
        _company_fk("pricing_rules"),
    )
    op.create_index(
        "idx_pricing_rules_company_active",
        "pricing_rules",
        ["shop_id", "rule_code", "is_active"],
    )

    op.create_table(
        "reservations",
        _id(),
        _company(),
        sa.Column("reservation_code", sa.String(30), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "source", sa.String(30), nullable=False, server_default=sa.text("'customer_service'")
        ),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        # 擴充欄位（舊庫沒有）
        sa.Column("seated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_fee", sa.Numeric(10, 2), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="reservations_pkey"),
        sa.UniqueConstraint("shop_id", "id", name="uq_reservations_shop_id_id"),
        sa.UniqueConstraint("shop_id", "reservation_code", name="uq_reservations_company_code"),
        sa.CheckConstraint("party_size >= 1", name="chk_reservations_party_size"),
        sa.CheckConstraint(
            "source IN ('customer_service', 'phone', 'walk_in', 'online')",
            name="chk_reservations_source",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'seated', 'completed', 'cancelled', 'no_show')",
            name="chk_reservations_status",
        ),
        sa.CheckConstraint("end_at > start_at", name="chk_reservations_time"),
        _company_fk("reservations"),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["auth_users.id"], name="fk_reservations_customer", ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "idx_reservations_company_customer",
        "reservations",
        ["shop_id", "customer_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_reservations_company_time_status", "reservations", ["shop_id", "start_at", "status"]
    )
    op.create_index("idx_reservations_company_status", "reservations", ["shop_id", "status"])

    op.create_table(
        "reservation_tables",
        _company(),
        sa.Column("reservation_id", sa.BigInteger(), nullable=False),
        sa.Column("table_id", sa.BigInteger(), nullable=False),
        # 擴充欄位（舊庫沒有）：與訂位時間同步，供 exclusion constraint 防止同桌重疊
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint(
            "shop_id", "reservation_id", "table_id", name="pk_reservation_tables"
        ),
        sa.ForeignKeyConstraint(
            ["shop_id", "reservation_id"],
            ["reservations.shop_id", "reservations.id"],
            name="fk_reservation_tables_reservation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id", "table_id"],
            ["seating_tables.shop_id", "seating_tables.id"],
            name="fk_reservation_tables_table",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("end_at > start_at", name="chk_reservation_tables_time"),
        postgresql.ExcludeConstraint(
            ("shop_id", "="),
            ("table_id", "="),
            (sa.text("tstzrange(start_at, end_at, '[)')"), "&&"),
            using="gist",
            where=sa.text("is_active"),
            name="ex_reservation_tables_no_overlap",
        ),
    )
    op.create_index(
        "idx_reservation_tables_company_table", "reservation_tables", ["shop_id", "table_id"]
    )

    op.create_table(
        "reservation_logs",
        _id(),
        _company(),
        sa.Column("reservation_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("old_data", postgresql.JSONB(), nullable=True),
        sa.Column("new_data", postgresql.JSONB(), nullable=True),
        sa.Column("operator_type", sa.String(30), nullable=False),
        sa.Column("operator_id", sa.String(100), nullable=True),
        sa.Column("operator_name", sa.String(100), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="reservation_logs_pkey"),
        sa.CheckConstraint(
            "operator_type IN ('customer', 'staff', 'ai', 'system')",
            name="chk_reservation_logs_operator_type",
        ),
        _company_fk("reservation_logs"),
        sa.ForeignKeyConstraint(
            ["shop_id", "reservation_id"],
            ["reservations.shop_id", "reservations.id"],
            name="fk_reservation_logs_reservation",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "idx_reservation_logs_company_reservation",
        "reservation_logs",
        ["shop_id", "reservation_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "customer_inquiries",
        _id(),
        _company(),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'open'")),
        _created_at(),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="customer_inquiries_pkey"),
        sa.CheckConstraint(
            "channel IN ('line', 'website', 'phone', 'facebook', 'other')",
            name="chk_customer_inquiries_channel",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'answered', 'transferred', 'closed')",
            name="chk_customer_inquiries_status",
        ),
        _company_fk("customer_inquiries"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["auth_users.id"],
            name="fk_customer_inquiries_customer",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "idx_customer_inquiries_company_created",
        "customer_inquiries",
        ["shop_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_customer_inquiries_company_customer",
        "customer_inquiries",
        ["shop_id", "customer_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("customer_id IS NOT NULL"),
    )

    op.create_table(
        "faqs",
        _id(),
        _company(),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.PrimaryKeyConstraint("id", name="faqs_pkey"),
        sa.UniqueConstraint("shop_id", "id", name="uq_faqs_shop_id_id"),
        _company_fk("faqs"),
    )
    op.create_index(
        "idx_faqs_company_category_active", "faqs", ["shop_id", "category", "is_active"]
    )
    op.create_index("idx_faqs_keywords", "faqs", ["keywords"], postgresql_using="gin")

    op.create_table(
        "menu_categories",
        _id(),
        _company(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id", name="menu_categories_pkey"),
        sa.UniqueConstraint("shop_id", "id", name="uq_menu_categories_shop_id_id"),
        _company_fk("menu_categories"),
    )

    op.create_table(
        "menu_items",
        _id(),
        _company(),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_test_data", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="menu_items_pkey"),
        sa.UniqueConstraint("shop_id", "id", name="uq_menu_items_shop_id_id"),
        sa.CheckConstraint("price >= 0", name="chk_menu_items_price"),
        _company_fk("menu_items"),
        sa.ForeignKeyConstraint(
            ["shop_id", "category_id"],
            ["menu_categories.shop_id", "menu_categories.id"],
            name="fk_menu_items_category",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("idx_menu_items_company_category", "menu_items", ["shop_id", "category_id"])


def downgrade() -> None:
    for table in (
        "menu_items",
        "menu_categories",
        "faqs",
        "customer_inquiries",
        "reservation_logs",
        "reservation_tables",
        "reservations",
        "pricing_rules",
        "seating_tables_rel",
        "seating_tables",
        "closing_hours",
        "business_hours",
    ):
        op.drop_table(table)
    for column in (
        "updated_at",
        "created_at",
        "is_active",
        "timezone",
        "facebook_url",
        "address",
        "phone",
    ):
        op.drop_column("booking_shops", column)
    op.drop_column("auth_users", "phone")
