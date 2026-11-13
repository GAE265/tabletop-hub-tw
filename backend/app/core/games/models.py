"""所有 domain 共用的桌遊表（ADR 0003）。

games、genres、game_genres 列在 AGENTS.md 第 3 節「共用資料表」，擁有者是立倫；
要改結構先和立倫確認。
games.id 用自動給號的整數是 §4.4 的例外（主鍵預設 UUID）。只有 games_advisor 的匯入桌遊（立倫）
與同步（其他組員）指令寫入。
"""

import uuid

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Double,
    ForeignKey,
    Identity,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("bgg_id", name="uq_games_bgg_id"),
        CheckConstraint("id > 0", name="ck_games_id_positive"),
        CheckConstraint("min_players BETWEEN 1 AND max_players", name="ck_games_players"),
        CheckConstraint("min_playtime BETWEEN 1 AND max_playtime", name="ck_games_playtime"),
        CheckConstraint("min_age >= 0", name="ck_games_min_age"),
        CheckConstraint("weight BETWEEN 1 AND 5", name="ck_games_weight"),
    )

    # 沒給 id 就自動給號；給了就照給的寫入（同步共用桌遊資料時要用）
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    bgg_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(Text)
    english_name: Mapped[str] = mapped_column(Text)
    min_players: Mapped[int] = mapped_column(Integer)
    max_players: Mapped[int] = mapped_column(Integer)
    min_playtime: Mapped[int] = mapped_column(Integer)
    max_playtime: Mapped[int] = mapped_column(Integer)
    min_age: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Double)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text))
    mechanics: Mapped[list[str]] = mapped_column(ARRAY(Text))


class Genre(Base):
    __tablename__ = "genres"
    __table_args__ = (
        UniqueConstraint("code", name="uq_genres_code"),
        UniqueConstraint("name", name="uq_genres_name"),
    )

    # 固定的小型分類表，主鍵用流水號（AGENTS.md §4.4）；找類型一律用 code，不寫死 id
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)


class GameGenre(Base):
    __tablename__ = "game_genres"
    __table_args__ = (UniqueConstraint("game_id", "genre_id", name="uq_game_genres_game_genre"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("games.id", ondelete="CASCADE"))
    genre_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("genres.id"))
