"""shop_games 的 repository：查一組桌遊裡哪些在這間店的庫存（連 `_test` 資料庫）。"""

from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.conftest import TEST_SHOP_ID
from tests.shops.conftest import OTHER_SHOP_ID


@pytest.fixture
def repo(app: FastAPI, db: Engine) -> Iterator:
    """app fixture 已經在資料庫放好兩間店。"""
    from app.domains.shops.repository import ShopGamesRepository

    with Session(db) as session:
        yield ShopGamesRepository(session)


def test_games_in_stock(repo, add_game: Callable[[str], int], stock: Callable) -> None:
    catan, werewolf, avalon = add_game("卡坦島"), add_game("狼人殺"), add_game("阿瓦隆")
    stock(TEST_SHOP_ID, catan)
    stock(TEST_SHOP_ID, avalon)
    stock(OTHER_SHOP_ID, werewolf)

    assert repo.games_in_stock(TEST_SHOP_ID, [catan, werewolf]) == {catan}
    assert repo.games_in_stock(OTHER_SHOP_ID, [catan, werewolf, avalon]) == {werewolf}
    assert repo.games_in_stock(TEST_SHOP_ID, []) == set()
