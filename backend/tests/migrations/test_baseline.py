import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from tests.db_utils import BACKEND_DIR, recreate_database, run_migrations


@pytest.fixture(scope="module")
def migrated() -> Iterator[Engine]:
    url = recreate_database(Settings().database_url, "migration")
    run_migrations(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def clean(migrated: Engine) -> Engine:
    with migrated.begin() as conn:
        conn.execute(text("TRUNCATE auth_users, booking_shops CASCADE"))
    return migrated


def column_types(engine: Engine, table: str) -> dict[str, str]:
    sql = text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t"
    )
    with engine.connect() as conn:
        return {name: kind for name, kind in conn.execute(sql, {"t": table})}


def test_upgrade_enables_vector_and_creates_tables(migrated: Engine) -> None:
    with migrated.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")) == 1
    assert set(column_types(migrated, "auth_users")) == {
        "id",
        "display_name",
        "role",
        "shop_id",
        "created_at",
    }
    assert set(column_types(migrated, "booking_shops")) == {"id", "name"}


def test_primary_and_reference_keys_are_uuid(migrated: Engine) -> None:
    assert column_types(migrated, "auth_users")["id"] == "uuid"
    assert column_types(migrated, "auth_users")["shop_id"] == "uuid"
    assert column_types(migrated, "booking_shops")["id"] == "uuid"


def test_id_is_generated_when_omitted(clean: Engine) -> None:
    with clean.begin() as conn:
        new_id = conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('店') RETURNING id"))
    assert new_id is not None


def test_explicit_id_is_kept(clean: Engine) -> None:
    wanted = "99999999-9999-4999-8999-999999999999"
    with clean.begin() as conn:
        got = conn.scalar(
            text("INSERT INTO booking_shops (id, name) VALUES (:id, '店') RETURNING id::text"),
            {"id": wanted},
        )
    assert got == wanted


def test_role_organizer_is_rejected(clean: Engine) -> None:
    with pytest.raises(IntegrityError), clean.begin() as conn:
        conn.execute(text("INSERT INTO auth_users (display_name, role) VALUES ('x', 'organizer')"))


@pytest.mark.parametrize("role", ["player", "shop_staff", "admin"])
def test_valid_roles_are_accepted(clean: Engine, role: str) -> None:
    with clean.begin() as conn:
        conn.execute(
            text("INSERT INTO auth_users (display_name, role) VALUES ('x', :r)"), {"r": role}
        )


def test_shop_id_must_reference_existing_shop(clean: Engine) -> None:
    with pytest.raises(IntegrityError), clean.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO auth_users (display_name, role, shop_id) "
                "VALUES ('x', 'shop_staff', '11111111-2222-4333-8444-555555555555')"
            )
        )


def test_migration_seeds_no_data(migrated: Engine) -> None:
    fresh_url = recreate_database(Settings().database_url, "migration_empty")
    run_migrations(fresh_url)
    engine = create_engine(fresh_url)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM auth_users")) == 0
        assert conn.scalar(text("SELECT count(*) FROM booking_shops")) == 0
    engine.dispose()


def test_alembic_cli_runs_from_backend_dir() -> None:
    """README 的 `uv run alembic upgrade head` 要能直接跑（CLI 需找得到 app 套件）。"""
    url = recreate_database(Settings().database_url, "migration_cli")
    cli = Path(sys.executable).parent / ("alembic.exe" if os.name == "nt" else "alembic")
    result = subprocess.run(
        [str(cli), "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": url, "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_downgrade_removes_tables() -> None:
    url = recreate_database(Settings().database_url, "migration_down")
    run_migrations(url)
    run_migrations(url, "downgrade", "base")
    engine = create_engine(url)
    with engine.connect() as conn:
        tables = conn.scalars(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        ).all()
    engine.dispose()
    assert "auth_users" not in tables
    assert "booking_shops" not in tables
