from collections.abc import Callable
from subprocess import CompletedProcess

from sqlalchemy import Engine, text

from app.core.config import Settings


def counts(engine: Engine) -> tuple[int, int]:
    with engine.connect() as conn:
        users = conn.scalar(text("SELECT count(*) FROM auth_users"))
        shops = conn.scalar(text("SELECT count(*) FROM booking_shops"))
    return users, shops


def test_first_run_creates_three_accounts_and_one_shop(
    db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    result = run_seed()
    assert result.returncode == 0, result.stderr
    assert counts(db) == (3, 1)
    with db.connect() as conn:
        rows = conn.execute(text("SELECT role, shop_id FROM auth_users")).all()
        shop_id = conn.scalar(text("SELECT id FROM booking_shops"))
    assert sorted(role for role, _ in rows) == ["admin", "player", "shop_staff"]
    assert {role: sid for role, sid in rows}["shop_staff"] == shop_id


def test_second_run_creates_nothing_new(
    db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    assert run_seed().returncode == 0
    assert run_seed().returncode == 0
    assert counts(db) == (3, 1)


def test_jwt_mode_refuses_and_writes_nothing(
    db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    result = run_seed("jwt")
    assert result.returncode != 0
    assert "AUTH_MODE" in result.stderr
    assert counts(db) == (0, 0)


def test_seeded_player_is_the_default_player(
    db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    assert run_seed().returncode == 0
    with db.connect() as conn:
        player_id = conn.scalar(text("SELECT id::text FROM auth_users WHERE role = 'player'"))
    assert player_id == str(Settings(_env_file=None, database_url="x").dev_default_user_id)
