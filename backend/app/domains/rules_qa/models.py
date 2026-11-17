"""規則教學與問答的資料表（openspec change add-rules-qa，design.md D2）。

game_id 參照共用表 games.id；依 ADR 0003 不設定 cascade，桌遊被刪除時由資料庫擋下。
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
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
