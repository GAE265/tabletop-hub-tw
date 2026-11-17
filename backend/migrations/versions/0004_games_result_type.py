"""games result_type: 共用桌遊表新增結果類型欄位

只加一個欄位與其 CHECK。欄位可為空、沒有預設值，既有桌遊升級後 result_type 為空
（openspec change add-games-result-type，design.md D2）。已合併的 0002 不修改。

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column(
            "result_type",
            sa.Text(),
            nullable=True,
            comment=(
                "這款遊戲的結果怎麼記：faction（陣營勝負，記哪一方獲勝，例如阿瓦隆）、"
                "score（個人分數，記每人分數與名次，例如馬可波羅）、"
                "cooperative（合作，記全隊是否通過與玩到哪個進度，例如瘋狂鬼宅）；"
                "空值代表這款遊戲尚未設定結果類型"
            ),
        ),
    )
    op.create_check_constraint(
        "ck_games_result_type",
        "games",
        "result_type IN ('faction', 'score', 'cooperative')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_games_result_type", "games", type_="check")
    op.drop_column("games", "result_type")
