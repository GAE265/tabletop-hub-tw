"""記錄一局遊戲的資料表：局、參加者、回合紀錄（AGENTS.md 10.2、openspec add-matches-record）。

game_id、shop_id、created_by、group_id 參照共用資料表 games、booking_shops、auth_users 與揪團
groups；matches 只讀不改它們的結構。每張表、每個欄位都有中文 comment（AGENTS.md 4.4）。
"""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MatchStatus(StrEnum):
    """一局目前的進度。已記錄結果就是 finished，狀態只由記錄結果改變。"""

    # 進行中：還在玩或還沒記錄結果，可以加入或移除參加者、記錄回合。例：血與刃的白薔薇玩到一半
    IN_PROGRESS = "in_progress"
    # 已結束：已記錄結果，不能再加入或移除參加者，參加者可以確認。例：白薔薇宣布薔薇陣營獲勝之後
    FINISHED = "finished"


class LocationType(StrEnum):
    """這局在哪裡玩。"""

    # 桌遊店：要帶店家（shop_id）。例：在合作桌遊店開的白薔薇揪團
    SHOP = "shop"
    # 自家：在朋友或自己家玩，不需要地址、也沒有店家。例：週末在 Amy 家玩阿瓦隆
    HOME = "home"


class MatchNotificationType(StrEnum):
    """戰績通知的種類。文字不存，由前端依種類與那一局的資料組成。"""

    # 結果已記錄：這一局的結果剛被記錄（第一次記錄或帶 overwrite 覆蓋），收件人需要（重新）確認。
    # 記錄成功時發給記錄者以外、有帳號的參加者；覆蓋會清掉大家的確認，所以每次都發。
    # 例：血與刃的白薔薇一局 4 人，玩家甲記錄「薔薇陣營獲勝」，有帳號的玩家乙、丙各收到一則
    RESULT_RECORDED = "match_result_recorded"


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), comment="建立時間")


def _updated_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), comment="最後更新時間")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("location_type IN ('shop', 'home')", name="ck_matches_location_type"),
        CheckConstraint(
            "(location_type = 'shop') = (shop_id IS NOT NULL)", name="ck_matches_location_shop"
        ),
        CheckConstraint("status IN ('in_progress', 'finished')", name="ck_matches_status"),
        CheckConstraint("(status = 'finished') = (result IS NOT NULL)", name="ck_matches_result"),
        {"comment": "一局遊戲：玩哪一款、何時何地、誰開局、進行到哪裡與結果（不一定屬於揪團）"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="一局的編號",
    )
    game_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("games.id"), index=True, comment="玩的是哪一款遊戲（共用表 games）"
    )
    played_on: Mapped[date] = mapped_column(Date, comment="這局進行的日期")
    location_type: Mapped[str] = mapped_column(
        Text, comment="地點類型：shop＝桌遊店（要有店家），home＝自家（不需要地址）"
    )
    shop_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("booking_shops.id"),
        nullable=True,
        comment="桌遊店；自家（location_type 為 home）時為空",
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所屬揪團；不一定屬於揪團",
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auth_users.id"), comment="開局的人（開局者），開局時自動成為參加者"
    )
    status: Mapped[str] = mapped_column(
        Text,
        server_default=text("'in_progress'"),
        comment="進度：in_progress＝進行中，finished＝已結束（已記錄結果）",
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            '這局的結果，含 type（例如 faction 陣營勝負：{"type": "faction", '
            '"winning_faction": "rose"}）；尚未記錄結果（進行中）時為空'
        ),
    )
    progress: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="合作遊戲玩到哪個進度（例如第五關）；不是合作遊戲或沒填為空"
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class MatchParticipant(Base):
    __tablename__ = "match_participants"
    __table_args__ = (
        UniqueConstraint("match_id", "seat_number", name="uq_match_participants_match_seat"),
        UniqueConstraint("match_id", "user_id", name="uq_match_participants_match_user"),
        CheckConstraint("seat_number >= 1", name="ck_match_participants_seat"),
        CheckConstraint("placement IS NULL OR placement >= 1", name="ck_match_participants_place"),
        {"comment": "一局的參加者：座位、帳號（沒有帳號的人只有名字）、陣營、分數與確認狀態"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="參加者的編號",
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("matches.id", ondelete="CASCADE"), index=True, comment="屬於哪一局"
    )
    seat_number: Mapped[int] = mapped_column(
        Integer, comment="座位編號，從 1 開始，同一局不重複；回合紀錄用它指出是誰"
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("auth_users.id"),
        nullable=True,
        comment="帳號；玩家在 App 按加入才有，沒有帳號的人為空（不以名字比對帳號）",
    )
    display_name: Mapped[str] = mapped_column(
        Text, comment="顯示名稱；有帳號時取自帳號，沒有帳號時是輸入的名字（例如 Amy）"
    )
    faction: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="陣營；結果類型為陣營勝負時，記錄結果時填入，尚未記錄為空"
    )
    score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="分數；不計分的遊戲為空，不存 0"
    )
    placement: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="名次，從 1 開始；不排名的遊戲為空"
    )
    is_winner: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="是否獲勝；尚未記錄結果時為空（不是 false）"
    )
    is_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        comment="本人是否已確認這局的紀錄；沒有帳號的參加者永遠是 false",
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="確認的時間；尚未確認為空"
    )


class MatchTurn(Base):
    __tablename__ = "match_turns"
    __table_args__ = (
        UniqueConstraint("match_id", "turn_number", name="uq_match_turns_match_turn"),
        CheckConstraint("turn_number >= 1", name="ck_match_turns_turn"),
        {"comment": "一局的回合紀錄（選填）：第幾個回合、本回合首家、這款遊戲特有的內容"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="回合紀錄的編號",
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("matches.id", ondelete="CASCADE"), index=True, comment="屬於哪一局"
    )
    turn_number: Mapped[int] = mapped_column(Integer, comment="第幾個回合，從 1 開始，同一局不重複")
    seat_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="本回合首家的座位；遊戲沒有這個概念或未填時為空"
    )
    game_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, comment="這款遊戲特有的內容，格式由程式裡該遊戲的定義決定"
    )
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auth_users.id"), comment="最後一次寫入這筆紀錄的人（覆蓋時換成覆蓋的人）"
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class MatchNotification(Base):
    """戰績的站內通知；文字不儲存，由 type 與那一局目前的資料組成（照 groups／booking 的做法）。"""

    __tablename__ = "matches_notifications"
    __table_args__ = (
        CheckConstraint("type IN ('match_result_recorded')", name="ck_matches_notifications_type"),
        Index("ix_matches_notifications_user_created", "user_id", "created_at"),
        {"comment": "戰績的站內通知：一局的結果被記錄或覆蓋時，通知其他有帳號的參加者去確認"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="通知編號（UUID）",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auth_users.id"), comment="收到通知的玩家"
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("matches.id", ondelete="CASCADE"),
        comment="通知的那一局；一局刪除時通知一併刪除",
    )
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("auth_users.id"),
        comment="記錄（或覆蓋）這一局結果、觸發這則通知的使用者",
    )
    type: Mapped[str] = mapped_column(
        Text,
        comment="通知種類：match_result_recorded＝這一局的結果被記錄或覆蓋，收件人需要重新確認",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="玩家標成已讀的時間；空值代表未讀"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="建立通知的時間"
    )
