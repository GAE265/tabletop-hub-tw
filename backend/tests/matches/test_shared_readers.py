"""共用表的讀取方法（只讀不寫）：games、booking_shops、auth_users（design.md D8）。

三個方法由 matches 代為新增，擁有者是立倫（games、auth_users）與瑋鋐（booking_shops）。
repository 在測試函式裡才 import：程式還沒寫的時候，每個測試各自失敗。
"""

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

SESSION_REPOSITORY_NAMES = {"session", "transaction"}


@pytest.fixture
def session(db: Engine):
    with db.begin() as conn:
        conn.execute(text("TRUNCATE games RESTART IDENTITY CASCADE"))
    with Session(db) as session:
        yield session


def insert_game(db: Engine, bgg_id: int, result_type: str | None) -> int:
    with db.begin() as conn:
        return conn.scalar(
            text(
                "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
                "min_playtime, max_playtime, min_age, weight, categories, mechanics, result_type) "
                "VALUES (:bgg, :name, 'Blades & Rose', 3, 5, 30, 60, 14, 2.0, "
                "ARRAY['Card Game'], ARRAY['Hidden Roles'], :rt) RETURNING id"
            ),
            {"bgg": bgg_id, "name": f"遊戲{bgg_id}", "rt": result_type},
        )


def public_methods(repository_class: type) -> set[str]:
    return {
        name
        for name in dir(repository_class)
        if not name.startswith("_") and name not in SESSION_REPOSITORY_NAMES
    }


# --- games ---


def test_get_game_returns_id_name_bgg_id_and_result_type(db: Engine, session: Session):
    from app.core.games.repository import GameRepository

    game_id = insert_game(db, 400566, "faction")
    game = GameRepository(session).get_game(game_id)
    assert game is not None
    assert (game.id, game.name, game.bgg_id, game.result_type) == (
        game_id,
        "遊戲400566",
        400566,
        "faction",
    )


def test_get_game_result_type_can_be_none(db: Engine, session: Session):
    from app.core.games.repository import GameRepository

    game_id = insert_game(db, 400566, None)
    game = GameRepository(session).get_game(game_id)
    assert game is not None
    assert game.result_type is None


def test_get_game_missing_returns_none(session: Session):
    from app.core.games.repository import GameRepository

    assert GameRepository(session).get_game(999999) is None


def test_get_game_does_not_write(db: Engine, session: Session):
    from app.core.games.repository import GameRepository

    game_id = insert_game(db, 400566, "faction")
    GameRepository(session).get_game(game_id)
    session.commit()
    with db.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM games")) == 1


# --- booking_shops ---


def test_get_shop_returns_id_and_name(db: Engine, session: Session):
    from app.domains.booking.repository import BookingRepository

    with db.begin() as conn:
        shop_id = conn.scalar(
            text("INSERT INTO booking_shops (name) VALUES ('測試店') RETURNING id")
        )
    shop = BookingRepository(session).get_shop(shop_id)
    assert shop is not None
    assert (shop.id, shop.name) == (shop_id, "測試店")


def test_get_shop_missing_returns_none(session: Session):
    from app.domains.booking.repository import BookingRepository

    assert BookingRepository(session).get_shop(uuid.uuid4()) is None


def test_get_shop_does_not_write(db: Engine, session: Session):
    from app.domains.booking.repository import BookingRepository

    with db.begin() as conn:
        shop_id = conn.scalar(
            text("INSERT INTO booking_shops (name) VALUES ('測試店') RETURNING id")
        )
    BookingRepository(session).get_shop(shop_id)
    session.commit()
    with db.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM booking_shops")) == 1


# --- auth_users ---


def test_get_user_returns_id_and_display_name(db: Engine, session: Session):
    from app.domains.auth.repository import AuthUserRepository

    with db.begin() as conn:
        user_id = conn.scalar(
            text(
                "INSERT INTO auth_users (display_name, role) VALUES ('小明', 'player') RETURNING id"
            )
        )
    user = AuthUserRepository(session).get_user(user_id)
    assert user is not None
    assert (user.id, user.display_name) == (user_id, "小明")


def test_get_user_missing_returns_none(session: Session):
    from app.domains.auth.repository import AuthUserRepository

    assert AuthUserRepository(session).get_user(uuid.uuid4()) is None


def test_auth_user_repository_only_has_the_agreed_methods():
    """matches 只用 get_user；shops 另外加了店員綁定店家用的 get_shop_id、set_shop_id。"""
    from app.domains.auth.repository import AuthUserRepository

    assert public_methods(AuthUserRepository) == {"get_user", "get_shop_id", "set_shop_id"}
