"""所有 domain 共用的桌遊表（ADR 0003）。

games、genres、game_genres 列在 AGENTS.md 第 3 節「共用資料表」，擁有者是立倫；
要改結構先和立倫確認。
games.id 用自動給號的整數是 §4.4 的例外（主鍵預設 UUID）。只有 games_advisor 的匯入桌遊（立倫）
與同步（其他組員）指令寫入。
"""

import uuid
from enum import StrEnum

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


class ResultType(StrEnum):
    """這款遊戲的結果怎麼記（依規則書，每款遊戲只有一種）。只決定結果的記法，和要不要記回合無關。

    資料庫存成文字欄位並用 CHECK 限制（不用 PostgreSQL 原生 enum）；空值代表尚未設定。
    """

    # 陣營勝負：記哪一方獲勝。例：血與刃的白薔薇、阿瓦隆、總統與炸彈客
    FACTION = "faction"
    # 個人分數：記每位玩家的分數與名次。例：馬可波羅、阿布斯學院
    SCORE = "score"
    # 合作：記全隊是否通過，以及玩到哪個進度（例如第五關）。例：瘋狂鬼宅
    COOPERATIVE = "cooperative"


def _result_type_check() -> str:
    values = ", ".join(f"'{result_type.value}'" for result_type in ResultType)
    return f"result_type IN ({values})"


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("bgg_id", name="uq_games_bgg_id"),
        CheckConstraint("id > 0", name="ck_games_id_positive"),
        CheckConstraint("min_players BETWEEN 1 AND max_players", name="ck_games_players"),
        CheckConstraint("min_playtime BETWEEN 1 AND max_playtime", name="ck_games_playtime"),
        CheckConstraint("min_age >= 0", name="ck_games_min_age"),
        CheckConstraint("weight BETWEEN 1 AND 5", name="ck_games_weight"),
        CheckConstraint(_result_type_check(), name="ck_games_result_type"),
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
    result_type: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "這款遊戲的結果怎麼記：faction（陣營勝負，記哪一方獲勝，例如阿瓦隆）、"
            "score（個人分數，記每人分數與名次，例如馬可波羅）、"
            "cooperative（合作，記全隊是否通過與玩到哪個進度，例如瘋狂鬼宅）；"
            "空值代表這款遊戲尚未設定結果類型"
        ),
    )


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
