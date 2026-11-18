"""matches tables: 局 matches、參加者 match_participants、回合紀錄 match_turns

記錄一局遊戲（openspec change add-matches-record，design.md D2）。每張表與每個欄位都有中文
comment（AGENTS.md 4.4）。matches.group_id 參照 groups.id，刪除揪團時設為空值，這局保留。

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.func.now()


def uuid_pk(comment: str) -> sa.Column:
    return sa.Column(
        "id",
        sa.Uuid(),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        comment=comment,
    )


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=NOW,
            comment="建立時間",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=NOW,
            comment="最後更新時間",
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "matches",
        uuid_pk("一局的編號"),
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.ForeignKey("games.id"),
            nullable=False,
            comment="玩的是哪一款遊戲（共用表 games）",
        ),
        sa.Column("played_on", sa.Date(), nullable=False, comment="這局進行的日期"),
        sa.Column(
            "location_type",
            sa.Text(),
            nullable=False,
            comment="地點類型：shop＝桌遊店（要有店家），home＝自家（不需要地址）",
        ),
        sa.Column(
            "shop_id",
            sa.Uuid(),
            sa.ForeignKey("booking_shops.id"),
            nullable=True,
            comment="桌遊店；自家（location_type 為 home）時為空",
        ),
        sa.Column(
            "group_id",
            sa.Uuid(),
            sa.ForeignKey("groups.id", ondelete="SET NULL"),
            nullable=True,
            comment="所屬揪團；不一定屬於揪團",
        ),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("auth_users.id"),
            nullable=False,
            comment="開局的人（開局者），開局時自動成為參加者",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'in_progress'"),
            comment="進度：in_progress＝進行中，finished＝已結束（已記錄結果）",
        ),
        sa.Column(
            "result",
            postgresql.JSONB(),
            nullable=True,
            comment=(
                '這局的結果，含 type（例如 faction 陣營勝負：{"type": "faction", '
                '"winning_faction": "rose"}）；尚未記錄結果（進行中）時為空'
            ),
        ),
        sa.Column(
            "progress",
            sa.Text(),
            nullable=True,
            comment="合作遊戲玩到哪個進度（例如第五關）；不是合作遊戲或沒填為空",
        ),
        *timestamps(),
        sa.CheckConstraint("location_type IN ('shop', 'home')", name="ck_matches_location_type"),
        sa.CheckConstraint(
            "(location_type = 'shop') = (shop_id IS NOT NULL)", name="ck_matches_location_shop"
        ),
        sa.CheckConstraint("status IN ('in_progress', 'finished')", name="ck_matches_status"),
        sa.CheckConstraint(
            "(status = 'finished') = (result IS NOT NULL)", name="ck_matches_result"
        ),
        comment="一局遊戲：玩哪一款、何時何地、誰開局、進行到哪裡與結果（不一定屬於揪團）",
    )
    op.create_index("ix_matches_game_id", "matches", ["game_id"])
    op.create_index("ix_matches_group_id", "matches", ["group_id"])

    op.create_table(
        "match_participants",
        uuid_pk("參加者的編號"),
        sa.Column(
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
            comment="屬於哪一局",
        ),
        sa.Column(
            "seat_number",
            sa.Integer(),
            nullable=False,
            comment="座位編號，從 1 開始，同一局不重複；回合紀錄用它指出是誰",
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("auth_users.id"),
            nullable=True,
            comment="帳號；玩家在 App 按加入才有，沒有帳號的人為空（不以名字比對帳號）",
        ),
        sa.Column(
            "display_name",
            sa.Text(),
            nullable=False,
            comment="顯示名稱；有帳號時取自帳號，沒有帳號時是輸入的名字（例如 Amy）",
        ),
        sa.Column(
            "faction",
            sa.Text(),
            nullable=True,
            comment="陣營；結果類型為陣營勝負時，記錄結果時填入，尚未記錄為空",
        ),
        sa.Column("score", sa.Integer(), nullable=True, comment="分數；不計分的遊戲為空，不存 0"),
        sa.Column(
            "placement", sa.Integer(), nullable=True, comment="名次，從 1 開始；不排名的遊戲為空"
        ),
        sa.Column(
            "is_winner",
            sa.Boolean(),
            nullable=True,
            comment="是否獲勝；尚未記錄結果時為空（不是 false）",
        ),
        sa.Column(
            "is_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="本人是否已確認這局的紀錄；沒有帳號的參加者永遠是 false",
        ),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="確認的時間；尚未確認為空",
        ),
        sa.UniqueConstraint("match_id", "seat_number", name="uq_match_participants_match_seat"),
        sa.UniqueConstraint("match_id", "user_id", name="uq_match_participants_match_user"),
        sa.CheckConstraint("seat_number >= 1", name="ck_match_participants_seat"),
        sa.CheckConstraint(
            "placement IS NULL OR placement >= 1", name="ck_match_participants_place"
        ),
        comment="一局的參加者：座位、帳號（沒有帳號的人只有名字）、陣營、分數與確認狀態",
    )
    op.create_index("ix_match_participants_match_id", "match_participants", ["match_id"])

    op.create_table(
        "match_turns",
        uuid_pk("回合紀錄的編號"),
        sa.Column(
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
            comment="屬於哪一局",
        ),
        sa.Column(
            "turn_number",
            sa.Integer(),
            nullable=False,
            comment="第幾個回合，從 1 開始，同一局不重複",
        ),
        sa.Column(
            "seat_number",
            sa.Integer(),
            nullable=False,
            comment="這個回合由哪個座位的玩家主導（出牌）",
        ),
        sa.Column(
            "game_data",
            postgresql.JSONB(),
            nullable=False,
            comment="這款遊戲特有的內容，格式由程式裡該遊戲的定義決定",
        ),
        sa.Column(
            "recorded_by",
            sa.Uuid(),
            sa.ForeignKey("auth_users.id"),
            nullable=False,
            comment="最後一次寫入這筆紀錄的人（覆蓋時換成覆蓋的人）",
        ),
        *timestamps(),
        sa.UniqueConstraint("match_id", "turn_number", name="uq_match_turns_match_turn"),
        sa.CheckConstraint("turn_number >= 1", name="ck_match_turns_turn"),
        comment="一局的回合紀錄（選填）：第幾個回合、由誰主導、這款遊戲特有的內容",
    )
    op.create_index("ix_match_turns_match_id", "match_turns", ["match_id"])


def downgrade() -> None:
    op.drop_table("match_turns")
    op.drop_table("match_participants")
    op.drop_table("matches")
