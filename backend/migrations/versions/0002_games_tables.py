"""games tables: 共用桌遊表 games、genres、game_genres 與 games_advisor 的 4 張表

共用表的規則見 AGENTS.md 第 3 節「共用資料表」。games.id 用自動給號的整數是 §4.4 的例外
（主鍵預設 UUID，只有固定的小型分類表可以用流水號），理由見 docs/adr/0003-shared-games-table.md。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ⚠️ 固定的 8 個類型，要和 spec §3.2、games.json 的 types 代碼一致
GENRES = [
    ("party", "派對"),
    ("strategy", "策略"),
    ("thematic", "主題"),
    ("war", "戰爭"),
    ("abstract", "抽象"),
    ("customizable", "集換"),
    ("children", "孩童"),
    ("family", "家庭"),
]


def uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def game_fk() -> sa.Column:
    return sa.Column(
        "game_id", sa.BigInteger(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    dim = get_settings().games_advisor_embedding_dim

    op.create_table(
        "games",
        # 沒給 id 就自動給號；給了就照給的寫入（同步共用桌遊資料時要用，spec §8.11）
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("bgg_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("english_name", sa.Text(), nullable=False),
        sa.Column("min_players", sa.Integer(), nullable=False),
        sa.Column("max_players", sa.Integer(), nullable=False),
        sa.Column("min_playtime", sa.Integer(), nullable=False),
        sa.Column("max_playtime", sa.Integer(), nullable=False),
        sa.Column("min_age", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Double(), nullable=False),
        sa.Column("categories", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("mechanics", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.UniqueConstraint("bgg_id", name="uq_games_bgg_id"),
        sa.CheckConstraint("id > 0", name="ck_games_id_positive"),
        sa.CheckConstraint("min_players BETWEEN 1 AND max_players", name="ck_games_players"),
        sa.CheckConstraint("min_playtime BETWEEN 1 AND max_playtime", name="ck_games_playtime"),
        sa.CheckConstraint("min_age >= 0", name="ck_games_min_age"),
        sa.CheckConstraint("weight BETWEEN 1 AND 5", name="ck_games_weight"),
    )
    genres = op.create_table(
        "genres",
        # 固定的小型分類表，主鍵用流水號（AGENTS.md §4.4）；找類型一律用 code，不寫死 id
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.UniqueConstraint("code", name="uq_genres_code"),
        sa.UniqueConstraint("name", name="uq_genres_name"),
    )
    op.bulk_insert(genres, [{"code": code, "name": name} for code, name in GENRES])
    op.create_table(
        "game_genres",
        uuid_pk(),
        game_fk(),
        sa.Column("genre_id", sa.BigInteger(), sa.ForeignKey("genres.id"), nullable=False),
        sa.UniqueConstraint("game_id", "genre_id", name="uq_game_genres_game_genre"),
    )

    op.create_table(
        "games_advisor_review_summaries",
        uuid_pk(),
        game_fk(),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(dim), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.UniqueConstraint("game_id", name="uq_games_advisor_review_summaries_game_id"),
    )
    op.create_table(
        "games_advisor_tags",
        uuid_pk(),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.UniqueConstraint("code", name="uq_games_advisor_tags_code"),
        sa.UniqueConstraint("name", name="uq_games_advisor_tags_name"),
        sa.CheckConstraint("code ~ '^[a-z][a-z0-9_]*$'", name="ck_games_advisor_tags_code"),
    )
    op.create_table(
        "games_advisor_game_tags",
        uuid_pk(),
        game_fk(),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("games_advisor_tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Double(), nullable=False),
        sa.UniqueConstraint("game_id", "tag_id", name="uq_games_advisor_game_tags_game_tag"),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1", name="ck_games_advisor_game_tags_confidence"
        ),
    )
    op.create_table(
        "games_advisor_review_excerpts",
        uuid_pk(),
        game_fk(),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(dim), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("site_name", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "language IN ('zh-TW', 'en')", name="ck_games_advisor_review_excerpts_language"
        ),
    )


def downgrade() -> None:
    op.drop_table("games_advisor_review_excerpts")
    op.drop_table("games_advisor_game_tags")
    op.drop_table("games_advisor_tags")
    op.drop_table("games_advisor_review_summaries")
    op.drop_table("game_genres")
    op.drop_table("genres")
    op.drop_table("games")
