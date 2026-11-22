"""規則影片的用語對照表：rules_qa_video_terms

每款遊戲一份、所有店家共用，由管理員上傳；AI 產生草稿時照表用詞
（openspec/changes/add-rules-video-mobile，design.md D4）。

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rules_qa_video_terms",
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            primary_key=True,
            comment="哪一款遊戲的對照表；每款遊戲一份（桌遊被刪除時由資料庫擋下，ADR 0003）",
        ),
        sa.Column(
            "terms",
            postgresql.JSONB(),
            nullable=False,
            comment=(
                "用語對照，格式同 terms.json：每筆有 en（規則書原文）、zh（影片用詞）、"
                "key（對到的素材或區域，可多筆對到同一個）、avoid（不要用的詞）、"
                "category（generic＝泛稱、single＝單一種牌）；空陣列代表確認不使用對照表"
            ),
        ),
        sa.Column(
            "updated_by",
            sa.Uuid(),
            sa.ForeignKey("auth_users.id"),
            nullable=False,
            comment="最後一次上傳的管理員",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="最後一次上傳的時間",
        ),
        comment="規則影片的用語對照表：每款遊戲一份，管理員上傳，AI 產生草稿時照表用詞",
    )


def downgrade() -> None:
    op.drop_table("rules_qa_video_terms")
