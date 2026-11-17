"""遊戲清單：給各功能（例如開團表單）用下拉選單選遊戲。只讀共用表 games。"""

from app.core.auth import CurrentUser
from app.core.games.repository import GameRepository
from app.core.games.schemas import GameListItem, GameListResponse


class GamesService:
    def __init__(self, games: GameRepository) -> None:
        self._games = games

    def list_games(
        self, user: CurrentUser, q: str | None, page: int, page_size: int
    ) -> GameListResponse:
        """所有已登入的角色都可以查詢。q 去掉前後空白後為空時，視為不搜尋。"""
        keyword = q.strip() if q else None
        rows, total = self._games.search_games(
            keyword or None, offset=(page - 1) * page_size, limit=page_size
        )
        return GameListResponse(
            items=[
                GameListItem(id=row.id, name=row.name, english_name=row.english_name)
                for row in rows
            ],
            total=total,
        )
