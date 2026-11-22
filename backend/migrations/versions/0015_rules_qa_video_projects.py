"""規則影片專案：rules_qa_video_projects

店員用手機產出規則影片的工作空間，一個專案一章（openspec/changes/add-rules-video-mobile，
design.md D1）。本章頁、參考頁、段資料等欄位等 MR 4 用到時再加。

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rules_qa_video_projects",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="專案編號（UUID）",
        ),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
            comment="這支規則影片教哪一款遊戲（桌遊被刪除時由資料庫擋下，ADR 0003）",
        ),
        sa.Column(
            "shop_id",
            sa.Uuid(),
            sa.ForeignKey("booking_shops.id"),
            nullable=False,
            comment="哪一間店的專案；店家人員只能存取自己店的專案",
        ),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("auth_users.id"),
            nullable=False,
            comment="建立專案的使用者（店家人員或管理員）",
        ),
        sa.Column(
            "chapter_number",
            sa.Integer(),
            nullable=False,
            comment="章節編號，例如《血與刃》步驟三是第 11 章；從 1 開始",
        ),
        sa.Column(
            "chapter_title",
            sa.Text(),
            nullable=False,
            comment="章節標題，例如「步驟三」；1 到 50 字",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="建立專案的時間",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="最後一次修改專案的時間；列表依此由新到舊排列",
        ),
        sa.CheckConstraint("chapter_number >= 1", name="ck_rules_qa_video_projects_chapter_number"),
        comment="規則影片專案：店員用手機產出規則影片的工作空間，一個專案一章",
    )
    op.create_index(
        "ix_rules_qa_video_projects_shop_updated",
        "rules_qa_video_projects",
        ["shop_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_rules_qa_video_projects_shop_updated", table_name="rules_qa_video_projects")
    op.drop_table("rules_qa_video_projects")
