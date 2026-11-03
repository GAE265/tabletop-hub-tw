import ast
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.config import Settings
from app.main import create_app
from tests.db_utils import BACKEND_DIR


@pytest.fixture
def dev_client(make_settings: Callable[..., Settings], test_db_url: str, db: Engine):
    return TestClient(create_app(make_settings(database_url=test_db_url)))


def test_lists_seeded_accounts(
    dev_client: TestClient, db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    assert run_seed().returncode == 0
    response = dev_client.get("/api/v1/dev/users")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert sorted(item["role"] for item in body["items"]) == ["admin", "player", "shop_staff"]
    staff = next(item for item in body["items"] if item["role"] == "shop_staff")
    assert staff["shop_id"] is not None


def test_response_matches_database(
    dev_client: TestClient, db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    assert run_seed().returncode == 0
    items = dev_client.get("/api/v1/dev/users").json()["items"]
    with db.connect() as conn:
        rows = conn.execute(
            text("SELECT id::text, display_name, role, shop_id::text FROM auth_users")
        ).all()
    expected = {row[0]: (row[1], row[2], row[3]) for row in rows}
    actual = {i["id"]: (i["display_name"], i["role"], i["shop_id"]) for i in items}
    assert actual == expected


def test_empty_before_seed(dev_client: TestClient) -> None:
    response = dev_client.get("/api/v1/dev/users")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_needs_no_identity_header(
    dev_client: TestClient, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    assert run_seed().returncode == 0
    assert dev_client.get("/api/v1/dev/users").status_code == 200


def test_only_lists_seeded_accounts(
    dev_client: TestClient, db: Engine, run_seed: Callable[..., CompletedProcess[str]]
) -> None:
    assert run_seed().returncode == 0
    with db.begin() as conn:
        conn.execute(text("INSERT INTO auth_users (display_name, role) VALUES ('路人', 'player')"))
    assert dev_client.get("/api/v1/dev/users").json()["total"] == 3


def test_route_absent_in_jwt_mode(make_settings: Callable[..., Settings]) -> None:
    client = TestClient(create_app(make_settings(auth_mode="jwt")))
    response = client.get("/api/v1/dev/users")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert "/api/v1/dev/users" not in client.get("/openapi.json").json()["paths"]


def test_dev_module_not_loaded_in_jwt_mode() -> None:
    code = (
        "import sys\n"
        "from app.core.config import Settings\n"
        "from app.main import create_app\n"
        "create_app(Settings(_env_file=None, database_url='postgresql+psycopg://u:p@h/d',"
        " auth_mode='jwt'))\n"
        "assert not any(m == 'app.dev' or m.startswith('app.dev.') for m in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_nothing_outside_app_dev_imports_app_dev() -> None:
    offenders: list[str] = []
    for path in BACKEND_DIR.rglob("*.py"):
        relative = path.relative_to(BACKEND_DIR)
        if ".venv" in relative.parts or relative.parts[:2] == ("app", "dev"):
            continue
        offenders += [f"{relative}:{n}" for n in imported_app_dev_lines(path)]
    assert offenders == []


def imported_app_dev_lines(path: Path) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            hit = any(a.name == "app.dev" or a.name.startswith("app.dev.") for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            hit = module == "app.dev" or module.startswith("app.dev.")
            hit = hit or (module == "app" and any(a.name == "dev" for a in node.names))
        else:
            continue
        if hit:
            lines.append(node.lineno)
    return lines
