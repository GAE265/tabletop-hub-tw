"""規則影片的工作加上輸入（input）：修改的工作要記下店員的修改要求與指定段

用一句話修改（add-rules-video-mobile MR 11）建立 kind=revise 的工作時，修改要求存在這個欄位；
背景執行緒的處理函式從這裡讀。草稿、產生影片的工作不需要輸入，維持空值。

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "rules_qa_video_jobs"
INPUT_COMMENT = (
    "工作的輸入：修改的工作（revise）是 request（店員的修改要求）與 segment_key"
    "（指定只改哪一段，空值代表不指定）；空值代表這種工作不需要輸入（草稿、產生影片）"
)


def upgrade() -> None:
    op.add_column(
        TABLE, sa.Column("input", postgresql.JSONB(), nullable=True, comment=INPUT_COMMENT)
    )


def downgrade() -> None:
    op.drop_column(TABLE, "input")
