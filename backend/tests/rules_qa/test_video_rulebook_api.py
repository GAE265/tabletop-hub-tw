"""店員拍規則書（照片模式的整本專案；2026-11-22 永傑決定）。

- 建立專案時選「拍規則書」：不讀已匯入的規則書、不自動產生草稿，步驟是 rulebook。
- 上傳、列出、刪除規則書照片（存在存放介面），每張附清晰度判斷。
- 草稿工作先切塊讀取照片（加圖說），寫成這個專案自己的頁面文字，之後照常分類與產生。

連 `_test` 資料庫；LLM 與看圖模型都用 fake（不需要金鑰）；工作用 JobRunner.run_once() 執行。
"""

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.domains.rules_qa.video_draft import DraftJobHandler
from app.domains.rules_qa.video_jobs import JobRunner
from app.integrations.llm.fake import FakeLLMProvider
from app.integrations.ocr.errors import OCRUnavailable
from app.integrations.ocr.fake import FakeVisionProvider
from app.integrations.storage.fake import FakeFileStorage
from tests.rules_qa.heic_support import broken_heic_bytes, heic_bytes, mpo_bytes
from tests.rules_qa.video_script_support import FAKE_PAGE
from tests.rules_qa.video_support import seed_people
from tests.rules_qa.whole_game_support import (
    SETUP_PAGE,
    VARIANT_PAGE,
    WIN_PAGE,
    whole_game_llm_outputs,
)

URL = "/api/v1/rules-videos"


@pytest.fixture
def api(app: FastAPI, rules_db: Engine) -> TestClient:
    seed_people(rules_db)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def storage(app: FastAPI) -> FakeFileStorage:
    return app.state.storage


@pytest.fixture
def game(add_game) -> int:
    # 照片模式不需要已匯入的規則書（games_manual 沒有這款遊戲的頁面）
    return add_game("假遊戲")


def _code(response) -> str:
    return response.json()["error"]["code"]


def photo(blur: bool = False) -> bytes:
    image = Image.new("RGB", (300, 400), (30, 30, 30))
    draw = ImageDraw.Draw(image)
    if not blur:
        for y in range(20, 380, 12):
            for x in range(20, 280, 10):
                draw.rectangle((x, y, x + 5, y + 6), outline=(235, 235, 235))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=90)
    return out.getvalue()


def _create(api, game) -> str:
    response = api.post(URL, json={"game_id": game, "rulebook": "photos"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload(api, project, data=None, name="page.jpg"):
    files = {"file": (name, data or photo(), "image/jpeg")}
    return api.post(f"{URL}/{project}/rulebook/photos", files=files)


def _jobs(rules_db, project):
    with rules_db.connect() as conn:
        return conn.execute(
            text(
                "SELECT kind, status, error, result FROM rules_qa_video_jobs "
                "WHERE project_id = :p ORDER BY created_at"
            ),
            {"p": project},
        ).all()


def _pages(rules_db, project):
    with rules_db.connect() as conn:
        return conn.execute(
            text("SELECT chapter_pages, page_texts FROM rules_qa_video_projects WHERE id = :p"),
            {"p": project},
        ).one()


def tile(text_value: str) -> dict:
    return {"title": "", "text": text_value}


NO_FIGURES = {"figures": []}

# 每張照片：四塊各一次、圖說一次。假規則書四頁的文字放在左上那一塊
PHOTO_READS = [
    reply
    for page in (SETUP_PAGE, FAKE_PAGE, WIN_PAGE, VARIANT_PAGE)
    for reply in (tile(page), tile(""), tile(""), tile(""), NO_FIGURES)
]


def _run(rules_db, storage, llm_outputs, vision_replies):
    llm = FakeLLMProvider(json_outputs=llm_outputs)
    vision = FakeVisionProvider(vision_replies)
    handler = DraftJobHandler(llm, vision=vision, storage=storage, read_workers=1)
    assert JobRunner(sessionmaker(rules_db), {"draft": handler}).run_once()
    return llm, vision


# --- 建立 ---


def test_create_photo_project(api, as_shop_staff, rules_db, game):
    response = api.post(URL, json={"game_id": game, "rulebook": "photos"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["rulebook"] == "photos" and body["step"] == "rulebook"
    assert _jobs(rules_db, body["id"]) == []  # 不自動產生草稿


def test_imported_rulebook_is_the_default(api, as_shop_staff, add_game, add_pages):
    game = add_game("有匯入的遊戲")
    add_pages(game, [(1, SETUP_PAGE)])
    body = api.post(URL, json={"game_id": game}).json()
    assert body["rulebook"] == "imported" and body["step"] == "draft"


def test_photo_rulebook_is_whole_game_only(api, as_shop_staff, game):
    response = api.post(
        URL,
        json={"game_id": game, "rulebook": "photos", "chapter_number": 1, "chapter_title": "x"},
    )
    assert response.status_code == 422


# --- 照片 ---


def test_upload_list_and_delete_photos(api, as_shop_staff, game):
    project = _create(api, game)
    first = _upload(api, project)
    assert first.status_code == 201, first.text
    assert _upload(api, project).status_code == 201
    body = api.get(f"{URL}/{project}/rulebook").json()
    assert [p["index"] for p in body["photos"]] == [1, 2]
    assert body["photos"][0]["id"] != body["photos"][1]["id"]
    assert body["photos"][0]["quality"] == "ok" and body["photos"][0]["width"] == 300
    assert body["read"] is False
    image = api.get(f"{URL}/{project}/rulebook/photos/2")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert api.delete(f"{URL}/{project}/rulebook/photos/1").status_code == 204
    assert [p["index"] for p in api.get(f"{URL}/{project}/rulebook").json()["photos"]] == [1]


def test_blurry_photo_is_flagged(api, as_shop_staff, game):
    project = _create(api, game)
    body = _upload(api, project, photo(blur=True)).json()
    assert body["photos"][0]["quality"] == "bad"
    assert "重拍" in body["photos"][0]["quality_message"]


def test_not_an_image_is_422(api, as_shop_staff, game):
    project = _create(api, game)
    response = _upload(api, project, b"GIF89a not really", name="x.gif")
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_PHOTO_INVALID"


def test_heic_rulebook_photo_is_saved_as_jpeg(api, as_shop_staff, storage, game):
    # iPhone 預設格式：轉成 JPEG 再存，清晰度照常計算（直拍的方向標記 6 會轉正）
    project = _create(api, game)
    response = _upload(api, project, heic_bytes((400, 300), exif_orientation=6), "IMG_0001.HEIC")
    assert response.status_code == 201, response.text
    saved = response.json()["photos"][0]
    assert saved["width"] == 300 and saved["quality"] in ("ok", "bad")
    image = api.get(f"{URL}/{project}/rulebook/photos/1")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    stored = Image.open(io.BytesIO(image.content))
    assert stored.format == "JPEG" and stored.size == (300, 400)


def test_broken_heic_rulebook_photo_is_422_and_leaves_no_file(api, as_shop_staff, storage, game):
    project = _create(api, game)
    response = _upload(api, project, broken_heic_bytes(), "IMG_0002.HEIC")
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_PHOTO_INVALID"
    assert api.get(f"{URL}/{project}/rulebook").json()["photos"] == []
    assert not [k for k in storage.files if k.startswith(f"rules_videos/{project}/")]


def test_mpo_rulebook_photo_is_saved_as_single_jpeg(api, as_shop_staff, game):
    # iPhone 轉出來附 HDR 增益圖的 JPEG（多圖 JPEG）：只留主圖，清晰度照常計算
    project = _create(api, game)
    response = _upload(api, project, mpo_bytes((300, 400)), "IMG_0003.JPG")
    assert response.status_code == 201, response.text
    saved = response.json()["photos"][0]
    assert saved["width"] == 300 and saved["quality"] in ("ok", "bad")
    image = api.get(f"{URL}/{project}/rulebook/photos/1")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    stored = Image.open(io.BytesIO(image.content))
    assert stored.format == "JPEG" and getattr(stored, "n_frames", 1) == 1


def test_unknown_photo_index_is_404(api, as_shop_staff, game):
    project = _create(api, game)
    assert api.delete(f"{URL}/{project}/rulebook/photos/3").status_code == 404


def test_imported_project_has_no_photo_rulebook(api, as_shop_staff, add_game, add_pages):
    game = add_game("有匯入的遊戲")
    add_pages(game, [(1, SETUP_PAGE)])
    project = api.post(URL, json={"game_id": game}).json()["id"]
    response = _upload(api, project)
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_NOT_PHOTO_RULEBOOK"


def test_player_cannot_read_rulebook(api, as_player):
    response = api.get(f"{URL}/00000000-0000-0000-0000-000000000001/rulebook")
    assert response.status_code == 403


# --- 草稿工作先讀照片 ---


def test_draft_job_reads_photos_then_generates(api, as_shop_staff, rules_db, storage, game):
    project = _create(api, game)
    for _ in range(4):
        assert _upload(api, project).status_code == 201
    assert api.post(f"{URL}/{project}/jobs", json={"kind": "draft"}).status_code == 202
    _, vision = _run(rules_db, storage, whole_game_llm_outputs(), PHOTO_READS)
    jobs = _jobs(rules_db, project)
    assert jobs[-1].status == "succeeded", jobs[-1].error
    assert jobs[-1].result["rulebook_photos"] == 4
    assert len(vision.calls) == 4 * 5
    # 每次呼叫的用量都記在工作結果（2026-11-23 永傑要求）：看圖 20 次＋LLM 7 次
    usage = jobs[-1].result["usage"]
    assert usage["calls"] == 20 + 7
    assert usage["by_name"]["rulebook_tile"]["calls"] == 16
    chapter_pages, page_texts = _pages(rules_db, project)
    assert chapter_pages == [1, 2, 3, 4]
    assert page_texts["1"]["text"].startswith("Setup.") and page_texts["1"]["photo"]
    body = api.get(f"{URL}/{project}").json()
    assert body["rulebook"] == "photos" and body["step"] == "draft"
    assert api.get(f"{URL}/{project}/rulebook").json()["read"] is True


def test_regenerate_does_not_read_unchanged_photos(api, as_shop_staff, rules_db, storage, game):
    project = _create(api, game)
    for _ in range(4):
        _upload(api, project)
    api.post(f"{URL}/{project}/jobs", json={"kind": "draft"})
    _run(rules_db, storage, whole_game_llm_outputs(), PHOTO_READS)
    api.post(f"{URL}/{project}/jobs", json={"kind": "draft"})
    _, vision = _run(rules_db, storage, whole_game_llm_outputs(), [])
    assert _jobs(rules_db, project)[-1].status == "succeeded"
    assert vision.calls == []


def test_new_photo_is_read_on_next_draft(api, as_shop_staff, rules_db, storage, game):
    project = _create(api, game)
    for _ in range(4):
        _upload(api, project)
    api.post(f"{URL}/{project}/jobs", json={"kind": "draft"})
    _run(rules_db, storage, whole_game_llm_outputs(), PHOTO_READS)
    _upload(api, project)
    assert api.get(f"{URL}/{project}/rulebook").json()["read"] is False
    api.post(f"{URL}/{project}/jobs", json={"kind": "draft"})
    extra = [tile("Designer notes."), tile(""), tile(""), tile(""), NO_FIGURES]
    _, vision = _run(rules_db, storage, whole_game_llm_outputs(), PHOTO_READS + extra)
    assert len(vision.calls) == 5 * 5
    assert _pages(rules_db, project).chapter_pages == [1, 2, 3, 4, 5]


def test_draft_without_photos_fails(api, as_shop_staff, rules_db, storage, game):
    project = _create(api, game)
    api.post(f"{URL}/{project}/jobs", json={"kind": "draft"})
    _run(rules_db, storage, [], [])
    job = _jobs(rules_db, project)[-1]
    assert job.status == "failed"
    assert job.error == "還沒有拍規則書：請先拍規則書的每一頁，再產生草稿"


def test_vision_unavailable_fails_without_retry(api, as_shop_staff, rules_db, storage, game):
    project = _create(api, game)
    _upload(api, project)
    api.post(f"{URL}/{project}/jobs", json={"kind": "draft"})
    _, vision = _run(rules_db, storage, [], [OCRUnavailable("連不上")])
    job = _jobs(rules_db, project)[-1]
    assert job.status == "failed"
    assert job.error == "看圖服務暫時無法使用，請稍後再試"
    assert len(vision.calls) == 1
