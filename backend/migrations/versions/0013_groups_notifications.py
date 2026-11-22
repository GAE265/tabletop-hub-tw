"""揪團確定成團與站內通知：groups.confirmed_at、groups_notifications

開團主可以確定成團（confirmed_at）；成團、解散、候補正取時，替受影響的玩家建立通知
（openspec/changes/add-groups-notifications）。

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "groups",
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="開團主確定成團的時間；空值代表還沒確定成團。成團後仍可報名、候補、退出與取消",
        ),
    )
    op.create_table(
        "groups_notifications",
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
            comment="收到通知的玩家",
        ),
        sa.Column(
            "group_id",
            sa.Uuid(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
            comment="通知的揪團；揪團刪除時通知一併刪除",
        ),
        sa.Column(
            "type",
            sa.Text(),
            nullable=False,
            comment=(
                "通知種類：group_confirmed＝開團主確定成團；group_cancelled＝揪團被取消（解散）；"
                "waitlist_promoted＝候補遞補為成員"
            ),
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="玩家標成已讀的時間；空值代表未讀",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="建立通知的時間",
        ),
        sa.CheckConstraint(
            "type IN ('group_confirmed', 'group_cancelled', 'waitlist_promoted')",
            name="ck_groups_notifications_type",
        ),
        comment="揪團的站內通知：成團、解散、候補正取時通知受影響的玩家",
    )
    op.create_index(
        "ix_groups_notifications_user_created",
        "groups_notifications",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_groups_notifications_user_created", table_name="groups_notifications")
    op.drop_table("groups_notifications")
    op.drop_column("groups", "confirmed_at")
