from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import get_session
from app.domains.rules_ingest.router import get_vision
from app.domains.rules_ingest.service import MAX_IMAGE_BYTES
from app.integrations.ocr.errors import (
    OCRError,
    OCRNotConfigured,
    OCROutputRejected,
    OCRUnavailable,
)
from app.integrations.ocr.fake import FakeVisionProvider
from app.main import create_app
from tests.db_utils import recreate_database, run_migrations
from tests.migrations.test_games_manual import INSERT_GAME
from tests.rules_ingest.test_manual_pages_service import PNG

URL = "/api/v1/games/1/manual-pages"


@pytest.fixture(scope="module")
def api_engine() -> Iterator[Engine]:
    url = recreate_database(Settings().database_url, "manual_import_api")
    run_migrations(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def vision(app, api_engine):
    with api_engine.begin() as connection:
        connection.execute(text("TRUNCATE games CASCADE"))
        connection.execute(INSERT_GAME, {"id": 1})

    def session():
        with Session(api_engine) as value:
            yield value

    provider = FakeVisionProvider([{"markdown": "# 標題"}, {"markdown": ""}])
    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_vision] = lambda: provider
    return provider


def stored(engine):
    with engine.connect() as connection:
        return dict(
            connection.execute(text("SELECT page, content FROM games_manual ORDER BY page")).all()
        )


@pytest.mark.usefixtures("as_admin")
def test_upload_overwrite_and_readback(client, vision, api_engine):
    for content in ["# 標題", ""]:
        response = client.put(URL + "/1", files={"file": ("page.png", PNG, "image/png")})
        assert response.status_code == 200
        assert response.json() == {"games_id": 1, "page": 1, "content": content}
        assert stored(api_engine) == {1: content}
    assert client.get(URL).json() == {
        "items": [{"page": 1, "content": ""}],
        "total": 1,
        "ocr_provider": "fake",
    }
    assert len(vision.calls) == 2


@pytest.mark.usefixtures("as_shop_staff")
def test_staff_can_import(client, vision):
    assert client.put(URL + "/1", files={"file": ("p.png", PNG)}).status_code == 200


@pytest.mark.usefixtures("as_player")
@pytest.mark.parametrize("method", ["put", "get"])
def test_player_denied(client, vision, api_engine, method):
    response = (
        client.get(URL)
        if method == "get"
        else client.put(URL + "/1", files={"file": ("p.png", PNG)})
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    assert vision.calls == []
    assert stored(api_engine) == {}


@pytest.mark.usefixtures("as_admin")
@pytest.mark.parametrize(
    ("page", "image", "status", "code"),
    [
        (0, PNG, 422, "VALIDATION_ERROR"),
        (1, None, 422, "VALIDATION_ERROR"),
        (1, b"", 400, "INVALID_IMAGE"),
        (1, b"plain text", 400, "INVALID_IMAGE"),
        (1, PNG + b"x" * MAX_IMAGE_BYTES, 400, "IMAGE_TOO_LARGE"),
    ],
)
def test_upload_validation(client, vision, api_engine, page, image, status, code):
    files = None if image is None else {"file": ("p.png", image)}
    response = client.put(URL + f"/{page}", files=files)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert vision.calls == []
    assert stored(api_engine) == {}


@pytest.mark.usefixtures("as_admin")
@pytest.mark.parametrize("method", ["get", "put"])
def test_game_not_found(client, vision, api_engine, method):
    url = "/api/v1/games/999/manual-pages"
    response = (
        client.get(url)
        if method == "get"
        else client.put(url + "/1", files={"file": ("p.png", PNG)})
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GAME_NOT_FOUND"
    assert vision.calls == []
    assert stored(api_engine) == {}


@pytest.mark.usefixtures("as_admin")
@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (OCRUnavailable("timeout"), "OCR_UNAVAILABLE"),
        (OCROutputRejected("refused"), "OCR_OUTPUT_REJECTED"),
        (OCRError("secret-key"), "OCR_FAILED"),
        (None, "OCR_UNAVAILABLE"),
    ],
)
def test_ocr_error_keeps_existing_page(app, client, vision, api_engine, failure, code):
    with api_engine.begin() as connection:
        connection.execute(text("INSERT INTO games_manual VALUES (1, 1, 'old')"))
    provider = FakeVisionProvider(None if failure is None else [failure])
    app.dependency_overrides[get_vision] = lambda: provider
    response = client.put(URL + "/1", files={"file": ("p.png", PNG)})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == code
    assert "secret-key" not in response.text
    assert stored(api_engine) == {1: "old"}


@pytest.mark.usefixtures("as_admin")
def test_list_sorted_and_empty(client, vision, api_engine):
    assert client.get(URL).json() == {"items": [], "total": 0, "ocr_provider": "fake"}
    with api_engine.begin() as connection:
        connection.execute(text("INSERT INTO games_manual VALUES (1, 3, 'three'), (1, 1, 'one')"))
    response = client.get(URL)
    assert response.status_code == 200
    assert response.json() == {
        "items": [{"page": 1, "content": "one"}, {"page": 3, "content": "three"}],
        "total": 2,
        "ocr_provider": "fake",
    }
    assert vision.calls == []


def test_cloud_missing_settings_fails_at_startup(make_settings):
    with pytest.raises(OCRNotConfigured) as error:
        create_app(make_settings(ocr_provider="cloud"))
    assert "LLM_API_KEY" in error.value.missing


def test_openapi_documents_multipart_and_schemas(client):
    response = client.get("/docs")
    assert response.status_code == 200
    schema = client.get("/openapi.json").json()
    put = schema["paths"]["/api/v1/games/{games_id}/manual-pages/{page}"]["put"]
    assert "multipart/form-data" in put["requestBody"]["content"]
    assert next(p for p in put["parameters"] if p["name"] == "page")["schema"]["minimum"] == 1
    assert "ManualPageOut" in schema["components"]["schemas"]
    assert "ManualPageListOut" in schema["components"]["schemas"]
