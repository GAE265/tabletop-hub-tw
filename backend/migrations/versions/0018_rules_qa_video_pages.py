"""規則影片專案的頁面文字：rules_qa_video_projects 加上本章頁、參考頁、編輯後的文字

店員在產生草稿前逐頁檢視辨識出的文字、修正錯字、刪除不屬於本章的段落；
編輯後的文字存在專案上，不改 games_manual（openspec/changes/add-rules-video-mobile，
design.md D11）。

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

TABLE = "rules_qa_video_projects"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "chapter_pages",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{}",
            comment="本章用規則書的哪幾頁（games_manual 的頁碼）；空陣列代表還沒選",
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "reference_pages",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default="{}",
            comment="參考頁：只查牌名與分類，不可寫成旁白；空陣列代表沒有參考頁",
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "page_texts",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment=(
                "店員編輯後的規則書文字：{頁碼: {text: 編輯後的文字, "
                "original_hash: 編輯時原文的雜湊}}，本章頁與參考頁都有；"
                "草稿與涵蓋檢查只用這份文字；空物件代表還沒存過"
            ),
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "pages_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="頁面文字每存一次加 1；草稿記下自己用的是哪一版，不同就標示依舊文字產生",
        ),
    )


def downgrade() -> None:
    for name in ("pages_version", "page_texts", "reference_pages", "chapter_pages"):
        op.drop_column(TABLE, name)
