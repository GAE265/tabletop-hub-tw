"""groups table comments: 替 groups、group_members 補上中文說明

AGENTS.md 1.10 版規定每張資料表、每個欄位都要用 comment 寫中文說明；這兩張表在 0003 建立時
還沒有這條規則，這裡補上（group_games 在 0007 建立時已經有說明）。只改說明，不改結構。

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 說明文字與 app/domains/groups/models.py 相同；migration 不 import model，所以這裡另外寫一份
TABLE_COMMENTS = {
    "groups": "揪團：由開團主發起的一場聚會，包含店家、時間、人數上限，以及選填的遊戲與簡介",
    "group_members": "揪團的成員與候補名單：同一張表用 status 區分，候補順位依報名時間",
}

COLUMN_COMMENTS = {
    "groups": {
        "id": "揪團編號（UUID）",
        "shop_id": "聚會地點的店家",
        "organizer_id": "開團主，也就是發起這個揪團的玩家；建立揪團時自動成為第一位成員",
        "title": "揪團名稱，例如「週六晚上阿瓦隆新手團」",
        "description": "揪團簡介；空值代表開團主沒有填寫",
        "start_at": "聚會開始時間",
        "end_at": "聚會結束時間，必須晚於開始時間；過了這個時間就視為已結束（不另外存狀態）",
        "capacity": "人數上限（包含開團主），至少 2 人；額滿後報名的玩家進入候補",
        "fee": "每人費用（新台幣）；空值代表開團主沒有填寫",
        "status": (
            "揪團狀態：open＝開放中，還可以報名或候補；cancelled＝已被開團主或管理員取消。"
            "已結束不存在這裡，由 end_at 判斷"
        ),
        "created_at": "建立揪團的時間",
    },
    "group_members": {
        "id": "這筆報名的編號（UUID）",
        "group_id": "報名的揪團；揪團刪除時這筆一併刪除",
        "user_id": "報名的玩家",
        "status": (
            "報名狀態：member＝已加入的成員，計入人數；"
            "waitlisted＝額滿後排隊候補，有人退出時依報名先後遞補"
        ),
        "joined_at": "報名時間；遞補成成員時不改，名單維持報名先後，也用來排候補順位",
    },
}


def upgrade() -> None:
    for table, comment in TABLE_COMMENTS.items():
        op.create_table_comment(table, comment)
    for table, columns in COLUMN_COMMENTS.items():
        for column, comment in columns.items():
            op.alter_column(table, column, comment=comment)


def downgrade() -> None:
    for table, columns in COLUMN_COMMENTS.items():
        for column, comment in columns.items():
            op.alter_column(table, column, comment=None, existing_comment=comment)
    for table, comment in TABLE_COMMENTS.items():
        op.drop_table_comment(table, existing_comment=comment)
