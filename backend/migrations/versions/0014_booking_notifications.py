"""訂位站內通知：booking_notifications

訂位成功時，替訂位的玩家與該店的店家人員建立通知（openspec/changes/add-booking-notifications）。

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "booking_notifications",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="通知編號（UUID）",
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("auth_users.id"),
            nullable=False,
            comment="收到通知的使用者（訂位的玩家，或該店的店家人員）",
        ),
        sa.Column(
            "reservation_id",
            sa.BigInteger(),
            sa.ForeignKey("reservations.id", ondelete="RESTRICT"),
            nullable=False,
            comment="通知的訂位",
        ),
        sa.Column(
            "type",
            sa.Text(),
            nullable=False,
            comment=(
                "通知種類：booking_confirmed＝給訂位玩家的訂位成功；"
                "shop_new_booking＝給店家人員的新訂位"
            ),
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="使用者標成已讀的時間；空值代表未讀",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="建立通知的時間",
        ),
        sa.CheckConstraint(
            "type IN ('booking_confirmed', 'shop_new_booking')",
            name="ck_booking_notifications_type",
        ),
        comment="訂位的站內通知：訂位成功時通知訂位的玩家與該店的店家人員",
    )
    op.create_index(
        "ix_booking_notifications_user_created",
        "booking_notifications",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_booking_notifications_user_created", table_name="booking_notifications")
    op.drop_table("booking_notifications")
