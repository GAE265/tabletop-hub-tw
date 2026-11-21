"""shops service 單元測試用的手寫 fake（AGENTS.md 7.5），照各 repository 的介面在記憶體中運作。

只在 fixture 裡 import 這個模組：程式還沒寫的時候，每個測試各自失敗，不會整個資料夾收集失敗。
"""

import uuid
from collections.abc import Collection
from contextlib import contextmanager

from app.domains.booking.records import ShopRef
from app.domains.shops.repository import ShopGameAlreadyExists, ShopGameItem


class FakeBookingShops:
    """booking_shops 的共用表 repository（BookingRepository 的 create_shop、get_shop）。"""

    def __init__(self) -> None:
        self.shops: dict[uuid.UUID, dict[str, str | None]] = {}

    def create_shop(self, *, name: str, phone: str | None, address: str | None) -> ShopRef:
        shop_id = uuid.uuid4()
        self.shops[shop_id] = {"name": name, "phone": phone, "address": address}
        return ShopRef(shop_id, name)

    def get_shop(self, shop_id: uuid.UUID) -> ShopRef | None:
        row = self.shops.get(shop_id)
        return None if row is None else ShopRef(shop_id, str(row["name"]))


class FakeAuthUsers:
    """auth_users 的共用表 repository（AuthUserRepository 的 get_shop_id、set_shop_id）。"""

    def __init__(self) -> None:
        self.shop_ids: dict[uuid.UUID, uuid.UUID | None] = {}

    def get_shop_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        return self.shop_ids.get(user_id)

    def set_shop_id(self, user_id: uuid.UUID, shop_id: uuid.UUID) -> bool:
        """只在帳號還沒有店時綁定；已經有店（或沒有這個帳號）回 False。"""
        if self.shop_ids.get(user_id, "missing") is not None:
            return False
        self.shop_ids[user_id] = shop_id
        return True


class FakeGames:
    """games 的共用表 repository（GameRepository 的 game_exists）。"""

    def __init__(self) -> None:
        self.names: dict[int, str] = {}

    def game_exists(self, game_id: int) -> bool:
        return game_id in self.names


class FakeShopGamesRepository:
    """shop_games 的 repository。"""

    def __init__(self, games: FakeGames) -> None:
        self.games = games
        # 依加入順序
        self.rows: list[tuple[uuid.UUID, int]] = []

    @contextmanager
    def transaction(self):
        yield

    def list_games(self, shop_id: uuid.UUID) -> list[ShopGameItem]:
        return [ShopGameItem(g, self.games.names[g]) for s, g in self.rows if s == shop_id]

    def games_in_stock(self, shop_id: uuid.UUID, game_ids: Collection[int]) -> set[int]:
        return {g for s, g in self.rows if s == shop_id and g in set(game_ids)}

    def add(self, shop_id: uuid.UUID, game_id: int) -> ShopGameItem:
        if (shop_id, game_id) in self.rows:
            raise ShopGameAlreadyExists()
        self.rows.append((shop_id, game_id))
        return ShopGameItem(game_id, self.games.names[game_id])

    def remove(self, shop_id: uuid.UUID, game_id: int) -> bool:
        if (shop_id, game_id) not in self.rows:
            return False
        self.rows.remove((shop_id, game_id))
        return True
