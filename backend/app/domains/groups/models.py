"""揪團與候補的資料表（AGENTS.md §10.3）。

shop_id、organizer_id、user_id、group_games.game_id 參照共用資料表 booking_shops、auth_users、games
（AGENTS.md 第 3 節），groups 只讀不改它們的結構。
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# 揪團狀態（AGENTS.md 4.4：Enum 的每個值都要寫中文註解）
GROUP_STATUSES = (
    # 開放中：還可以報名或候補。例如週六晚上的《阿瓦隆》團，時間還沒到
    "open",
    # 已取消：開團主或管理員取消了這個揪團。例如《卡坦島》團湊不到人，開團主取消
    "cancelled",
)
# 「已結束」不儲存，由 end_at 判斷（design.md D2）

# 報名狀態
MEMBER_STATUSES = (
    # 成員：已經加入，計入人數。例如 5 人上限的《阿瓦隆》團裡的第 3 位玩家
    "member",
    # 候補：額滿後報名，排隊等遞補。例如 5 人團已滿，第 6 位報名的玩家
    "waitlisted",
)


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("capacity >= 2", name="ck_groups_capacity"),
        CheckConstraint("fee IS NULL OR fee >= 0", name="ck_groups_fee"),
        CheckConstraint("end_at > start_at", name="ck_groups_time"),
        # ended 不儲存，由 end_at 計算（design.md D2）
        CheckConstraint("status IN ('open', 'cancelled')", name="ck_groups_status"),
        {"comment": "揪團：由開團主發起的一場聚會，包含店家、時間、人數上限，以及選填的遊戲與簡介"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="揪團編號（UUID）",
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("booking_shops.id"),
        index=True,
        comment="聚會地點的店家",
    )
    organizer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("auth_users.id"),
        index=True,
        comment="開團主，也就是發起這個揪團的玩家；建立揪團時自動成為第一位成員",
    )
    title: Mapped[str] = mapped_column(
        Text,
        comment="揪團名稱，例如「週六晚上阿瓦隆新手團」",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="揪團簡介；空值代表開團主沒有填寫",
    )
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        comment="聚會開始時間",
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment="聚會結束時間，必須晚於開始時間；過了這個時間就視為已結束（不另外存狀態）",
    )
    capacity: Mapped[int] = mapped_column(
        Integer,
        comment="人數上限（包含開團主），至少 2 人；額滿後報名的玩家進入候補",
    )
    # 新台幣，每人；空值代表沒有填寫
    fee: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="每人費用（新台幣）；空值代表開團主沒有填寫",
    )
    status: Mapped[str] = mapped_column(
        Text,
        server_default=text("'open'"),
        comment=(
            "揪團狀態：open＝開放中，還可以報名或候補；cancelled＝已被開團主或管理員取消。"
            "已結束不存在這裡，由 end_at 判斷"
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="建立揪團的時間",
    )


class GroupMember(Base):
    """成員與候補放同一張表，用 status 區分；候補順位依 joined_at 計算（design.md D1）。"""

    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
        CheckConstraint("status IN ('member', 'waitlisted')", name="ck_group_members_status"),
        {"comment": "揪團的成員與候補名單：同一張表用 status 區分，候補順位依報名時間"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="這筆報名的編號（UUID）",
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("groups.id", ondelete="CASCADE"),
        index=True,
        comment="報名的揪團；揪團刪除時這筆一併刪除",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("auth_users.id"),
        comment="報名的玩家",
    )
    status: Mapped[str] = mapped_column(
        Text,
        comment="報名狀態：member＝已加入的成員，計入人數；waitlisted＝額滿後排隊候補，有人退出時依報名先後遞補",
    )
    # 報名時間；遞補成成員時不改，名單才會維持報名先後
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="報名時間；遞補成成員時不改，名單維持報名先後，也用來排候補順位",
    )


class GroupGame(Base):
    """揪團要玩的遊戲（一團可以有多款，可以沒有），依選擇的順序（update-groups-shop-game-pickers）。"""

    __tablename__ = "group_games"
    __table_args__ = (
        CheckConstraint("position >= 1", name="ck_group_games_position"),
        {"comment": "揪團要玩的遊戲：一個揪團可以有多款遊戲，也可以一款都沒有"},
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
        comment="哪一個揪團；揪團刪除時這筆一併刪除",
    )
    # 遊戲被刪除（例如共用桌遊同步）時只刪掉這筆對應，揪團保留
    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
        comment="要玩的遊戲；遊戲被刪除時只刪掉這筆對應，揪團本身保留",
    )
    position: Mapped[int] = mapped_column(
        Integer, comment="開團主選擇的順序，從 1 開始；畫面依這個順序顯示遊戲"
    )
