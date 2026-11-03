from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

ALLOWED = "http://localhost:5000"
OTHER = "http://evil.example.com"


@pytest.fixture
def make_client(make_settings: Callable[..., Settings]) -> Callable[..., TestClient]:
    def _make(**overrides: object) -> TestClient:
        return TestClient(create_app(make_settings(**overrides)))

    return _make


def preflight(client: TestClient, origin: str, headers: str = "x-dev-user"):
    return client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": headers,
        },
    )


def test_default_origin_is_the_local_flutter_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)  # 不受執行環境影響
    settings = Settings(_env_file=None, database_url="postgresql+psycopg://u:p@h/d")
    assert settings.cors_origins == [ALLOWED]


def test_allowed_origin_gets_cors_header(make_client: Callable[..., TestClient]) -> None:
    client = make_client(cors_allow_origins=ALLOWED)
    response = client.get("/api/v1/health", headers={"Origin": ALLOWED})
    assert response.headers["access-control-allow-origin"] == ALLOWED


def test_other_origin_gets_no_cors_header(make_client: Callable[..., TestClient]) -> None:
    client = make_client(cors_allow_origins=ALLOWED)
    response = client.get("/api/v1/health", headers={"Origin": OTHER})
    assert "access-control-allow-origin" not in response.headers


def test_request_without_origin_gets_no_cors_header(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(cors_allow_origins=ALLOWED)
    assert "access-control-allow-origin" not in client.get("/api/v1/health").headers


def test_preflight_allows_x_dev_user(make_client: Callable[..., TestClient]) -> None:
    response = preflight(make_client(cors_allow_origins=ALLOWED), ALLOWED, "x-dev-user")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert "x-dev-user" in response.headers["access-control-allow-headers"].lower()


def test_preflight_allows_authorization_and_content_type(
    make_client: Callable[..., TestClient],
) -> None:
    response = preflight(
        make_client(cors_allow_origins=ALLOWED), ALLOWED, "authorization, content-type"
    )
    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed
    assert "content-type" in allowed


def test_preflight_from_other_origin_is_rejected(
    make_client: Callable[..., TestClient],
) -> None:
    response = preflight(make_client(cors_allow_origins=ALLOWED), OTHER)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_preflight_with_unlisted_header_is_rejected(
    make_client: Callable[..., TestClient],
) -> None:
    response = preflight(make_client(cors_allow_origins=ALLOWED), ALLOWED, "x-unknown")
    assert response.status_code == 400


def test_multiple_origins_are_comma_separated(make_client: Callable[..., TestClient]) -> None:
    client = make_client(cors_allow_origins="http://a.test, http://b.test:8080")
    for origin in ("http://a.test", "http://b.test:8080"):
        response = client.get("/api/v1/health", headers={"Origin": origin})
        assert response.headers["access-control-allow-origin"] == origin


def test_empty_setting_disables_cors(make_client: Callable[..., TestClient]) -> None:
    client = make_client(cors_allow_origins="")
    response = client.get("/api/v1/health", headers={"Origin": ALLOWED})
    assert "access-control-allow-origin" not in response.headers
