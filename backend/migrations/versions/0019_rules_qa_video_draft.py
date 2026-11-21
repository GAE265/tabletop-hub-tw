"""規則影片專案的草稿：rules_qa_video_projects 加上段資料正本、版本、涵蓋檢查

段資料以資料庫為正本：失敗時原本的草稿不變、用版本偵測同時修改
（openspec/changes/add-rules-video-mobile，design.md D11）。

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "rules_qa_video_projects"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "video",
            postgresql.JSONB(),
            nullable=True,
            comment=(
                "段資料正本（video.json 的內容，含每段的狀態與修改紀錄、素材的檔名與區域）；"
                "空值代表還沒有草稿"
            ),
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "video_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="段資料每改一次加 1；工作開始時記下、寫入前比對，不同就不覆寫",
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "coverage",
            postgresql.JSONB(),
            nullable=True,
            comment=(
                "最近一次規則涵蓋檢查：status＝done 時附 report，not_done 時附 reason；"
                "空值代表還沒檢查"
            ),
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "coverage_version",
            sa.Integer(),
            nullable=True,
            comment="涵蓋檢查是對哪一個 video_version 做的；不同就是過期；空值代表還沒檢查",
        ),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "draft_pages_version",
            sa.Integer(),
            nullable=True,
            comment=(
                "草稿用的是哪一版頁面文字；與 pages_version 不同時，草稿標示依舊文字產生；"
                "空值代表還沒有草稿"
            ),
        ),
    )


def downgrade() -> None:
    for name in ("draft_pages_version", "coverage_version", "coverage", "video_version", "video"):
        op.drop_column(TABLE, name)
