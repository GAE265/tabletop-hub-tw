"""產生影片 API 與選拍略過（add-rules-video-mobile MR 9，design.md D15 與實作決定）。

建立工作：POST /rules-videos/{id}/jobs（kind=render）；成品：GET /rules-videos/{id}/render、
GET /rules-videos/{id}/render/video；略過：PATCH /rules-videos/{id}/assets/{key}（skipped）。
用手寫的假 ffmpeg 指令稿與 FakeTTSProvider，不需要安裝 ffmpeg、不需要金鑰。
"""

import io
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.domains.rules_qa.video_draft import DraftJobHandler
from app.domains.rules_qa.video_jobs import JobRunner
from app.domains.rules_qa.video_render import (
    RENDER_TIMEOUT_MESSAGE,
    RenderConfig,
    RenderJobHandler,
)
from app.integrations.llm.fake import FakeLLMProvider
from app.integrations.storage.fake import FakeFileStorage
from app.integrations.tts import FakeTTSProvider, TTSConfig, TTSUnavailable
from app.integrations.video import load_video
from tests.integrations.video.support import fake_ffmpeg
from tests.rules_qa.video_draft_support import add_manual, project_row, set_pages
from tests.rules_qa.video_script_support import coverage_output, llm_output
from tests.rules_qa.video_support import OTHER_STAFF, insert_job, insert_project, seed_people

URL = "/api/v1/rules-videos"
ASSETS = ("back", "red", "blue", "board")


class FakeDownTTSProvider(FakeTTSProvider):
    """手寫的 fake：語音服務連不上。"""

    def synthesize(self, text: str, voice: str | None = None):
        raise TTSUnavailable("語音服務逾時")


def png(color=(200, 30, 30), size=(60, 90)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def api(app: FastAPI, rules_db: Engine) -> TestClient:
    seed_people(rules_db)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def storage(app: FastAPI) -> FakeFileStorage:
    return app.state.storage


@pytest.fixture
def game(api, add_game, add_pages) -> int:
    game = add_game("假遊戲")
    add_manual(add_pages, game)
    return game


def _code(response) -> str:
    return response.json()["error"]["code"]


def _run_draft(rules_db: Engine, project: uuid.UUID) -> None:
    insert_job(rules_db, project, kind="draft")
    llm = FakeLLMProvider(json_outputs=[llm_output(), coverage_output()])
    assert JobRunner(sessionmaker(rules_db), {"draft": DraftJobHandler(llm)}).run_once()


def _upload(api, project, key, data=None):
    files = {"file": (f"{key}.png", data or png(), "image/png")}
    response = api.put(f"{URL}/{project}/assets/{key}/photo", files=files)
    assert response.status_code == 200, response.text


def _make_ready(api, project) -> None:
    for key in ASSETS:
        _upload(api, project, key)
    body = {"regions": {"zone_a": [0.1, 0.1, 0.4, 0.4]}}
    assert api.patch(f"{URL}/{project}/assets/board", json=body).status_code == 200


@pytest.fixture
def project(rules_db: Engine, game: int) -> uuid.UUID:
    project = insert_project(rules_db, game)
    set_pages(rules_db, project)
    _run_draft(rules_db, project)
    return project


@pytest.fixture
def ready(api, as_shop_staff, project) -> uuid.UUID:
    _make_ready(api, project)
    return project


def _config(tmp_path: Path, command: list[str], timeout: float = 600) -> RenderConfig:
    return RenderConfig(
        work_dir=tmp_path / "work",
        ffmpeg_command=command,
        ffmpeg_timeout_seconds=timeout,
        font_regular=None,
        font_bold=None,
        font_index=0,
        music_volume=0.25,
        tts=TTSConfig(provider="fake"),
    )


def _render(rules_db, storage, project, tmp_path, *, command=None, tts=None, timeout=600):
    """建立並執行一個產生影片的工作；回傳工作那一列。"""
    job = insert_job(rules_db, project, kind="render")
    handler = RenderJobHandler(
        storage, _config(tmp_path, command or fake_ffmpeg(tmp_path / "bin"), timeout), tts=tts
    )
    assert JobRunner(sessionmaker(rules_db), {"render": handler}).run_once()
    with rules_db.connect() as conn:
        return conn.execute(
            text("SELECT * FROM rules_qa_video_jobs WHERE id = :i"), {"i": job}
        ).one()


def _set_video(rules_db: Engine, project: uuid.UUID, video: dict) -> None:
    with rules_db.begin() as conn:
        conn.execute(
            text("UPDATE rules_qa_video_projects SET video = CAST(:v AS jsonb) WHERE id = :p"),
            {"v": json.dumps(video, ensure_ascii=False), "p": project},
        )


def _make_optional(rules_db: Engine, project: uuid.UUID, *keys: str) -> None:
    video = project_row(rules_db, project).video
    for asset in video["assets"]:
        if asset["asset_key"] in keys:
            asset["priority"] = "optional"
    _set_video(rules_db, project, video)


# --- 建立工作 ---


def test_create_render_job_is_202(api, ready):
    response = api.post(f"{URL}/{ready}/jobs", json={"kind": "render"})
    assert response.status_code == 202, response.text
    assert response.json()["kind"] == "render"


def test_not_ready_is_422(api, as_shop_staff, project):
    response = api.post(f"{URL}/{project}/jobs", json={"kind": "render"})
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_NOT_READY"
    details = response.json()["error"]["details"]
    assert {m["asset_key"] for m in details["missing_photos"]} == set(ASSETS)
    assert details["missing_regions"] == [{"asset_key": "board", "region": "zone_a"}]
    assert api.get(f"{URL}/{project}/jobs").json()["total"] == 1  # 只有草稿那一個


def test_drawn_asset_is_not_ready(api, ready, rules_db):
    video = project_row(rules_db, ready).video
    video["assets"][0]["kind"] = "drawn"
    _set_video(rules_db, ready, video)
    response = api.post(f"{URL}/{ready}/jobs", json={"kind": "render"})
    assert response.status_code == 422
    assert "本版不支援" in response.json()["error"]["details"]["unsupported"][0]["message"]


def test_render_without_draft_is_404(api, as_shop_staff, rules_db, game):
    bare = insert_project(rules_db, game)
    response = api.post(f"{URL}/{bare}/jobs", json={"kind": "render"})
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_DRAFT_NOT_FOUND"


# --- 執行 ---


def test_render_succeeds_and_stores_video(api, ready, rules_db, storage, tmp_path):
    job = _render(rules_db, storage, ready, tmp_path)
    assert job.status == "succeeded", job.error
    result = job.result
    assert result["video_key"] == f"rules_videos/{ready}/renders/{job.id}.mp4"
    assert result["video_key"] in storage.files
    assert result["total_seconds"] > 0
    assert sorted(result["reencoded"]) == ["s1", "s2"] and result["reused"] == []
    assert result["estimated"] is True  # TTS 用 fake：時間為估計值
    # 工作資料夾展開了段資料與照片
    folder = tmp_path / "work" / str(ready)
    assert (folder / "video.json").is_file()
    assert load_video(folder).assets["board"].regions["zone_a"] is not None


def test_render_reports_progress(api, ready, rules_db, storage, tmp_path):
    from app.domains.rules_qa.video_jobs import JobContext

    messages: list[str] = []
    handler = RenderJobHandler(storage, _config(tmp_path, fake_ffmpeg(tmp_path / "bin")))
    ctx = JobContext(
        job_id=uuid.uuid4(),
        project_id=ready,
        kind="render",
        session_factory=sessionmaker(rules_db),
        _report=lambda job_id, progress, message: messages.append(message),
    )
    handler(ctx)
    assert "段影片 1／2" in messages and "段影片 2／2" in messages
    assert messages.index("段影片 2／2") < messages.index("混音")
    assert messages[-1] == "儲存影片"


def test_only_changed_segment_is_reencoded(api, ready, rules_db, storage, tmp_path):
    command = fake_ffmpeg(tmp_path / "bin")
    assert _render(rules_db, storage, ready, tmp_path, command=command).status == "succeeded"
    # board 只用在 s1 的側欄
    _upload(api, ready, "board", png((10, 200, 10), (80, 60)))
    api.patch(f"{URL}/{ready}/assets/board", json={"regions": {"zone_a": [0.1, 0.1, 0.4, 0.4]}})
    job = _render(rules_db, storage, ready, tmp_path, command=command)
    assert job.status == "succeeded", job.error
    assert job.result["reencoded"] == ["s1"] and job.result["reused"] == ["s2"]


def test_cache_removed_reencodes_everything(api, ready, rules_db, storage, tmp_path):
    command = fake_ffmpeg(tmp_path / "bin")
    _render(rules_db, storage, ready, tmp_path, command=command)
    shutil.rmtree(tmp_path / "work")
    job = _render(rules_db, storage, ready, tmp_path, command=command)
    assert job.status == "succeeded", job.error
    assert sorted(job.result["reencoded"]) == ["s1", "s2"]


def test_ffmpeg_failure_keeps_previous_render(api, ready, rules_db, storage, tmp_path):
    first = _render(rules_db, storage, ready, tmp_path)
    job = _render(
        rules_db, storage, ready, tmp_path, command=fake_ffmpeg(tmp_path / "b2", fail=True)
    )
    assert job.status == "failed"
    assert "影片輸出失敗" in job.error and "fake encoder exploded" not in job.error
    data = api.get(f"{URL}/{ready}/render").json()
    assert data["job_id"] == str(first.id)


def test_ffmpeg_timeout_fails_job(api, ready, rules_db, storage, tmp_path):
    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    job = _render(
        rules_db, storage, ready, tmp_path, command=[sys.executable, str(slow)], timeout=0.5
    )
    assert job.status == "failed"
    assert job.error == RENDER_TIMEOUT_MESSAGE


def test_tts_failure_fails_job(api, ready, rules_db, storage, tmp_path):
    job = _render(rules_db, storage, ready, tmp_path, tts=FakeDownTTSProvider())
    assert job.status == "failed"
    assert "旁白" in job.error and "稍後再試" in job.error


def test_render_touches_updated_at(api, ready, rules_db, storage, tmp_path):
    with rules_db.connect() as conn:
        before = conn.scalar(
            text("SELECT updated_at FROM rules_qa_video_projects WHERE id = :p"), {"p": ready}
        )
    _render(rules_db, storage, ready, tmp_path)
    with rules_db.connect() as conn:
        after = conn.scalar(
            text("SELECT updated_at FROM rules_qa_video_projects WHERE id = :p"), {"p": ready}
        )
    assert after > before


# --- 讀成品 ---


def test_read_render(api, ready, rules_db, storage, tmp_path):
    job = _render(rules_db, storage, ready, tmp_path)
    response = api.get(f"{URL}/{ready}/render")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["job_id"] == str(job.id)
    assert data["total_seconds"] == job.result["total_seconds"]
    assert sorted(data["reencoded"]) == ["s1", "s2"] and data["reused"] == []
    assert data["estimated"] is True and data["finished_at"]
    # 段清單（看影片頁點一段跳到那個時間點）：段的順序、開始秒數、第一句字幕
    segments = data["segments"]
    assert [s["segment_key"] for s in segments] == ["s1", "s2"]
    assert 0 <= segments[0]["start_seconds"] < segments[1]["start_seconds"] < data["total_seconds"]
    assert segments[0]["title"] == "把打出的牌蓋著洗在一起，然後同時翻開。"
    video = api.get(f"{URL}/{ready}/render/video")
    assert video.status_code == 200
    assert video.headers["content-type"] == "video/mp4"
    assert video.content == storage.files[job.result["video_key"]]


def test_no_render_is_404(api, ready):
    response = api.get(f"{URL}/{ready}/render")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_RENDER_NOT_FOUND"
    response = api.get(f"{URL}/{ready}/render/video")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_RENDER_NOT_FOUND"


# --- 步驟 ---


def test_steps(api, as_shop_staff, rules_db, storage, game, tmp_path):
    project = insert_project(rules_db, game)
    step = lambda: api.get(f"{URL}/{project}").json()["step"]  # noqa: E731
    assert step() == "pages"
    set_pages(rules_db, project)
    _run_draft(rules_db, project)
    assert step() == "draft"  # 還沒拍任何照片
    _upload(api, project, "red")
    assert step() == "assets"
    _make_ready(api, project)
    assert step() == "render"
    _render(rules_db, storage, project, tmp_path)
    assert step() == "done"
    listed = api.get(URL).json()["items"]
    assert next(p for p in listed if p["id"] == str(project))["step"] == "done"


# --- 權限 ---


def test_other_shop_is_404(api, as_shop_staff, rules_db, game):
    other = insert_project(rules_db, game, OTHER_STAFF)
    for response in (
        api.post(f"{URL}/{other}/jobs", json={"kind": "render"}),
        api.get(f"{URL}/{other}/render"),
        api.get(f"{URL}/{other}/render/video"),
    ):
        assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_player_is_403(api, as_player, project):
    assert api.post(f"{URL}/{project}/jobs", json={"kind": "render"}).status_code == 403
    assert api.get(f"{URL}/{project}/render").status_code == 403
    assert api.get(f"{URL}/{project}/render/video").status_code == 403


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, project):
    from app.main import create_app

    client = TestClient(create_app(make_settings(database_url=test_db_url, auth_mode="jwt")))
    assert client.post(f"{URL}/{project}/jobs", json={"kind": "render"}).status_code == 401
    assert client.get(f"{URL}/{project}/render").status_code == 401


# --- 設定與註冊 ---


def test_render_handler_is_registered(make_settings, test_db_url):
    from app.main import create_app

    app = create_app(make_settings(database_url=test_db_url))
    assert isinstance(app.state.rules_video_job_handlers["render"], RenderJobHandler)


def test_work_dir_setting(make_settings, tmp_path):
    default = make_settings().rules_video_work_dir
    assert Path(default).parts[-3:] == ("backend", ".local", "rules_videos")
    assert make_settings(rules_video_work_dir=str(tmp_path)).rules_video_work_dir == str(tmp_path)


# --- 選拍略過 ---


def test_skip_optional_asset(api, as_shop_staff, rules_db, project):
    # blue 只是 s1 三張牌之一，略過後 s1 還有紅牌
    _make_optional(rules_db, project, "blue")
    detail = api.get(f"{URL}/{project}/assets/blue").json()
    assert detail["skipped"] is False
    assert detail["skip_affected_segments"] == [1] and detail["skip_blocked_segments"] == []
    response = api.patch(f"{URL}/{project}/assets/blue", json={"skipped": True})
    assert response.status_code == 200, response.text
    assert response.json()["skipped"] is True
    readiness = api.get(f"{URL}/{project}/readiness").json()
    assert "blue" not in {m["asset_key"] for m in readiness["missing_photos"]}
    # 取消略過
    api.patch(f"{URL}/{project}/assets/blue", json={"skipped": False})
    readiness = api.get(f"{URL}/{project}/readiness").json()
    assert "blue" in {m["asset_key"] for m in readiness["missing_photos"]}


def test_cannot_skip_when_segment_relies_on_it(api, as_shop_staff, rules_db, project):
    # red 是 s2 主畫面唯一的圖
    _make_optional(rules_db, project, "red")
    detail = api.get(f"{URL}/{project}/assets/red").json()
    assert detail["skip_blocked_segments"] == [2]
    response = api.patch(f"{URL}/{project}/assets/red", json={"skipped": True})
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_SKIP_BLOCKED"
    assert response.json()["error"]["message"] == "第 2 段只靠這張，不能略過"
    assert response.json()["error"]["details"] == {"segments": [2]}
    missing = api.get(f"{URL}/{project}/readiness").json()["missing_photos"]
    red = next(m for m in missing if m["asset_key"] == "red")
    assert red["skip_blocked_segments"] == [2]


def test_cannot_skip_must_asset(api, as_shop_staff, project):
    response = api.patch(f"{URL}/{project}/assets/blue", json={"skipped": True})
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_SKIP_NOT_OPTIONAL"


def test_render_after_skip(api, as_shop_staff, rules_db, storage, project, tmp_path):
    # 略過 blue（s1 的一張牌）與 board（s1 的側欄，含 highlight、move 的目的地）後仍能輸出
    _make_optional(rules_db, project, "blue", "board")
    for key in ("blue", "board"):
        assert api.patch(f"{URL}/{project}/assets/{key}", json={"skipped": True}).status_code == 200
    for key in ("back", "red"):
        _upload(api, project, key)
    assert api.get(f"{URL}/{project}/readiness").json()["ready"] is True
    assert api.post(f"{URL}/{project}/jobs", json={"kind": "render"}).status_code == 202
    with rules_db.begin() as conn:
        conn.execute(text("DELETE FROM rules_qa_video_jobs WHERE kind = 'render'"))
    job = _render(rules_db, storage, project, tmp_path)
    assert job.status == "succeeded", job.error
    assert sorted(job.result["skipped_assets"]) == ["blue", "board"]
    rendered = load_video(tmp_path / "work" / str(project))
    assert set(rendered.assets) == {"back", "red"}
    # 資料庫的草稿不改
    assert {a["asset_key"] for a in project_row(rules_db, project).video["assets"]} == set(ASSETS)


def test_strip_skipped_removes_references(rules_db, project):
    from app.domains.rules_qa.video_assets import strip_skipped

    video = project_row(rules_db, project).video
    # 每張牌的牌背都是 back：略過 back 後 s1 的主畫面沒有牌了
    result = strip_skipped(video, {"back"})
    assert result.blocked == [1] and result.affected == [1]
    # 略過 blue：拿掉 c2，以及指向 main.c2 的 label 與 hide
    result = strip_skipped(video, {"blue"})
    s1 = result.video["segments"][0]
    assert [i["item_key"] for i in s1["slots"]["main"]["items"]] == ["c1", "c3"]
    assert s1.get("labels", []) == []
    targets = [c["target"] for b in s1["beats"] for c in b.get("cues", [])]
    assert "main.c2" not in targets
    assert "blue" not in {a["asset_key"] for a in result.video["assets"]}
    # 原本的段資料不變
    assert len(video["segments"][0]["slots"]["main"]["items"]) == 3


# --- 整本範圍：店員看到的錯誤不含內部代號 ---


def test_bad_video_data_message_hides_internal_codes(api, ready, rules_db, storage, tmp_path):
    from app.domains.rules_qa.video_render import RENDER_DATA_MESSAGE

    video = project_row(rules_db, ready).video
    video["segments"][0]["highlights"][0]["target"] = "sidebar@no_such_zone"
    _set_video(rules_db, ready, video)
    job = _render(rules_db, storage, ready, tmp_path)
    assert job.status == "failed"
    assert job.error == RENDER_DATA_MESSAGE
    assert "h1" not in job.error and "s1" not in job.error
    assert "no_such_zone" in job.error_detail
