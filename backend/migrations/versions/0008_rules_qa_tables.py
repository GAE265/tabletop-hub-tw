"""rules qa tables: 規則教學影片與規則問答的檢索段落

新增 rules_qa_videos（一款遊戲最多一支教學影片）與 rules_qa_chunks（規則書段落與向量）
（openspec change add-rules-qa，design.md D2）。向量維度讀 RULES_QA_EMBEDDING_DIM，
參照 games.id 的外鍵依 ADR 0003 不設定 cascade。

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.core.config import get_settings

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dim = get_settings().rules_qa_embedding_dim
    op.create_table(
        "rules_qa_videos",
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            primary_key=True,
            comment="這支教學影片教哪一款遊戲",
        ),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            comment="影片來源：youtube（組內上傳到 YouTube）或 file（影片生產器產生的 mp4）",
        ),
        sa.Column(
            "video_url", sa.Text(), nullable=False, comment="影片網址：YouTube 網址，或 mp4 的網址"
        ),
        sa.Column(
            "youtube_id",
            sa.Text(),
            nullable=True,
            comment="YouTube 影片 ID；source 為 youtube 時必填，file 時為空值",
        ),
        sa.Column("title", sa.Text(), nullable=False, comment="影片標題，顯示在規則教學頁"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="最後一次設定或取代這支影片的時間",
        ),
        sa.CheckConstraint("source IN ('youtube', 'file')", name="ck_rules_qa_videos_source"),
        sa.CheckConstraint(
            "(source = 'youtube') = (youtube_id IS NOT NULL)",
            name="ck_rules_qa_videos_youtube_id",
        ),
        comment="規則教學影片：一款遊戲最多一支，玩家在規則教學頁先看影片再發問",
    )
    op.create_table(
        "rules_qa_chunks",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="段落編號",
        ),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
            comment="段落屬於哪一款遊戲的規則書",
        ),
        sa.Column(
            "page",
            sa.Integer(),
            nullable=False,
            comment="段落出自規則書第幾頁，回答的出處就是這個頁碼",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="段落文字（Markdown），交給 LLM 當作回答的依據",
        ),
        sa.Column(
            "embedding",
            Vector(dim),
            nullable=False,
            comment="段落的向量，用來找出和問題最相關的段落",
        ),
        sa.Column(
            "embedding_model",
            sa.Text(),
            nullable=False,
            comment="產生向量的 embedding 模型名稱；換模型後只檢索新模型的段落，舊的要重建",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="建立索引的時間",
        ),
        sa.CheckConstraint("page >= 1", name="ck_rules_qa_chunks_page"),
        comment="規則問答的檢索段落：規則書每頁切成的段落與向量，問答時找出最相關的段落",
    )
    op.create_index("ix_rules_qa_chunks_game_id", "rules_qa_chunks", ["game_id"])


def downgrade() -> None:
    op.drop_index("ix_rules_qa_chunks_game_id", table_name="rules_qa_chunks")
    op.drop_table("rules_qa_chunks")
    op.drop_table("rules_qa_videos")
