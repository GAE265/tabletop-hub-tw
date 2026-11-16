"""groups tables: 揪團 groups 與成員／候補 group_members

成員與候補放同一張表，用 status 區分（openspec change add-groups-calendar，design.md D1）。

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def upgrade() -> None:
    op.create_table(
        "groups",
        uuid_pk(),
        sa.Column("shop_id", sa.Uuid(), sa.ForeignKey("booking_shops.id"), nullable=False),
        sa.Column("organizer_id", sa.Uuid(), sa.ForeignKey("auth_users.id"), nullable=False),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("fee", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("capacity >= 2", name="ck_groups_capacity"),
        sa.CheckConstraint("fee IS NULL OR fee >= 0", name="ck_groups_fee"),
        sa.CheckConstraint("end_at > start_at", name="ck_groups_time"),
        sa.CheckConstraint("status IN ('open', 'cancelled')", name="ck_groups_status"),
    )
    op.create_index("ix_groups_shop_id", "groups", ["shop_id"])
    op.create_index("ix_groups_organizer_id", "groups", ["organizer_id"])
    op.create_index("ix_groups_start_at", "groups", ["start_at"])

    op.create_table(
        "group_members",
        uuid_pk(),
        sa.Column(
            "group_id", sa.Uuid(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("auth_users.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
        sa.CheckConstraint("status IN ('member', 'waitlisted')", name="ck_group_members_status"),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"])


def downgrade() -> None:
    op.drop_table("group_members")
    op.drop_table("groups")
