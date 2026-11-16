"""games_manual：規則書每一頁的 Markdown 文字（rules_ingest）

沿用開發資料庫既有的表名與欄位。和舊表的差別：外鍵不加 ON DELETE CASCADE（ADR 0003：
參照 games.id 的表不可跟著桌遊刪除），並新增 page >= 1 的檢查。

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "games_manual",
        sa.Column("games_id", sa.BigInteger(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("games_id", "page", name="games_manual_pkey"),
        sa.ForeignKeyConstraint(["games_id"], ["games.id"], name="games_manual_games_id_fkey"),
        sa.CheckConstraint("page >= 1", name="ck_games_manual_page_positive"),
    )


def downgrade() -> None:
    op.drop_table("games_manual")
