"""規則影片專案改成整個遊戲一支影片：章節欄位改為可空，加上分類結果

店員建立專案時只選遊戲，不選章節；AI 先把整本規則書分成「開局、走完一輪、獲勝方式」三格與
排除清單（add-rules-video-mobile 整本範圍）。舊的單章專案（命令列與既有資料）照舊有章節。

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "rules_qa_video_projects"


def upgrade() -> None:
    op.alter_column(
        TABLE,
        "chapter_number",
        existing_type=sa.Integer(),
        nullable=True,
        comment=(
            "章節編號（舊的單章專案），例如《血與刃》步驟三是第 11 章；空值代表整個遊戲一支影片"
        ),
    )
    op.alter_column(
        TABLE,
        "chapter_title",
        existing_type=sa.Text(),
        nullable=True,
        comment="章節標題（舊的單章專案），1 到 50 字；空值代表整個遊戲一支影片",
    )
    op.alter_column(
        TABLE,
        "chapter_pages",
        existing_type=postgresql.ARRAY(sa.Integer()),
        existing_nullable=False,
        comment="這支影片用到的頁（整個遊戲時預設全選）；空陣列代表還沒選",
    )
    op.alter_column(
        TABLE,
        "reference_pages",
        existing_type=postgresql.ARRAY(sa.Integer()),
        existing_nullable=False,
        comment="參考頁（舊的單章專案用）；整個遊戲一支影片時一律是空陣列",
    )
    op.add_column(
        TABLE,
        sa.Column(
            "classification",
            postgresql.JSONB(),
            nullable=True,
            comment=(
                "AI 把規則書分成三格的結果：slots（開局、走完一輪、獲勝方式各自引用的原文片段）、"
                "excluded（不講的片段與原因，店員看不到）、dropped（引用不到原文而沒採用的）；"
                "空值代表舊的單章專案或還沒分類"
            ),
        ),
    )
    op.create_table_comment(
        TABLE,
        "規則影片專案：店員用手機產出規則影片的工作空間，一個專案一支影片（整個遊戲；舊資料是一章）",
        existing_comment="規則影片專案：店員用手機產出規則影片的工作空間，一個專案一章",
    )


def downgrade() -> None:
    op.create_table_comment(
        TABLE,
        "規則影片專案：店員用手機產出規則影片的工作空間，一個專案一章",
        existing_comment=(
            "規則影片專案：店員用手機產出規則影片的工作空間，一個專案一支影片（整個遊戲；舊資料是一章）"
        ),
    )
    op.drop_column(TABLE, "classification")
    # 整個遊戲的專案沒有章節，降版時刪掉這些專案與它們的工作（工作的外鍵沒有 cascade）
    whole_game = f"SELECT id FROM {TABLE} WHERE chapter_number IS NULL OR chapter_title IS NULL"
    op.execute(f"DELETE FROM rules_qa_video_jobs WHERE project_id IN ({whole_game})")
    op.execute(f"DELETE FROM {TABLE} WHERE id IN ({whole_game})")
    op.alter_column(TABLE, "chapter_title", existing_type=sa.Text(), nullable=False)
    op.alter_column(TABLE, "chapter_number", existing_type=sa.Integer(), nullable=False)
