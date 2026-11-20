"""店家庫存（shops_games）的資料存取。

店家本身（booking_shops）與帳號（auth_users）、桌遊（games）是共用資料表，
各自由擁有者的 repository 提供（AGENTS.md 4.2），這裡只管 shops_games。
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionRepository
from app.core.games.models import Game
from app.domains.shops.models import ShopGame


class ShopGameAlreadyExists(Exception):
    """同一間店已經有這款桌遊（資料庫的 unique 擋下）。"""


@dataclass(frozen=True)
class ShopGameItem:
    game_id: int
    name: str


class ShopGamesRepository(SessionRepository):
    def list_games(self, shop_id: uuid.UUID) -> list[ShopGameItem]:
        """這間店的庫存，依加入的先後排。"""
        rows = self.session.execute(
            select(ShopGame.game_id, Game.name)
            .join(Game, Game.id == ShopGame.game_id)
            .where(ShopGame.shop_id == shop_id)
            .order_by(ShopGame.created_at, ShopGame.id)
        )
        return [ShopGameItem(game_id, name) for game_id, name in rows]

    def add(self, shop_id: uuid.UUID, game_id: int) -> ShopGameItem:
        """加入一款桌遊；這間店已經有就拋出 ShopGameAlreadyExists。呼叫端要用 transaction()。"""
        try:
            self.session.execute(insert(ShopGame).values(shop_id=shop_id, game_id=game_id))
            self.session.flush()
        except IntegrityError as error:
            raise ShopGameAlreadyExists() from error
        name = self.session.scalar(select(Game.name).where(Game.id == game_id))
        return ShopGameItem(game_id, name or "")

    def remove(self, shop_id: uuid.UUID, game_id: int) -> bool:
        """移除一款桌遊；原本就不在庫存回 False。呼叫端要用 transaction()。"""
        result = self.session.execute(
            delete(ShopGame).where(ShopGame.shop_id == shop_id, ShopGame.game_id == game_id)
        )
        return result.rowcount > 0
