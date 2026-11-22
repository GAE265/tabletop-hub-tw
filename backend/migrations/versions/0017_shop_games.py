"""shop games: 店家庫存（每間店有哪些桌遊）

新增 shop_games。只記「有沒有」，不記數量。

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shop_games",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="庫存紀錄的識別碼",
        ),
        sa.Column(
            "shop_id",
            sa.Uuid(),
            sa.ForeignKey("booking_shops.id", ondelete="CASCADE"),
            nullable=False,
            comment="哪一間店；店家被刪除時庫存一併刪除",
        ),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            nullable=False,
            comment="店裡有的桌遊；桌遊被刪除時只刪掉這筆庫存",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="加入庫存的時間（UTC）",
        ),
        sa.UniqueConstraint("shop_id", "game_id", name="uq_shop_games_shop_game"),
        comment="店家庫存：每間店有哪些桌遊，同一間店同一款桌遊只有一筆，目前不記數量",
    )


def downgrade() -> None:
    op.drop_table("shop_games")
