from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_ok_when_database_up(make_settings: Callable[..., Settings], test_db_url: str):
    client = TestClient(create_app(make_settings(database_url=test_db_url)))
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_health_degraded_when_database_down(make_settings: Callable[..., Settings]):
    client = TestClient(create_app(make_settings()))  # 預設指向連不上的資料庫
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "down"}


def test_health_needs_no_identity_even_in_jwt_mode(
    make_settings: Callable[..., Settings], test_db_url: str
):
    client = TestClient(create_app(make_settings(auth_mode="jwt", database_url=test_db_url)))
    assert client.get("/api/v1/health").status_code == 200


def test_health_post_is_405_with_error_format(client: TestClient):
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_health_listed_in_openapi(client: TestClient):
    assert "/api/v1/health" in client.get("/openapi.json").json()["paths"]
