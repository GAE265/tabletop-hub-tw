"""刪除影片專案：DELETE /api/v1/rules-videos/{project_id}（2026-11-24 永傑決定）。

- 權限沿用其他操作：同店的店員與管理員都可以刪；別家店 404（不透露專案存在）；玩家 403。
- 有進行中（queued、running）的工作時 409，什麼都不刪；running 超過逾時上限的視為卡住，可以刪。
- 先在一個交易裡刪資料庫（工作紀錄與專案），再刪存放空間的 `rules_videos/<專案>/` 與工作資料夾。
  刪檔案失敗只記 log，仍回 204：資料庫已經沒有這個專案，不會留下指向不存在檔案的資料。

連 `_test` 資料庫；存放空間用 FakeFileStorage，工作資料夾放在 tmp_path。
"""

import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.auth import CurrentUser, get_current_user
from app.integrations.llm.fake import FakeLLMProvider
from app.integrations.storage import StorageUnavailable
from app.integrations.storage.fake import FakeFileStorage
from app.main import create_app
from tests.conftest import TEST_ADMIN, TEST_SHOP_ID, TEST_SHOP_STAFF
from tests.rules_qa.video_support import (
    OTHER_STAFF,
    insert_job,
    insert_project,
    seed_people,
)

URL = "/api/v1/rules-videos"

# 同一家店、但不是建立者的店員
SAME_SHOP_STAFF = CurrentUser(
    id=uuid.UUID("abababab-abab-4bab-8bab-abababababab"), role="shop_staff", shop_id=TEST_SHOP_ID
)


class FakeDownFileStorage(FakeFileStorage):
    """刪除整個前綴時連不上（模擬雲端暫時無法使用）。"""

    def delete_prefix(self, prefix: str) -> int:
        raise StorageUnavailable("連不上存放空間（測試）")


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    return tmp_path / "work"


@pytest.fixture
def app(make_settings, test_db_url: str, rules_db: Engine, work_dir: Path) -> FastAPI:
    # 工作資料夾放在 tmp_path，不碰本機的 backend/.local/rules_videos
    application = create_app(
        make_settings(database_url=test_db_url, rules_video_work_dir=str(work_dir))
    )
    application.state.llm = FakeLLMProvider()
    return application


@pytest.fixture
def api(app: FastAPI, rules_db: Engine) -> TestClient:
    seed_people(rules_db)
    with rules_db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO auth_users (id, display_name, role, shop_id) "
                "VALUES (:i, '同店店員', 'shop_staff', :s)"
            ),
            {"i": SAME_SHOP_STAFF.id, "s": TEST_SHOP_ID},
        )
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def storage(app: FastAPI) -> FakeFileStorage:
    assert isinstance(app.state.storage, FakeFileStorage)
    return app.state.storage


@pytest.fixture
def game(add_game) -> int:
    return add_game("假遊戲")


def _as(app: FastAPI, user: CurrentUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _code(response) -> str:
    return response.json()["error"]["code"]


def _fill(storage: FakeFileStorage, work_dir: Path, project: uuid.UUID) -> list[str]:
    """一個用過一陣子的專案：素材照片（含換照片留下的舊檔）、規則書照片與清單、兩支成品、快取。"""
    keys = [
        f"rules_videos/{project}/assets/board-1a2b3c4d.jpg",
        f"rules_videos/{project}/assets/board-old00000.jpg",
        f"rules_videos/{project}/rulebook/aaaaaaaaaaaa.jpg",
        f"rules_videos/{project}/rulebook/manifest.json",
        f"rules_videos/{project}/renders/{uuid.uuid4()}.mp4",
        f"rules_videos/{project}/renders/{uuid.uuid4()}.mp4",
    ]
    for key in keys:
        storage.put(key, b"x", "application/octet-stream")
    cache = work_dir / str(project) / "cache"
    cache.mkdir(parents=True)
    (cache / "s1.mp4").write_bytes(b"x")
    (work_dir / str(project) / "assets").mkdir()
    (work_dir / str(project) / "assets" / "board.jpg").write_bytes(b"x")
    return keys


def _counts(engine: Engine, project: uuid.UUID) -> tuple[int, int]:
    with engine.connect() as conn:
        projects = conn.scalar(
            text("SELECT count(*) FROM rules_qa_video_projects WHERE id = :p"), {"p": project}
        )
        jobs = conn.scalar(
            text("SELECT count(*) FROM rules_qa_video_jobs WHERE project_id = :p"), {"p": project}
        )
    return projects, jobs


def _files(storage: FakeFileStorage, project: uuid.UUID) -> list[str]:
    return [k for k in storage.files if k.startswith(f"rules_videos/{project}/")]


# --- 正常刪除 ---


def test_creator_deletes_everything(api, app, rules_db, storage, work_dir, game):
    _as(app, TEST_SHOP_STAFF)
    project = insert_project(rules_db, game)
    insert_job(rules_db, project, status="succeeded", kind="draft")
    insert_job(rules_db, project, status="failed", kind="render")
    _fill(storage, work_dir, project)
    # 同店另一個專案：不能被波及
    other = insert_project(rules_db, game)
    insert_job(rules_db, other, status="succeeded")
    other_keys = _fill(storage, work_dir, other)

    response = api.delete(f"{URL}/{project}")

    assert response.status_code == 204, response.text
    assert _counts(rules_db, project) == (0, 0)
    assert _files(storage, project) == []
    assert not (work_dir / str(project)).exists()
    assert _counts(rules_db, other) == (1, 1)
    assert all(key in storage.files for key in other_keys)
    assert (work_dir / str(other) / "cache" / "s1.mp4").exists()


def test_admin_can_delete_other_shop(api, app, rules_db, storage, work_dir, game):
    project = insert_project(rules_db, game, user=OTHER_STAFF)
    _fill(storage, work_dir, project)
    _as(app, TEST_ADMIN)
    assert api.delete(f"{URL}/{project}").status_code == 204
    assert _counts(rules_db, project) == (0, 0)
    assert _files(storage, project) == []


def test_files_already_gone_is_fine(api, app, rules_db, game):
    _as(app, TEST_SHOP_STAFF)
    project = insert_project(rules_db, game)
    assert api.delete(f"{URL}/{project}").status_code == 204
    assert _counts(rules_db, project) == (0, 0)


def test_storage_failure_still_deletes_database(api, app, rules_db, work_dir, game, caplog):
    # 刪檔案失敗：資料庫已經刪了，回 204；只記 log（不會留下指向不存在檔案的資料）
    app.state.storage = FakeDownFileStorage()
    _as(app, TEST_SHOP_STAFF)
    project = insert_project(rules_db, game)
    response = api.delete(f"{URL}/{project}")
    assert response.status_code == 204
    assert _counts(rules_db, project) == (0, 0)
    assert str(project) in caplog.text


def test_delete_twice_is_404(api, app, rules_db, game):
    _as(app, TEST_SHOP_STAFF)
    project = insert_project(rules_db, game)
    assert api.delete(f"{URL}/{project}").status_code == 204
    response = api.delete(f"{URL}/{project}")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_unknown_project_is_404(api, app):
    _as(app, TEST_SHOP_STAFF)
    response = api.delete(f"{URL}/{uuid.uuid4()}")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"


def test_deleted_project_is_gone_everywhere(api, app, rules_db, game):
    _as(app, TEST_SHOP_STAFF)
    project = insert_project(rules_db, game)
    assert api.delete(f"{URL}/{project}").status_code == 204
    assert api.get(f"{URL}/{project}").status_code == 404
    assert api.get(f"{URL}/{project}/draft").status_code == 404
    assert api.post(f"{URL}/{project}/jobs", json={"kind": "draft"}).status_code == 404
    assert api.get(f"{URL}").json()["items"] == []


# --- 進行中的工作 ---


@pytest.mark.parametrize(
    ("status", "kind", "minutes"),
    [("running", "draft", 5), ("queued", "render", None)],
    ids=["running-draft", "queued-render"],
)
def test_active_job_blocks_delete(
    api, app, rules_db, storage, work_dir, game, status, kind, minutes
):
    _as(app, TEST_SHOP_STAFF)
    project = insert_project(rules_db, game)
    insert_job(rules_db, project, status=status, kind=kind, started_minutes_ago=minutes)
    keys = _fill(storage, work_dir, project)
    response = api.delete(f"{URL}/{project}")
    assert response.status_code == 409 and _code(response) == "RULES_VIDEO_PROJECT_BUSY"
    assert _counts(rules_db, project) == (1, 1)
    assert all(key in storage.files for key in keys)
    assert (work_dir / str(project) / "cache" / "s1.mp4").exists()


def test_stuck_job_does_not_block_delete(api, app, rules_db, game):
    # running 超過逾時上限（30 分鐘）視為卡住，和建立新工作時的規則一樣
    _as(app, TEST_SHOP_STAFF)
    project = insert_project(rules_db, game)
    insert_job(rules_db, project, status="running", started_minutes_ago=31)
    assert api.delete(f"{URL}/{project}").status_code == 204
    assert _counts(rules_db, project) == (0, 0)


# --- 權限 ---


def test_same_shop_other_staff_can_delete(api, app, rules_db, storage, work_dir, game):
    # 權限沿用其他操作：同店的店員都可以，不限建立者（2026-11-24 永傑決定，最小版）
    project = insert_project(rules_db, game)  # 建立者是 TEST_SHOP_STAFF
    _fill(storage, work_dir, project)
    _as(app, SAME_SHOP_STAFF)
    assert api.delete(f"{URL}/{project}").status_code == 204
    assert _counts(rules_db, project) == (0, 0)
    assert _files(storage, project) == []


def test_other_shop_is_404(api, app, rules_db, game):
    project = insert_project(rules_db, game)
    _as(app, OTHER_STAFF)
    response = api.delete(f"{URL}/{project}")
    assert response.status_code == 404 and _code(response) == "RULES_VIDEO_PROJECT_NOT_FOUND"
    assert _counts(rules_db, project) == (1, 0)


def test_player_is_403(api, app, as_player, rules_db, game):
    project = insert_project(rules_db, game)
    assert api.delete(f"{URL}/{project}").status_code == 403
    assert _counts(rules_db, project) == (1, 0)


def test_unauthenticated_in_jwt_mode(test_db_url, make_settings, rules_db, game, tmp_path):
    seed_people(rules_db)  # 這個測試不用 api fixture，自己建人
    project = insert_project(rules_db, game)
    client = TestClient(
        create_app(
            make_settings(
                database_url=test_db_url, auth_mode="jwt", rules_video_work_dir=str(tmp_path)
            )
        )
    )
    assert client.delete(f"{URL}/{project}").status_code == 401
    assert _counts(rules_db, project) == (1, 0)
