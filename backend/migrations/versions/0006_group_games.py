"""group games: 揪團可以選多款遊戲

新增 group_games（揪團 ↔ 遊戲，依選擇的順序），把既有 groups.game_id 搬進去後移除該欄位
（openspec change update-groups-shop-game-pickers，design.md D1）。降級時把每個揪團順序第一
的遊戲放回 groups.game_id。已合併的 0003 不修改。

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "group_games",
        sa.Column(
            "group_id",
            sa.Uuid(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            primary_key=True,
            comment="哪一個揪團；揪團刪除時這筆一併刪除",
        ),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            primary_key=True,
            comment="要玩的遊戲；遊戲被刪除時只刪掉這筆對應，揪團本身保留",
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            comment="開團主選擇的順序，從 1 開始；畫面依這個順序顯示遊戲",
        ),
        sa.CheckConstraint("position >= 1", name="ck_group_games_position"),
        comment="揪團要玩的遊戲：一個揪團可以有多款遊戲，也可以一款都沒有",
    )
    op.execute(
        "INSERT INTO group_games (group_id, game_id, position) "
        "SELECT id, game_id, 1 FROM groups WHERE game_id IS NOT NULL"
    )
    op.drop_column("groups", "game_id")


def downgrade() -> None:
    op.add_column(
        "groups",
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE groups SET game_id = ("
        "SELECT game_id FROM group_games WHERE group_games.group_id = groups.id "
        "ORDER BY position LIMIT 1)"
    )
    op.drop_table("group_games")
