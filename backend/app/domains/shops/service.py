"""新增店家與管理店家庫存的商業規則。

權限以資料庫（auth_users.shop_id）為準，不看 CurrentUser.shop_id：身分只來自請求標頭或 token，
店員新增店家後它不會更新。
"""

import uuid
from typing import Any, Protocol

from app.core.auth import CurrentUser, require_role
from app.core.errors import AppError, PermissionDenied
from app.domains.booking.records import ShopRef
from app.domains.shops.repository import ShopGameAlreadyExists, ShopGameItem
from app.domains.shops.schemas import ShopCreatedOut


class ShopGamesRepositoryProtocol(Protocol):
    def transaction(self) -> Any: ...
    def list_games(self, shop_id: uuid.UUID) -> list[ShopGameItem]: ...
    def add(self, shop_id: uuid.UUID, game_id: int) -> ShopGameItem: ...
    def remove(self, shop_id: uuid.UUID, game_id: int) -> bool: ...


class ShopDirectory(Protocol):
    """booking_shops 的共用表 repository（BookingRepository）。"""

    def create_shop(self, *, name: str, phone: str | None, address: str | None) -> ShopRef: ...
    def get_shop(self, shop_id: uuid.UUID) -> ShopRef | None: ...


class UserDirectory(Protocol):
    """auth_users 的共用表 repository（AuthUserRepository）。"""

    def get_shop_id(self, user_id: uuid.UUID) -> uuid.UUID | None: ...
    def set_shop_id(self, user_id: uuid.UUID, shop_id: uuid.UUID) -> bool: ...


class GameDirectory(Protocol):
    """games 的共用表 repository（GameRepository）。"""

    def game_exists(self, game_id: int) -> bool: ...


def _already_has_shop() -> AppError:
    return AppError(409, "SHOP_STAFF_ALREADY_HAS_SHOP", "這個店家帳號已經有所屬店家，不能再新增")


class ShopsService:
    def __init__(
        self,
        *,
        shop_games: ShopGamesRepositoryProtocol,
        shops: ShopDirectory,
        users: UserDirectory,
        games: GameDirectory,
    ) -> None:
        self._shop_games = shop_games
        self._shops = shops
        self._users = users
        self._games = games

    # --- 新增店家 ---

    def create_shop(
        self,
        user: CurrentUser,
        *,
        name: str,
        phone: str | None = None,
        address: str | None = None,
    ) -> ShopCreatedOut:
        """店員新增店家並綁定自己的帳號；管理員新增但不綁定。玩家沒有權限。"""
        require_role(user, "shop_staff", "admin")
        is_staff = user.role == "shop_staff"
        if is_staff and self._users.get_shop_id(user.id) is not None:
            raise _already_has_shop()
        with self._shop_games.transaction():
            shop = self._shops.create_shop(name=name, phone=phone, address=address)
            # 帳號同時被別的請求綁走時綁定失敗，整個交易退回，不留下沒人管的店
            if is_staff and not self._users.set_shop_id(user.id, shop.id):
                raise _already_has_shop()
        return ShopCreatedOut(id=shop.id, name=shop.name, phone=phone, address=address)

    # --- 庫存 ---

    def list_games(self, user: CurrentUser, shop_id: uuid.UUID) -> list[ShopGameItem]:
        self._require_access(user, shop_id)
        return self._shop_games.list_games(shop_id)

    def add_game(self, user: CurrentUser, shop_id: uuid.UUID, game_id: int) -> ShopGameItem:
        self._require_access(user, shop_id)
        if not self._games.game_exists(game_id):
            raise AppError(404, "GAME_NOT_FOUND", "找不到這款桌遊", {"game_id": game_id})
        try:
            with self._shop_games.transaction():
                return self._shop_games.add(shop_id, game_id)
        except ShopGameAlreadyExists:
            raise AppError(
                409, "SHOP_GAME_ALREADY_EXISTS", "這間店已經有這款桌遊", {"game_id": game_id}
            ) from None

    def remove_game(self, user: CurrentUser, shop_id: uuid.UUID, game_id: int) -> None:
        self._require_access(user, shop_id)
        with self._shop_games.transaction():
            removed = self._shop_games.remove(shop_id, game_id)
        if not removed:
            raise AppError(
                404, "SHOP_GAME_NOT_FOUND", "這間店的庫存沒有這款桌遊", {"game_id": game_id}
            )

    def _require_access(self, user: CurrentUser, shop_id: uuid.UUID) -> None:
        """先看角色，再看店家存在，最後看店員是不是這間店的人（管理員不限）。"""
        require_role(user, "shop_staff", "admin")
        if self._shops.get_shop(shop_id) is None:
            raise AppError(404, "SHOP_NOT_FOUND", "找不到這間店家", {"shop_id": str(shop_id)})
        if user.role == "shop_staff" and self._users.get_shop_id(user.id) != shop_id:
            raise PermissionDenied(details={"shop_id": str(shop_id)})
