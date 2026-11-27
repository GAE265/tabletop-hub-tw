"""戰績的站內通知：matches_notifications

一局的結果被記錄或覆蓋時，替其他有帳號的參加者建立通知，請他們確認這局的紀錄
（docs/mr_info/feature-matches-notifications.md）。結構照 groups_notifications。

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matches_notifications",
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
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
            comment="通知的那一局；一局刪除時通知一併刪除",
        ),
        sa.Column(
            "recorded_by",
            sa.Uuid(),
            sa.ForeignKey("auth_users.id"),
            nullable=False,
            comment="記錄（或覆蓋）這一局結果、觸發這則通知的使用者",
        ),
        sa.Column(
            "type",
            sa.Text(),
            nullable=False,
            comment="通知種類：match_result_recorded＝這一局的結果被記錄或覆蓋，收件人需要重新確認",
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
            "type IN ('match_result_recorded')", name="ck_matches_notifications_type"
        ),
        comment="戰績的站內通知：一局的結果被記錄或覆蓋時，通知其他有帳號的參加者去確認",
    )
    op.create_index(
        "ix_matches_notifications_user_created",
        "matches_notifications",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_matches_notifications_user_created", table_name="matches_notifications")
    op.drop_table("matches_notifications")
