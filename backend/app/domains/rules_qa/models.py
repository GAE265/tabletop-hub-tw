"""規則教學與問答的資料表（openspec change add-rules-qa，design.md D2）。

game_id 參照共用表 games.id；依 ADR 0003 不設定 cascade，桌遊被刪除時由資料庫擋下。
"""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# 影片來源：
# - youtube：組內上傳到 YouTube 的教學影片，例如《血與刃的白薔薇》的規則影片
# - file：規則影片生產器產生、存在我們雲端儲存的 mp4（add-rules-video-maker 才會寫入）
VIDEO_SOURCES = ("youtube", "file")


class RulesQaVideo(Base):
    __tablename__ = "rules_qa_videos"
    __table_args__ = (
        CheckConstraint("source IN ('youtube', 'file')", name="ck_rules_qa_videos_source"),
        CheckConstraint(
            "(source = 'youtube') = (youtube_id IS NOT NULL)",
            name="ck_rules_qa_videos_youtube_id",
        ),
        {"comment": "規則教學影片：一款遊戲最多一支，玩家在規則教學頁先看影片再發問"},
    )

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id"),
        primary_key=True,
        comment="這支教學影片教哪一款遊戲",
    )
    source: Mapped[str] = mapped_column(
        Text, comment="影片來源：youtube（組內上傳到 YouTube）或 file（影片生產器產生的 mp4）"
    )
    video_url: Mapped[str] = mapped_column(Text, comment="影片網址：YouTube 網址，或 mp4 的網址")
    youtube_id: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="YouTube 影片 ID；source 為 youtube 時必填，file 時為空值"
    )
    title: Mapped[str] = mapped_column(Text, comment="影片標題，顯示在規則教學頁")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="最後一次設定或取代這支影片的時間",
    )


class RulesQaChunk(Base):
    __tablename__ = "rules_qa_chunks"
    __table_args__ = (
        CheckConstraint("page >= 1", name="ck_rules_qa_chunks_page"),
        {"comment": "規則問答的檢索段落：規則書每頁切成的段落與向量，問答時找出最相關的段落"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="段落編號",
    )
    game_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("games.id"), index=True, comment="段落屬於哪一款遊戲的規則書"
    )
    page: Mapped[int] = mapped_column(
        Integer, comment="段落出自規則書第幾頁，回答的出處就是這個頁碼"
    )
    content: Mapped[str] = mapped_column(
        Text, comment="段落文字（Markdown），交給 LLM 當作回答的依據"
    )
    # 維度由設定決定（RULES_QA_EMBEDDING_DIM），寫在 migration，不寫死在 model
    embedding: Mapped[list[float]] = mapped_column(
        Vector(), comment="段落的向量，用來找出和問題最相關的段落"
    )
    embedding_model: Mapped[str] = mapped_column(
        Text, comment="產生向量的 embedding 模型名稱；換模型後只檢索新模型的段落，舊的要重建"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="建立索引的時間"
    )


class RulesQaVideoProject(Base):
    """規則影片專案（add-rules-video-mobile design.md D1）。

    本章頁、參考頁、段資料等欄位由「頁面文字」「草稿工作」用到時再加；目前步驟（step）不存欄位，由狀態推出。
    """

    __tablename__ = "rules_qa_video_projects"
    __table_args__ = (
        CheckConstraint("chapter_number >= 1", name="ck_rules_qa_video_projects_chapter_number"),
        Index("ix_rules_qa_video_projects_shop_updated", "shop_id", "updated_at"),
        {"comment": "規則影片專案：店員用手機產出規則影片的工作空間，一個專案一章"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="專案編號（UUID）",
    )
    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id"),
        comment="這支規則影片教哪一款遊戲（桌遊被刪除時由資料庫擋下，ADR 0003）",
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("booking_shops.id"),
        comment="哪一間店的專案；店家人員只能存取自己店的專案",
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auth_users.id"), comment="建立專案的使用者（店家人員或管理員）"
    )
    chapter_number: Mapped[int] = mapped_column(
        Integer, comment="章節編號，例如《血與刃》步驟三是第 11 章；從 1 開始"
    )
    chapter_title: Mapped[str] = mapped_column(Text, comment="章節標題，例如「步驟三」；1 到 50 字")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="建立專案的時間"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="最後一次修改專案的時間；列表依此由新到舊排列",
    )


# 工作種類與狀態；每個值的意思寫在 migration 0016 的欄位說明（add-rules-video-mobile design.md D2）
JOB_KINDS = ("draft", "render", "revise")
JOB_STATUSES = ("queued", "running", "succeeded", "failed")
ACTIVE_JOB_INDEX = "ux_rules_qa_video_jobs_active"


class RulesQaVideoJob(Base):
    """規則影片的非同步工作。kind：draft＝產生草稿、render＝產生影片、revise＝用一句話修改；
    status：queued＝等待、running＝處理中、succeeded＝完成、failed＝失敗。"""

    __tablename__ = "rules_qa_video_jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('draft', 'render', 'revise')", name="ck_rules_qa_video_jobs_kind"
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_rules_qa_video_jobs_status",
        ),
        CheckConstraint("progress >= 0 AND progress <= 1", name="ck_rules_qa_video_jobs_progress"),
        Index(
            ACTIVE_JOB_INDEX,
            "project_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index("ix_rules_qa_video_jobs_project_created", "project_id", "created_at"),
        Index(
            "ix_rules_qa_video_jobs_queued",
            "created_at",
            postgresql_where=text("status = 'queued'"),
        ),
        {"comment": "規則影片的非同步工作：產生草稿、產生影片、修改，由後端的背景執行緒依序處理"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        comment="工作編號（UUID）",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rules_qa_video_projects.id"), comment="屬於哪一個影片專案"
    )
    kind: Mapped[str] = mapped_column(
        Text, comment="工作種類：draft＝產生草稿；render＝產生影片；revise＝用一句話修改"
    )
    status: Mapped[str] = mapped_column(
        Text,
        server_default="queued",
        comment="狀態：queued＝等待；running＝處理中；succeeded＝完成；failed＝失敗",
    )
    progress: Mapped[float] = mapped_column(
        Double, server_default="0", comment="進度 0 到 1；完成時為 1"
    )
    message: Mapped[str | None] = mapped_column(
        Text, comment="現在在做什麼，給店員看；空值代表還沒有回報"
    )
    error: Mapped[str | None] = mapped_column(
        Text, comment="失敗原因與下一步，給店員看；空值代表沒有失敗"
    )
    error_detail: Mapped[str | None] = mapped_column(
        Text, comment="失敗時的例外類型與訊息，給開發者看；空值代表沒有未預期的例外"
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="完成時的結果；空值代表還沒完成或失敗"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auth_users.id"), comment="建立工作的使用者"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="建立工作的時間"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="開始處理的時間；空值代表還在等待"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="完成或失敗的時間；空值代表還沒結束"
    )


class RulesQaVideoTerms(Base):
    """規則影片的用語對照表（add-rules-video-mobile design.md D4）。每款遊戲一份，所有店家共用。"""

    __tablename__ = "rules_qa_video_terms"
    __table_args__ = (
        {"comment": "規則影片的用語對照表：每款遊戲一份，管理員上傳，AI 產生草稿時照表用詞"},
    )

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id"),
        primary_key=True,
        comment="哪一款遊戲的對照表；每款遊戲一份（桌遊被刪除時由資料庫擋下，ADR 0003）",
    )
    terms: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        comment=(
            "用語對照，格式同 terms.json（en、zh、key、avoid、category）；"
            "空陣列代表確認不使用對照表"
        ),
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auth_users.id"), comment="最後一次上傳的管理員"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="最後一次上傳的時間"
    )
