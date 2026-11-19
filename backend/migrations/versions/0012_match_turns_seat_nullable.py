"""match_turns.seat_number 改為可為空（本回合首家選填），並改 comment

白薔薇的回合紀錄中，「本回合首家」是選填：遊戲沒有這個概念或沒填時為空。0010 已合併，
所以用新的 migration 修改。downgrade 時把空值補成 1 才能恢復 NOT NULL。

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_COMMENT = "一局的回合紀錄（選填）：第幾個回合、本回合首家、這款遊戲特有的內容"
OLD_TABLE_COMMENT = "一局的回合紀錄（選填）：第幾個回合、由誰主導、這款遊戲特有的內容"
COLUMN_COMMENT = "本回合首家的座位；遊戲沒有這個概念或未填時為空"
OLD_COLUMN_COMMENT = "這個回合由哪個座位的玩家主導（出牌）"


def upgrade() -> None:
    op.alter_column(
        "match_turns",
        "seat_number",
        existing_type=sa.Integer(),
        nullable=True,
        existing_nullable=False,
        comment=COLUMN_COMMENT,
        existing_comment=OLD_COLUMN_COMMENT,
    )
    op.create_table_comment("match_turns", TABLE_COMMENT, existing_comment=OLD_TABLE_COMMENT)


def downgrade() -> None:
    op.execute("UPDATE match_turns SET seat_number = 1 WHERE seat_number IS NULL")
    op.alter_column(
        "match_turns",
        "seat_number",
        existing_type=sa.Integer(),
        nullable=False,
        existing_nullable=True,
        comment=OLD_COLUMN_COMMENT,
        existing_comment=COLUMN_COMMENT,
    )
    op.create_table_comment("match_turns", OLD_TABLE_COMMENT, existing_comment=TABLE_COMMENT)
