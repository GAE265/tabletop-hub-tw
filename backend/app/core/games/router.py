from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.games.repository import GameRepository
from app.core.games.schemas import GameSearchOut, GameSummary

router = APIRouter(prefix="/games", tags=["games"])


@router.get("", response_model=GameSearchOut)
def search_games(
    name: Annotated[str | None, Query(min_length=1)] = None,
    session: Session = Depends(get_session),
) -> GameSearchOut:
    repo = GameRepository(session)
    if name is not None:
        rows = repo.search_games_by_name(name)
        items = [GameSummary(id=row["id"], name=row["name"], english_name=row["english_name"]) for row in rows]
    else:
        rows = repo.list_games()
        items = [GameSummary(id=row["id"], name=row["name"], english_name=row["english_name"]) for row in rows]
    return GameSearchOut(items=items, total=len(items))
