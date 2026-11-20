"""店家與庫存 API：只解析請求、取得目前使用者、呼叫 service（AGENTS.md 4.2）。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_session
from app.core.games.repository import GameRepository
from app.domains.auth.repository import AuthUserRepository
from app.domains.booking.repository import BookingRepository
from app.domains.shops.repository import ShopGamesRepository
from app.domains.shops.schemas import (
    ShopCreate,
    ShopCreatedOut,
    ShopGameAdd,
    ShopGameList,
    ShopGameOut,
)
from app.domains.shops.service import ShopsService

router = APIRouter(prefix="/shops", tags=["shops"])

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_shops_service(session: Annotated[Session, Depends(get_session)]) -> ShopsService:
    return ShopsService(
        shop_games=ShopGamesRepository(session),
        shops=BookingRepository(session),
        users=AuthUserRepository(session),
        games=GameRepository(session),
    )


ServiceDep = Annotated[ShopsService, Depends(get_shops_service)]


@router.post("", response_model=ShopCreatedOut, status_code=status.HTTP_201_CREATED)
def create_shop(body: ShopCreate, user: CurrentUserDep, service: ServiceDep):
    return service.create_shop(user, name=body.name, phone=body.phone, address=body.address)


@router.get("/{shop_id}/games", response_model=ShopGameList)
def list_shop_games(shop_id: uuid.UUID, user: CurrentUserDep, service: ServiceDep):
    items = [ShopGameOut(game_id=i.game_id, name=i.name) for i in service.list_games(user, shop_id)]
    return ShopGameList(items=items, total=len(items))


@router.post("/{shop_id}/games", response_model=ShopGameOut, status_code=status.HTTP_201_CREATED)
def add_shop_game(shop_id: uuid.UUID, body: ShopGameAdd, user: CurrentUserDep, service: ServiceDep):
    item = service.add_game(user, shop_id, body.game_id)
    return ShopGameOut(game_id=item.game_id, name=item.name)


@router.delete("/{shop_id}/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_shop_game(shop_id: uuid.UUID, game_id: int, user: CurrentUserDep, service: ServiceDep):
    service.remove_game(user, shop_id, game_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
