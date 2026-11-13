"""共用桌遊表的資料存取（AGENTS.md §4.2：一張共用表只有一個 repository，由擁有者建立）。

GameRepository 讀寫 games、genres、game_genres 與 games.id 的計數器。各 domain 的 service 可以
直接使用；只有 games_advisor 的匯入桌遊與同步共用桌遊資料兩個指令會寫入（ADR 0003）。
"""

from collections.abc import Collection, Mapping
from typing import Any

from psycopg.errors import ForeignKeyViolation
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionRepository
from app.core.games.models import Game, GameGenre, Genre


class GameInUseError(Exception):
    """要刪的桌遊還被其他資料表參照，資料庫擋下刪除。"""

    def __init__(self, game_id: int, name: str, table: str) -> None:
        super().__init__(f"{game_id} 號「{name}」還被資料表 {table} 參照")
        self.game_id = game_id
        self.name = name
        self.table = table


class GameRepository(SessionRepository):
    """共用桌遊表 games、genres、game_genres 與 games.id 計數器的讀寫。"""

    def count_games(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Game)) or 0

    def list_games(self) -> list[dict[str, Any]]:
        """全部桌遊，照 id 排。每款是 id、11 個欄位，加上 types（類型代碼，照字母排）。"""
        types: dict[int, list[str]] = {}
        genre_rows = self.session.execute(
            select(GameGenre.game_id, Genre.code)
            .join(Genre, Genre.id == GameGenre.genre_id)
            .order_by(Genre.code)
        )
        for game_id, code in genre_rows:
            types.setdefault(game_id, []).append(code)

        # 讀成一般的列，不讀成 ORM 物件：同一個 session 之後用 SQL 改過資料，也不會讀到舊值
        games = self.session.execute(select(Game.__table__).order_by(Game.id)).mappings()
        return [{**game, "types": types.get(game["id"], [])} for game in games]

    def find_games_by_bgg_ids(self, bgg_ids: Collection[int]) -> list[dict[str, Any]]:
        """用 bgg_id 查桌遊，照 id 排。資料庫沒有的 bgg_id 不會出現在結果裡。

        每款是 id 與 11 個欄位，不含 types。
        """
        if not bgg_ids:
            return []
        games = self.session.execute(
            select(Game.__table__).where(Game.bgg_id.in_(list(bgg_ids))).order_by(Game.id)
        ).mappings()
        return [dict(game) for game in games]

    def list_genre_codes(self) -> set[str]:
        return set(self.session.scalars(select(Genre.code)))

    def add_game(self, values: Mapping[str, Any]) -> int:
        """寫入一款桌遊，id 由資料庫自動給號；回傳拿到的 id。"""
        return self.session.execute(insert(Game).values(**values).returning(Game.id)).scalar_one()

    def save_game(self, game_id: int, values: Mapping[str, Any]) -> None:
        """照給的 id 寫入一款桌遊；這個 id 已經存在就只更新欄位，參照它的資料不受影響。

        照給的 id 寫入不會推動計數器，寫完要另外呼叫 set_next_game_id。
        """
        statement = pg_insert(Game).values(id=game_id, **values)
        self.session.execute(
            statement.on_conflict_do_update(index_elements=[Game.id], set_=dict(values))
        )

    def delete_games_except(self, keep_ids: Collection[int]) -> int:
        """刪掉 id 不在 keep_ids 裡的桌遊，回傳刪除的款數。

        類型、心得摘要、標籤、心得片段會跟著刪。還被其他資料表參照的桌遊刪不掉，
        拋 GameInUseError；這時交易已經失敗，呼叫端要整個退回。
        """
        statement = select(Game.id, Game.name).order_by(Game.id)
        if keep_ids:
            statement = statement.where(Game.id.not_in(keep_ids))
        doomed = self.session.execute(statement).all()
        # 一款一款刪，被擋下時才知道是哪一款
        for game_id, name in doomed:
            try:
                self.session.execute(delete(Game).where(Game.id == game_id))
            except IntegrityError as exc:
                if isinstance(exc.orig, ForeignKeyViolation):
                    table = exc.orig.diag.table_name or "（不明）"
                    raise GameInUseError(game_id, name, table) from exc
                raise
        return len(doomed)

    def replace_game_genres(self, game_id: int, codes: Collection[str]) -> None:
        """把一款桌遊的類型整組換成 codes。"""
        self.session.execute(delete(GameGenre).where(GameGenre.game_id == game_id))
        if not codes:
            return
        genre_ids = dict(
            self.session.execute(select(Genre.code, Genre.id).where(Genre.code.in_(codes))).all()
        )
        if unknown := sorted(set(codes) - set(genre_ids)):
            raise ValueError(f"不認得的類型代碼：{'、'.join(unknown)}")
        self.session.execute(
            insert(GameGenre),
            [{"game_id": game_id, "genre_id": genre_ids[code]} for code in set(codes)],
        )

    def next_game_id(self) -> int:
        """games.id 計數器的下一個號碼。只讀，不會用掉號碼。"""
        sequence = self.session.scalar(select(func.pg_get_serial_sequence("games", "id")))
        # 計數器還沒給過號時，last_value 本身就是下一個號碼
        next_or_last = "CASE WHEN is_called THEN last_value + 1 ELSE last_value END"
        return self.session.scalar(text(f"SELECT {next_or_last} FROM {sequence}"))

    def set_next_game_id(self, next_id: int) -> None:
        """把計數器設成 next_id：下一款沒給 id 的桌遊會拿到這個號碼。

        用 ALTER TABLE 而不是 setval()：setval() 不會跟著交易退回。
        """
        self.session.execute(text(f"ALTER TABLE games ALTER COLUMN id RESTART WITH {int(next_id)}"))
