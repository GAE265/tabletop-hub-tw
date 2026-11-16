"""rules_ingest 的資料存取：規則書頁面（games_manual）。"""

from psycopg.errors import ForeignKeyViolation
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionRepository
from app.domains.rules_ingest.models import GameManualPage


class GameNotFoundError(Exception):
    """要寫入的桌遊不存在（games.id 找不到）。"""

    def __init__(self, games_id: int) -> None:
        super().__init__(f"找不到桌遊 {games_id}")
        self.games_id = games_id


class ManualPageRepository(SessionRepository):
    def upsert_page(self, games_id: int, page: int, content: str) -> None:
        """寫入一頁；該頁已存在就用新的 content 取代（同頁重送是冪等的）。

        桌遊不存在時拋出 GameNotFoundError。呼叫端用 transaction() 決定何時提交。
        """
        stmt = pg_insert(GameManualPage).values(games_id=games_id, page=page, content=content)
        stmt = stmt.on_conflict_do_update(
            index_elements=[GameManualPage.games_id, GameManualPage.page],
            set_={"content": stmt.excluded.content},
        )
        try:
            self.session.execute(stmt)
            self.session.flush()
        except IntegrityError as error:
            if isinstance(error.orig, ForeignKeyViolation):
                self.session.rollback()
                raise GameNotFoundError(games_id) from error
            raise
