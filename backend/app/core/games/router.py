"""遊戲清單 API：只解析請求、取得目前使用者、呼叫 service（AGENTS.md 4.2）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_session
from app.core.games.repository import GameRepository
from app.core.games.schemas import GameListResponse
from app.core.games.service import GamesService

router = APIRouter(prefix="/games", tags=["games"])


def get_games_service(session: Annotated[Session, Depends(get_session)]) -> GamesService:
    return GamesService(GameRepository(session))


@router.get("", response_model=GameListResponse)
def list_games(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GamesService, Depends(get_games_service)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> GameListResponse:
    """遊戲清單；q 依中文或英文名稱搜尋（部分相符、不分大小寫）。"""
    return service.list_games(user, q, page, page_size)
