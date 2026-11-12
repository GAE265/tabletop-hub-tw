"""games_advisor 自己的表：心得摘要、標籤詞彙表、每款桌遊的標籤、心得片段。

game_id 參照共用表 games.id（app/core/games/models.py）。
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Double,
    ForeignKey,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


def _game_fk() -> Mapped[int]:
    return mapped_column(BigInteger, ForeignKey("games.id", ondelete="CASCADE"))


# 向量欄位不寫維度：實際維度由 migration 讀 GAMES_ADVISOR_EMBEDDING_DIM 建立，這裡不重複寫死


class ReviewSummary(Base):
    __tablename__ = "games_advisor_review_summaries"
    __table_args__ = (
        UniqueConstraint("game_id", name="uq_games_advisor_review_summaries_game_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    game_id: Mapped[int] = _game_fk()
    summary: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    embedding_model: Mapped[str] = mapped_column(Text)


class Tag(Base):
    __tablename__ = "games_advisor_tags"
    __table_args__ = (
        UniqueConstraint("code", name="uq_games_advisor_tags_code"),
        UniqueConstraint("name", name="uq_games_advisor_tags_name"),
        CheckConstraint("code ~ '^[a-z][a-z0-9_]*$'", name="ck_games_advisor_tags_code"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    definition: Mapped[str] = mapped_column(Text)


class GameTag(Base):
    __tablename__ = "games_advisor_game_tags"
    __table_args__ = (
        UniqueConstraint("game_id", "tag_id", name="uq_games_advisor_game_tags_game_tag"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_games_advisor_game_tags_confidence"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    game_id: Mapped[int] = _game_fk()
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("games_advisor_tags.id", ondelete="CASCADE")
    )
    # 低於門檻的也存，推薦時才套用門檻
    confidence: Mapped[float] = mapped_column(Double)


class ReviewExcerpt(Base):
    __tablename__ = "games_advisor_review_excerpts"
    __table_args__ = (
        CheckConstraint(
            "language IN ('zh-TW', 'en')", name="ck_games_advisor_review_excerpts_language"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    game_id: Mapped[int] = _game_fk()
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    embedding_model: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    site_name: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text)
