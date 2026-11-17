from contextlib import contextmanager

import pytest

from app.core.errors import AppError
from app.domains.rules_ingest.repository import GameNotFoundError
from app.domains.rules_ingest.service import (
    MAX_IMAGE_BYTES,
    TRANSCRIPTION_SCHEMA,
    ManualPagesService,
)
from app.integrations.ocr.errors import OCRError, OCROutputRejected, OCRUnavailable
from app.integrations.ocr.fake import FakeVisionProvider
from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_STAFF

PNG = b"\x89PNG\r\n\x1a\nexample"
JPEG = b"\xff\xd8\xffexample"


class FakeGamesRepository:
    def __init__(self, exists=True):
        self.exists = exists

    def game_exists(self, game_id):
        return self.exists


class FakePagesRepository:
    def __init__(self):
        self.rows = {}
        self.writes = []
        self.deleted = False

    @contextmanager
    def transaction(self):
        yield

    def upsert_page(self, games_id, page, content):
        if self.deleted:
            raise GameNotFoundError(games_id)
        self.writes.append((games_id, page, content))
        self.rows[games_id, page] = content

    def list_pages(self, games_id):
        return [
            {"page": page, "content": content}
            for (game, page), content in sorted(self.rows.items())
            if game == games_id
        ]


class FakeRecordingVisionProvider(FakeVisionProvider):
    def generate_json(self, **kwargs):
        self.received_images = kwargs["images"]
        self.received_schema = kwargs["schema"]
        return super().generate_json(**kwargs)


def make_service(replies=None, exists=True):
    pages = FakePagesRepository()
    vision = FakeRecordingVisionProvider(replies)
    return ManualPagesService(pages, FakeGamesRepository(exists), vision, "fake")


@pytest.mark.parametrize("user", [TEST_ADMIN, TEST_SHOP_STAFF])
@pytest.mark.parametrize("image", [PNG, JPEG])
def test_import_transcribes_original_image_once(user, image):
    service = make_service([{"markdown": "# 標題"}])
    result = service.import_page(user, 1, 1, image)
    assert result.model_dump() == {"games_id": 1, "page": 1, "content": "# 標題"}
    assert service.pages.rows == {(1, 1): "# 標題"}
    assert service.vision.received_images == [image]
    assert len(service.vision.calls) == 1
    assert service.vision.received_schema == TRANSCRIPTION_SCHEMA
    assert TRANSCRIPTION_SCHEMA.schema["additionalProperties"] is False


def test_overwrite_including_empty_page():
    service = make_service([{"markdown": "old"}, {"markdown": "new"}, {"markdown": ""}])
    for expected in ["old", "new", ""]:
        assert service.import_page(TEST_ADMIN, 1, 1, PNG).content == expected
        assert service.pages.rows == {(1, 1): expected}


@pytest.mark.parametrize(
    ("image", "exists", "code"),
    [
        (b"", True, "INVALID_IMAGE"),
        (b"text", True, "INVALID_IMAGE"),
        (PNG + b"x" * MAX_IMAGE_BYTES, True, "IMAGE_TOO_LARGE"),
        (PNG, False, "GAME_NOT_FOUND"),
    ],
)
def test_invalid_input_never_calls_vision_or_writes(image, exists, code):
    service = make_service(exists=exists)
    with pytest.raises(AppError) as error:
        service.import_page(TEST_ADMIN, 999, 1, image)
    assert error.value.code == code
    assert service.vision.calls == []
    assert service.pages.writes == []


@pytest.mark.parametrize("operation", ["import", "list"])
def test_player_denied_before_any_side_effect(operation):
    service = make_service()
    with pytest.raises(AppError) as error:
        if operation == "import":
            service.import_page(TEST_PLAYER, 1, 1, PNG)
        else:
            service.list_pages(TEST_PLAYER, 1)
    assert error.value.status_code == 403
    assert service.vision.calls == []
    assert service.pages.writes == []


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (OCRUnavailable("timeout"), "OCR_UNAVAILABLE"),
        (OCROutputRejected("refused"), "OCR_OUTPUT_REJECTED"),
        (OCRError("secret-key"), "OCR_FAILED"),
    ],
)
def test_ocr_failure_preserves_old_content_and_hides_details(failure, code):
    service = make_service([failure])
    service.pages.rows[1, 1] = "old"
    with pytest.raises(AppError) as error:
        service.import_page(TEST_ADMIN, 1, 1, PNG)
    assert error.value.status_code == 503
    assert error.value.code == code
    assert "secret-key" not in error.value.message
    assert service.pages.rows == {(1, 1): "old"}
    assert service.pages.writes == []


@pytest.mark.parametrize("reply", [{}, {"markdown": 1}, {"markdown": "", "extra": True}])
def test_invalid_model_output_is_rejected(reply):
    service = make_service([reply])
    with pytest.raises(AppError, match="輸出被拒絕"):
        service.import_page(TEST_ADMIN, 1, 1, PNG)
    assert service.pages.writes == []


def test_concurrent_game_deletion_is_not_found():
    service = make_service([{"markdown": "new"}])
    service.pages.deleted = True
    with pytest.raises(AppError) as error:
        service.import_page(TEST_ADMIN, 1, 1, PNG)
    assert error.value.code == "GAME_NOT_FOUND"


@pytest.mark.parametrize("rows", [{}, {(1, 3): "three", (2, 1): "other", (1, 1): ""}])
def test_list_sorted_pages_and_provider_without_vision(rows):
    service = make_service()
    service.pages.rows = rows
    result = service.list_pages(TEST_ADMIN, 1)
    expected = [
        {"page": page, "content": value}
        for (game, page), value in sorted(rows.items())
        if game == 1
    ]
    assert result.model_dump() == {
        "items": expected,
        "total": len(expected),
        "ocr_provider": "fake",
    }
    assert service.vision.calls == []


def test_list_unknown_game():
    service = make_service(exists=False)
    with pytest.raises(AppError) as error:
        service.list_pages(TEST_ADMIN, 999)
    assert error.value.code == "GAME_NOT_FOUND"
