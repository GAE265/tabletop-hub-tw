"""所有 domain 共用的桌遊表（ADR 0003）。

這三張表是 AGENTS.md §4.2、§4.4 的例外：表名沒有 domain 開頭、所有 domain 都可以直接查詢、
games.id 是字串編號。只有 games_advisor 的匯入指令寫入；其他 domain 要改這三張表請 @ 立倫。
"""

import uuid

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Double,
    ForeignKey,
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
        CheckConstraint("id ~ '^[1-9][0-9]*$'", name="ck_games_id_format"),
        CheckConstraint("min_players BETWEEN 1 AND max_players", name="ck_games_players"),
        CheckConstraint("min_playtime BETWEEN 1 AND max_playtime", name="ck_games_playtime"),
        CheckConstraint("min_age >= 0", name="ck_games_min_age"),
        CheckConstraint("weight BETWEEN 1 AND 5", name="ck_games_weight"),
    )

    # 編號 "1"、"2"……由立倫指定；照編號排序要轉成數字，否則 "10" 會排在 "2" 前面
    id: Mapped[str] = mapped_column(Text, primary_key=True)
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


class GameType(Base):
    __tablename__ = "game_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_game_types_code"),
        UniqueConstraint("name", name="uq_game_types_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)


class GameGameType(Base):
    __tablename__ = "game_game_types"
    __table_args__ = (
        UniqueConstraint("game_id", "game_type_id", name="uq_game_game_types_game_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    game_id: Mapped[str] = mapped_column(Text, ForeignKey("games.id", ondelete="CASCADE"))
    game_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("game_types.id"))
