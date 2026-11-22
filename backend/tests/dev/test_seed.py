from collections.abc import Callable
from subprocess import CompletedProcess

from sqlalchemy import Engine, text

from app.core.config import Settings


def counts(engine: Engine) -> tuple[int, int]:
    with engine.connect() as conn:
        users = conn.scalar(text("SELECT count(*) FROM auth_users"))
        shops = conn.scalar(text("SELECT count(*) FROM booking_shops"))
    return users, shops


def test_first_run_creates_four_accounts_and_one_shop(
    db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    """兩個店員：一個屬於測試店家，一個還沒有店（示範新增店家用，add-shops-management）。"""
    result = run_seed()
    assert result.returncode == 0, result.stderr
    assert counts(db) == (4, 1)
    with db.connect() as conn:
        roles = conn.scalars(text("SELECT role FROM auth_users")).all()
        staff_shops = conn.scalars(
            text("SELECT shop_id FROM auth_users WHERE role = 'shop_staff'")
        ).all()
        shop_id = conn.scalar(text("SELECT id FROM booking_shops"))
    assert sorted(roles) == ["admin", "player", "shop_staff", "shop_staff"]
    assert sorted(staff_shops, key=lambda s: s is None) == [shop_id, None]


def test_second_run_creates_nothing_new(
    db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    assert run_seed().returncode == 0
    assert run_seed().returncode == 0
    assert counts(db) == (4, 1)


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


def phones(engine: Engine) -> dict[str, str | None]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT role, phone FROM auth_users")).all()
    return {role: phone for role, phone in rows}


def test_accounts_have_distinct_fake_phones(
    db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    """訂位要求使用者有電話（BOOKING_PHONE_REQUIRED），測試帳號都要有，且彼此不同。"""
    assert run_seed().returncode == 0
    # 有兩個店員，不能用 phones()（以角色為 key）取值
    with db.connect() as conn:
        values = conn.scalars(text("SELECT phone FROM auth_users")).all()
    assert all(values), values
    assert len(set(values)) == 4


def test_rerun_fills_missing_phone_but_keeps_existing_one(
    db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    """已經建立過帳號的資料庫，重跑 seed 會補上空的電話，但不覆蓋已經填好的電話。"""
    assert run_seed().returncode == 0
    with db.begin() as conn:
        conn.execute(text("UPDATE auth_users SET phone = NULL WHERE role = 'player'"))
        conn.execute(text("UPDATE auth_users SET phone = '0911222333' WHERE role = 'admin'"))
    assert run_seed().returncode == 0
    result = phones(db)
    assert result["player"]
    assert result["admin"] == "0911222333"


def test_rerun_keeps_shop_created_by_staff_without_shop(
    db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    """還沒有店的店員新增店家之後，重跑 seed 不會把他和那間店的綁定拿掉。"""
    assert run_seed().returncode == 0
    with db.begin() as conn:
        new_shop = conn.scalar(
            text("INSERT INTO booking_shops (name) VALUES ('自己開的店') RETURNING id")
        )
        conn.execute(
            text(
                "UPDATE auth_users SET shop_id = :s WHERE role = 'shop_staff' AND shop_id IS NULL"
            ),
            {"s": new_shop},
        )
    assert run_seed().returncode == 0
    with db.connect() as conn:
        staff_shops = conn.scalars(
            text("SELECT shop_id FROM auth_users WHERE role = 'shop_staff'")
        ).all()
    assert new_shop in staff_shops
    assert None not in staff_shops
