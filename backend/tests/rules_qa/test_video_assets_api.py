"""素材 API（add-rules-video-mobile MR 7，design.md D13 與實作決定）。

上傳照片：PUT /rules-videos/{id}/assets/{asset_key}/photo；讀照片：GET 同一路徑；
素材明細：GET /rules-videos/{id}/assets/{asset_key}；方向與區域：PATCH 同一路徑；
缺什麼：GET /rules-videos/{id}/readiness。存放介面用 app.state.storage（測試時是 FakeFileStorage）。
"""

import io
import json
import time
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.domains.rules_qa.video_assets import MAX_PHOTO_BYTES
from app.domains.rules_qa.video_draft import DraftJobHandler
from app.domains.rules_qa.video_jobs import JobRunner
from app.integrations.llm.fake import FakeLLMProvider
from app.integrations.storage.fake import FakeFileStorage
from tests.rules_qa.heic_support import broken_heic_bytes, heic_bytes, mpo_bytes, noisy_heic_bytes
from tests.rules_qa.video_draft_support import FakeHookLLM, add_manual, project_row, set_pages
from tests.rules_qa.video_script_support import coverage_output, llm_output
from tests.rules_qa.video_support import OTHER_STAFF, insert_job, insert_project, seed_people

URL = "/api/v1/rules-videos"


def image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (40, 20), exif_orientation=None):
    image = Image.new("RGB", size, (200, 30, 30))
    out = io.BytesIO()
    if exif_orientation is not None:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation  # Orientation
        image.save(out, fmt, exif=exif)
    else:
        image.save(out, fmt)
    return out.getvalue()


@pytest.fixture
def api(app: FastAPI, rules_db: Engine) -> TestClient:
    seed_people(rules_db)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def storage(app: FastAPI) -> FakeFileStorage:
    assert isinstance(app.state.storage, FakeFileStorage)
    return app.state.storage


@pytest.fixture
def game(api, add_game, add_pages) -> int:
    game = add_game("假遊戲")
    add_manual(add_pages, game)
    return game


def _run_draft(rules_db: Engine, project: uuid.UUID, output=None, llm=None) -> bool:
    insert_job(rules_db, project, kind="draft")
    llm = llm or FakeLLMProvider(json_outputs=[output or llm_output(), coverage_output()])
    return JobRunner(sessionmaker(rules_db), {"draft": DraftJobHandler(llm)}).run_once()


@pytest.fixture
def project(rules_db: Engine, game: int) -> uuid.UUID:
    """有草稿的專案：素材 back、red、blue、board（board 有區域 zone_a）。"""
    project = insert_project(rules_db, game)
    set_pages(rules_db, project)
    assert _run_draft(rules_db, project)
    return project


def _code(response) -> str:
    return response.json()["error"]["code"]


def _upload(api, project, key="board", data=None, name="photo.jpg", mime="image/jpeg"):
    files = {"file": (name, data if data is not None else image_bytes(), mime)}
    return api.put(f"{URL}/{project}/assets/{key}/photo", files=files)


def _asset(rules_db: Engine, project: uuid.UUID, key: str) -> dict:
    video = project_row(rules_db, project).video
    return next(a for a in video["assets"] if a["asset_key"] == key)


def _updated_at(rules_db: Engine, project: uuid.UUID):
    with rules_db.connect() as conn:
        return conn.scalar(
            text("SELECT updated_at FROM rules_qa_video_projects WHERE id = :p"), {"p": project}
        )


# --- 上傳照片 ---


def test_upload_jpeg(api, as_shop_staff, rules_db, storage, project):
    before = _updated_at(rules_db, project)
    response = _upload(api, project)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["asset_key"] == "board" and data["has_photo"] is True
    assert data["video_version"] == 2
    file = _asset(rules_db, project, "board")["file"]
    assert file.startswith("board-") and file.endswith(".jpg")
    key = f"rules_videos/{project}/assets/{file}"
    assert key in storage.files and storage.content_types[key] == "image/jpeg"
    assert project_row(rules_db, project).video_version == 2
    assert _updated_at(rules_db, project) > before


def test_upload_png(api, as_shop_staff, rules_db, storage, project):
    response = _upload(api, project, data=image_bytes("PNG"), name="p.png", mime="image/png")
    assert response.status_code == 200, response.text
    assert _asset(rules_db, project, "board")["file"].endswith(".png")


def test_replace_photo_deletes_old_file(api, as_shop_staff, rules_db, storage, project):
    _upload(api, project)
    old = f"rules_videos/{project}/assets/{_asset(rules_db, project, 'board')['file']}"
    assert _upload(api, project).status_code == 200
    new = f"rules_videos/{project}/assets/{_asset(rules_db, project, 'board')['file']}"
    assert new != old and new in storage.files and old not in storage.files


def test_exif_orientation_is_applied(api, as_shop_staff, rules_db, storage, project):
    # 直拍的手機照片：EXIF 方向 6（要順時針轉 90 度），存成轉正後的圖
    data = image_bytes(size=(40, 20), exif_orientation=6)
    assert _upload(api, project, data=data).status_code == 200
    stored = storage.files[
        f"rules_videos/{project}/assets/{_asset(rules_db, project, 'board')['file']}"
    ]
    image = Image.open(io.BytesIO(stored))
    assert image.size == (20, 40)
    assert image.getexif().get(0x0112) in (None, 1)


def test_new_photo_resets_orientation_and_keeps_regions(api, as_shop_staff, rules_db, project):
    _upload(api, project)
    body = {"orientation": 90, "regions": {"zone_a": [0.1, 0.2, 0.3, 0.4]}}
    assert api.patch(f"{URL}/{project}/assets/board", json=body).status_code == 200
    data = _upload(api, project).json()
    assert data["orientation"] == 0
    assert data["regions"] == {"zone_a": [0.1, 0.2, 0.3, 0.4]}


def test_not_an_image_is_422(api, as_shop_staff, project):
    response = _upload(api, project, data=b"not an image", name="x.jpg")
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_PHOTO_INVALID"


def test_gif_is_422(api, as_shop_staff, project):
    response = _upload(api, project, data=image_bytes("GIF"), name="x.gif", mime="image/gif")
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_PHOTO_INVALID"
    assert "JPEG" in response.json()["error"]["message"]


def test_too_large_is_422(api, as_shop_staff, project):
    assert MAX_PHOTO_BYTES == 15 * 1024 * 1024
    response = _upload(api, project, data=b"x" * (MAX_PHOTO_BYTES + 1))
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_PHOTO_TOO_LARGE"


# --- HEIC（iPhone 預設格式）：轉成 JPEG 再存 ---


def _stored(rules_db, storage, project, key="board") -> tuple[str, bytes]:
    stored_key = f"rules_videos/{project}/assets/{_asset(rules_db, project, key)['file']}"
    return stored_key, storage.files[stored_key]


def test_heic_is_saved_as_jpeg(api, as_shop_staff, rules_db, storage, project):
    response = _upload(api, project, data=heic_bytes((40, 20)), name="IMG_0001.HEIC")
    assert response.status_code == 200, response.text
    assert _asset(rules_db, project, "board")["file"].endswith(".jpg")
    stored_key, stored = _stored(rules_db, storage, project)
    assert storage.content_types[stored_key] == "image/jpeg"
    image = Image.open(io.BytesIO(stored))
    assert image.format == "JPEG" and image.size == (40, 20)


def test_heic_orientation_is_applied(api, as_shop_staff, rules_db, storage, project):
    # 直拍的 iPhone 照片：方向標記 6（要順時針轉 90 度），存成轉正後的 JPEG、拿掉方向標記
    data = heic_bytes((40, 20), exif_orientation=6)
    assert _upload(api, project, data=data, name="IMG_0002.HEIC").status_code == 200
    image = Image.open(io.BytesIO(_stored(rules_db, storage, project)[1]))
    assert image.format == "JPEG" and image.size == (20, 40)
    assert image.getexif().get(0x0112) in (None, 1)


def test_read_heic_photo_is_jpeg(api, as_shop_staff, project):
    assert _upload(api, project, data=heic_bytes(), name="IMG_0003.HEIC").status_code == 200
    response = api.get(f"{URL}/{project}/assets/board/photo")
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"


def test_transparent_heic_becomes_opaque_jpeg(api, as_shop_staff, rules_db, storage, project):
    data = heic_bytes((40, 20), mode="RGBA")
    assert _upload(api, project, data=data, name="IMG_0004.HEIC").status_code == 200, data[:12]
    image = Image.open(io.BytesIO(_stored(rules_db, storage, project)[1]))
    assert image.format == "JPEG" and image.mode == "RGB"


def test_broken_heic_is_422_and_leaves_no_file(api, as_shop_staff, rules_db, storage, project):
    before_version = project_row(rules_db, project).video_version
    response = _upload(api, project, data=broken_heic_bytes(), name="IMG_0005.HEIC")
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_PHOTO_INVALID"
    assert not [k for k in storage.files if k.startswith(f"rules_videos/{project}/")]
    assert not _asset(rules_db, project, "board").get("file")
    assert project_row(rules_db, project).video_version == before_version


def test_unsupported_format_message_mentions_heic(api, as_shop_staff, project):
    response = _upload(api, project, data=image_bytes("GIF"), name="x.gif", mime="image/gif")
    assert response.status_code == 422
    assert response.json()["error"]["message"].endswith("只能上傳 JPEG、PNG 或 HEIC 照片")


def test_large_heic_converts_in_reasonable_time(api, as_shop_staff, rules_db, storage, project):
    # iPhone 照片的尺寸（4032×3024）、接近 15 MB 的上限：轉檔（含上傳）要在 15 秒內完成
    data = noisy_heic_bytes((4032, 3024), quality=80)
    assert 14 * 1024 * 1024 < len(data) <= MAX_PHOTO_BYTES, len(data)
    started = time.perf_counter()
    response = _upload(api, project, data=data, name="IMG_0006.HEIC")
    elapsed = time.perf_counter() - started
    assert response.status_code == 200, response.text
    print(f"\n大圖 HEIC {len(data) / 1024 / 1024:.1f} MiB 上傳加轉檔：{elapsed:.2f} 秒")
    assert elapsed < 15
    image = Image.open(io.BytesIO(_stored(rules_db, storage, project)[1]))
    assert image.format == "JPEG" and image.size == (4032, 3024)


# --- 多圖 JPEG（MPO）：iPhone 把 HEIC 轉成 JPEG 時會附 HDR 增益圖，只留主圖存成一般 JPEG ---


def test_mpo_is_saved_as_single_jpeg(api, as_shop_staff, rules_db, storage, project):
    response = _upload(api, project, data=mpo_bytes((40, 20)), name="IMG_0007.JPG")
    assert response.status_code == 200, response.text
    assert _asset(rules_db, project, "board")["file"].endswith(".jpg")
    stored_key, stored = _stored(rules_db, storage, project)
    assert storage.content_types[stored_key] == "image/jpeg"
    image = Image.open(io.BytesIO(stored))
    assert image.format == "JPEG" and image.size == (40, 20)
    assert getattr(image, "n_frames", 1) == 1


def test_mpo_orientation_is_applied(api, as_shop_staff, rules_db, storage, project):
    data = mpo_bytes((40, 20), exif_orientation=6)
    assert _upload(api, project, data=data, name="IMG_0008.JPG").status_code == 200
    image = Image.open(io.BytesIO(_stored(rules_db, storage, project)[1]))
    assert image.format == "JPEG" and image.size == (20, 40)
    assert image.getexif().get(0x0112) in (None, 1)


def test_unknown_asset_is_404(api, as_shop_staff, project):
    response = _upload(api, project, key="nope")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_ASSET_NOT_FOUND"


def test_no_draft_is_404(api, as_shop_staff, rules_db, game):
    bare = insert_project(rules_db, game)
    response = _upload(api, bare)
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_DRAFT_NOT_FOUND"


def test_upload_keeps_coverage_fresh(api, as_shop_staff, project):
    # 只改素材不讓涵蓋檢查過期（MR 5 的決定）
    _upload(api, project)
    assert api.get(f"{URL}/{project}/draft").json()["coverage"]["status"] == "done"
    assert {a["asset_key"]: a for a in api.get(f"{URL}/{project}/draft").json()["assets"]}["board"][
        "has_photo"
    ]


# --- 讀照片 ---


def test_read_photo(api, as_shop_staff, project):
    data = image_bytes()
    _upload(api, project, data=data)
    response = api.get(f"{URL}/{project}/assets/board/photo")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == data


def test_read_photo_missing_is_404(api, as_shop_staff, project):
    response = api.get(f"{URL}/{project}/assets/board/photo")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PHOTO_NOT_FOUND"


# --- 素材明細、方向、區域 ---


def test_asset_detail(api, as_shop_staff, project):
    response = api.get(f"{URL}/{project}/assets/board")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["has_photo"] is False and data["orientation"] == 0
    assert data["regions"] == {"zone_a": None}
    assert data["priority"] == "must" and data["kind"] == "flat_photo"
    assert data["shot"] and data["reason"]


def test_set_orientation(api, as_shop_staff, rules_db, project):
    response = api.patch(f"{URL}/{project}/assets/board", json={"orientation": 90})
    assert response.status_code == 200, response.text
    assert response.json()["orientation"] == 90
    assert _asset(rules_db, project, "board")["orientation"] == 90
    assert project_row(rules_db, project).video_version == 2


def test_bad_orientation_is_422(api, as_shop_staff, project):
    assert api.patch(f"{URL}/{project}/assets/board", json={"orientation": 45}).status_code == 422


def test_set_region(api, as_shop_staff, rules_db, project):
    body = {"regions": {"zone_a": [0.1, 0.2, 0.5, 0.5]}}
    response = api.patch(f"{URL}/{project}/assets/board", json=body)
    assert response.status_code == 200, response.text
    assert _asset(rules_db, project, "board")["regions"] == {"zone_a": [0.1, 0.2, 0.5, 0.5]}


@pytest.mark.parametrize(
    "regions",
    [
        {"zone_a": [0.6, 0.1, 0.5, 0.5]},  # 超出右邊
        {"zone_a": [-0.1, 0.1, 0.5, 0.5]},  # 負的
        {"zone_a": [0.1, 0.1, 0, 0.5]},  # 寬 0
        {"zone_a": [0.1, 0.1, 0.5]},  # 少一個數字
        {"nope": [0.1, 0.1, 0.5, 0.5]},  # 草稿沒有這個區域
    ],
    ids=["right", "negative", "zero-width", "short", "unknown-name"],
)
def test_bad_region_is_422(api, as_shop_staff, rules_db, project, regions):
    response = api.patch(f"{URL}/{project}/assets/board", json={"regions": regions})
    assert response.status_code == 422
    assert project_row(rules_db, project).video_version == 1  # 沒有寫入


def test_orientation_change_clears_regions(api, as_shop_staff, rules_db, project):
    body = {"regions": {"zone_a": [0.1, 0.2, 0.5, 0.5]}}
    api.patch(f"{URL}/{project}/assets/board", json=body)
    response = api.patch(f"{URL}/{project}/assets/board", json={"orientation": 180})
    assert response.json()["regions"] == {"zone_a": None}
    # 同時給方向與區域：用給的區域
    body = {"orientation": 90, "regions": {"zone_a": [0.1, 0.1, 0.2, 0.2]}}
    assert api.patch(f"{URL}/{project}/assets/board", json=body).json()["regions"] == {
        "zone_a": [0.1, 0.1, 0.2, 0.2]
    }


def test_same_orientation_keeps_regions(api, as_shop_staff, project):
    body = {"regions": {"zone_a": [0.1, 0.2, 0.5, 0.5]}}
    api.patch(f"{URL}/{project}/assets/board", json=body)
    response = api.patch(f"{URL}/{project}/assets/board", json={"orientation": 0})
    assert response.json()["regions"] == {"zone_a": [0.1, 0.2, 0.5, 0.5]}


# --- 缺什麼 ---


def test_readiness_lists_missing(api, as_shop_staff, project):
    response = api.get(f"{URL}/{project}/readiness")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ready"] is False
    assert {m["asset_key"] for m in data["missing_photos"]} == {"back", "red", "blue", "board"}
    assert all(m["priority"] == "must" for m in data["missing_photos"])
    assert data["missing_regions"] == [{"asset_key": "board", "region": "zone_a"}]
    assert data["unsupported"] == []


def test_readiness_all_done(api, as_shop_staff, project):
    for key in ("back", "red", "blue", "board"):
        assert _upload(api, project, key=key).status_code == 200
    body = {"regions": {"zone_a": [0.1, 0.2, 0.5, 0.5]}}
    api.patch(f"{URL}/{project}/assets/board", json=body)
    data = api.get(f"{URL}/{project}/readiness").json()
    assert data == {"ready": True, "missing_photos": [], "missing_regions": [], "unsupported": []}


def test_readiness_optional_and_drawn(api, as_shop_staff, rules_db, project):
    # 選拍沒有照片也列出（第 1 階段的段資料要求每個照片素材都有檔案）；繪製素材註明本版不支援
    video = project_row(rules_db, project).video
    for asset in video["assets"]:
        if asset["asset_key"] == "blue":
            asset["priority"] = "optional"
        if asset["asset_key"] == "back":
            asset["kind"] = "drawn"
    with rules_db.begin() as conn:
        conn.execute(
            text("UPDATE rules_qa_video_projects SET video = CAST(:v AS jsonb) WHERE id = :p"),
            {"v": json.dumps(video, ensure_ascii=False), "p": project},
        )
    data = api.get(f"{URL}/{project}/readiness").json()
    missing = {m["asset_key"]: m["priority"] for m in data["missing_photos"]}
    assert missing == {"red": "must", "blue": "optional", "board": "must"}
    assert data["unsupported"] == [
        {"asset_key": "back", "kind": "drawn", "message": "本版不支援繪製素材，請改成拍照"}
    ]


def test_readiness_without_draft_is_404(api, as_shop_staff, rules_db, game):
    bare = insert_project(rules_db, game)
    response = api.get(f"{URL}/{bare}/readiness")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_DRAFT_NOT_FOUND"


# --- 重新產生草稿時沿用 ---


def test_regenerate_keeps_photo_orientation_and_regions(
    api, as_shop_staff, rules_db, storage, project
):
    _upload(api, project)
    body = {"orientation": 90, "regions": {"zone_a": [0.1, 0.2, 0.5, 0.5]}}
    api.patch(f"{URL}/{project}/assets/board", json=body)
    file = _asset(rules_db, project, "board")["file"]

    assert _run_draft(rules_db, project)
    board = _asset(rules_db, project, "board")
    assert board["file"] == file
    assert board["orientation"] == 90
    assert board["regions"] == {"zone_a": [0.1, 0.2, 0.5, 0.5]}
    assert f"rules_videos/{project}/assets/{file}" in storage.files


def test_regenerate_without_asset_keeps_file_in_storage(
    api, as_shop_staff, rules_db, storage, project
):
    _upload(api, project, key="blue")
    file = _asset(rules_db, project, "blue")["file"]
    output = llm_output()
    output["assets"] = [a for a in output["assets"] if a["asset_key"] != "blue"]
    _swap_asset(output, "blue", "red")
    assert _run_draft(rules_db, project, output=output)
    assert "blue" not in {a["asset_key"] for a in project_row(rules_db, project).video["assets"]}
    assert f"rules_videos/{project}/assets/{file}" in storage.files


def _swap_asset(node, old: str, new: str) -> None:
    """把段資料裡引用 old 素材的地方都換成 new（讓少一個素材的草稿仍然有效）。"""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("asset_key", "back_asset_key") and value == old:
                node[key] = new
            else:
                _swap_asset(value, old, new)
    elif isinstance(node, list):
        for value in node:
            _swap_asset(value, old, new)


def test_upload_during_draft_job_fails_job_and_keeps_photo(
    api, as_shop_staff, rules_db, storage, project
):
    # 草稿工作進行中上傳照片：工作寫入前發現版本變了 → 失敗、不覆寫；照片保留
    def upload() -> None:
        assert _upload(api, project).status_code == 200

    llm = FakeHookLLM([llm_output(), coverage_output()], hook_at=2, hook=upload)
    _run_draft(rules_db, project, llm=llm)
    with rules_db.connect() as conn:
        status = conn.scalar(
            text(
                "SELECT status FROM rules_qa_video_jobs WHERE project_id = :p "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"p": project},
        )
    assert status == "failed"
    file = _asset(rules_db, project, "board")["file"]
    assert file and f"rules_videos/{project}/assets/{file}" in storage.files


# --- 權限 ---


def test_other_shop_is_404(api, as_shop_staff, rules_db, game):
    other = insert_project(rules_db, game, OTHER_STAFF)
    set_pages(rules_db, other)
    assert _run_draft(rules_db, other)
    for response in (
        _upload(api, other),
        api.get(f"{URL}/{other}/assets/board/photo"),
        api.get(f"{URL}/{other}/assets/board"),
        api.patch(f"{URL}/{other}/assets/board", json={"orientation": 90}),
        api.get(f"{URL}/{other}/readiness"),
    ):
        assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_player_is_403(api, as_player, project):
    assert _upload(api, project).status_code == 403
    assert api.get(f"{URL}/{project}/assets/board/photo").status_code == 403
    assert api.get(f"{URL}/{project}/assets/board").status_code == 403
    assert api.patch(f"{URL}/{project}/assets/board", json={"orientation": 90}).status_code == 403
    assert api.get(f"{URL}/{project}/readiness").status_code == 403


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, project):
    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert _upload(client, project).status_code == 401
    assert client.get(f"{URL}/{project}/assets/board/photo").status_code == 401
    assert client.get(f"{URL}/{project}/readiness").status_code == 401


# --- 存放介面的設定（main.py 建立 app.state.storage） ---


def test_default_storage_is_fake(make_settings, test_db_url):
    from app.main import create_app

    app = create_app(make_settings(database_url=test_db_url))
    assert isinstance(app.state.storage, FakeFileStorage)


def test_local_storage(make_settings, test_db_url, tmp_path):
    from app.integrations.storage.local import LocalFileStorage
    from app.main import create_app

    settings = make_settings(
        database_url=test_db_url,
        storage_provider="local",
        storage_local_dir=str(tmp_path),
        storage_public_base_url="http://localhost:8000/media",
    )
    assert isinstance(create_app(settings).state.storage, LocalFileStorage)


def test_bad_storage_setting_stops_startup(make_settings, test_db_url):
    # 存放設定寫錯：啟動時就報錯（整個後端起不來），說明缺哪個設定
    from app.main import create_app

    settings = make_settings(database_url=test_db_url, storage_provider="local")
    with pytest.raises(ValueError, match="storage_local_dir|local_dir"):
        create_app(settings)
