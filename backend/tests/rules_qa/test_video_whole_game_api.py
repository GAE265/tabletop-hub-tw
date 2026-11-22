"""整個遊戲一支影片：建立專案、自動產生草稿、分類三格、分格涵蓋檢查、錯誤訊息
（add-rules-video-mobile 整本範圍）。

連 `_test` 資料庫；LLM 用 FakeLLMProvider（不需要金鑰）；工作用 JobRunner.run_once() 執行。
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.domains.rules_qa.video_draft import DraftJobHandler
from app.domains.rules_qa.video_jobs import JobRunner
from app.integrations.llm.fake import FakeLLMProvider
from tests.rules_qa.video_script_support import coverage_output
from tests.rules_qa.video_support import seed_people
from tests.rules_qa.whole_game_support import (
    VARIANT_QUOTE,
    WHOLE_GAME_PAGES,
    classify_output,
    slot_coverage,
    whole_game_llm_outputs,
    whole_game_output,
)

URL = "/api/v1/rules-videos"


@pytest.fixture
def api(app: FastAPI, rules_db: Engine) -> TestClient:
    seed_people(rules_db)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def game(api, add_game, add_pages) -> int:
    game = add_game("假遊戲")
    add_pages(game, WHOLE_GAME_PAGES)
    return game


def _code(response) -> str:
    return response.json()["error"]["code"]


def _create(api, game) -> dict:
    response = api.post(URL, json={"game_id": game})
    assert response.status_code == 201, response.text
    return response.json()


def _run(rules_db: Engine, outputs) -> FakeLLMProvider:
    llm = FakeLLMProvider(json_outputs=outputs)
    assert JobRunner(sessionmaker(rules_db), {"draft": DraftJobHandler(llm)}).run_once()
    return llm


def _job(rules_db: Engine, project: str):
    with rules_db.connect() as conn:
        return conn.execute(
            text(
                "SELECT status, error, error_detail, result FROM rules_qa_video_jobs "
                "WHERE project_id = :p ORDER BY created_at DESC LIMIT 1"
            ),
            {"p": project},
        ).one()


def _classification(rules_db: Engine, project: str):
    with rules_db.connect() as conn:
        return conn.scalar(
            text("SELECT classification FROM rules_qa_video_projects WHERE id = :p"),
            {"p": project},
        )


# --- 建立：只選遊戲 ---


def test_create_with_game_only(api, as_shop_staff, game):
    data = _create(api, game)
    assert data["chapter_number"] is None and data["chapter_title"] is None
    assert data["title"] == "假遊戲 規則教學"
    assert data["step"] == "draft"  # 頁面文字那一步不在店員流程裡
    pages = api.get(f"{URL}/{data['id']}/pages").json()
    assert pages["chapter_pages"] == [1, 2, 3, 4]  # 這支影片用到的頁：預設全選
    assert pages["reference_pages"] == []


def test_create_starts_draft_job(api, as_shop_staff, game):
    data = _create(api, game)
    jobs = api.get(f"{URL}/{data['id']}/jobs").json()["items"]
    assert [(j["kind"], j["status"]) for j in jobs] == [("draft", "queued")]


def test_game_without_rulebook_is_422(api, as_shop_staff, add_game):
    bare = add_game("沒有規則書的遊戲")
    response = api.post(URL, json={"game_id": bare})
    assert response.status_code == 422 and _code(response) == "RULES_VIDEO_NO_RULEBOOK"
    assert "管理員" in response.json()["error"]["message"]
    assert api.get(URL).json()["total"] == 0  # 沒有建立專案


def test_only_one_chapter_field_is_422(api, as_shop_staff, game):
    # 單章模式要兩個都給；整本模式兩個都不給
    assert api.post(URL, json={"game_id": game, "chapter_number": 1}).status_code == 422
    assert api.post(URL, json={"game_id": game, "chapter_title": "步驟三"}).status_code == 422


def test_chapter_mode_still_works(api, as_shop_staff, game):
    # 既有的單章專案（命令列與舊資料）照舊：不自動產生草稿
    response = api.post(
        URL, json={"game_id": game, "chapter_number": 11, "chapter_title": "步驟三"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["step"] == "pages" and data["title"] == "步驟三"
    assert api.get(f"{URL}/{data['id']}/jobs").json()["total"] == 0


def test_list_shows_whole_game_title(api, as_shop_staff, game):
    _create(api, game)
    item = api.get(URL).json()["items"][0]
    assert item["title"] == "假遊戲 規則教學" and item["chapter_number"] is None


def test_player_cannot_create(api, as_player, game):
    assert api.post(URL, json={"game_id": game}).status_code == 403


# --- 草稿工作（整本） ---


def test_draft_job_classifies_and_generates(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    llm = _run(rules_db, whole_game_llm_outputs())
    job = _job(rules_db, project)
    assert job.status == "succeeded", job.error
    # 依序：分類 → 三格各產生一次（2026-11-22 永傑決定）→ 三格各一個涵蓋檢查
    assert [c.kwargs["schema"].name for c in llm.calls] == [
        "rules_video_scope",
        "rules_video_whole_game",
        "rules_video_whole_game",
        "rules_video_whole_game",
        "rules_video_coverage",
        "rules_video_coverage",
        "rules_video_coverage",
    ]
    assert job.result["scope"] == {"setup": 1, "round": 2, "win": 1, "excluded": 1}
    draft = api.get(f"{URL}/{project}/draft").json()
    assert [s["segment_key"] for s in draft["segments"]] == ["s_setup", "s1", "s2", "s_win"]
    assert [s["chapter"] for s in draft["segments"]] == ["setup", "round", "round", "win"]
    assert {a["asset_key"]: a["label"] for a in draft["assets"]}["board"] == "盤面"
    assert api.get(f"{URL}/{project}").json()["step"] == "draft"


def test_excluded_list_is_stored_but_not_shown(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    _run(rules_db, whole_game_llm_outputs())
    stored = _classification(rules_db, project)
    assert stored["excluded"][0]["text"] == VARIANT_QUOTE and stored["excluded"][0]["reason"]
    assert [s["key"] for s in stored["slots"]] == ["setup", "round", "win"]
    # 店員看得到的 API 都沒有排除清單與排除原因（/pages 本來就回傳整頁原文，所以比對原因與欄位）
    reason = stored["excluded"][0]["reason"]
    for path in ("", "/draft", "/pages"):
        body = api.get(f"{URL}/{project}{path}").text
        assert reason not in body and "excluded" not in body
    assert VARIANT_QUOTE not in api.get(f"{URL}/{project}/draft").text


def test_coverage_summary_by_slot(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    coverage = [
        slot_coverage("R1"),
        slot_coverage("R1", status="missing", missing="洗牌"),
        slot_coverage("R1", status="incomplete", missing="抽完"),
    ]
    _run(rules_db, whole_game_llm_outputs(coverage=coverage))
    summary = api.get(f"{URL}/{project}/draft").json()["coverage"]
    assert summary["status"] == "done"
    assert [(s["slot"], s["title"], len(s["issues"])) for s in summary["slots"]] == [
        ("setup", "開局", 0),
        ("round", "走完一輪", 1),
        ("win", "獲勝方式", 1),
    ]
    # 合計也照舊提供；同名的規則依格分開
    assert len(summary["issues"]) == 2
    assert {i["rule_id"] for i in summary["issues"]} == {"round-R1", "win-R1"}


def test_coverage_of_one_slot_not_done_keeps_draft(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    coverage = [slot_coverage(), coverage_output([]), slot_coverage()]  # 走完一輪沒拆出規則
    _run(rules_db, whole_game_llm_outputs(coverage=coverage))
    assert _job(rules_db, project).status == "succeeded"
    summary = api.get(f"{URL}/{project}/draft").json()["coverage"]
    slots = {s["slot"]: s for s in summary["slots"]}
    assert slots["round"]["status"] == "not_done" and slots["round"]["reason"]
    assert slots["setup"]["status"] == "done"
    assert summary["status"] == "not_done"


def test_empty_slot_fails_job(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    # 第 3 頁放進了排除清單（每一頁都有去處），獲勝方式的片段又對不上原文：那一格空了
    output = classify_output(
        win=[{"page": 3, "quote": "Nobody ever wins this game."}],
        excluded=[
            {"page": 3, "quote": "The game ends when the deck is empty.", "reason": "r"},
            {"page": 4, "quote": "Advanced players may add the Knight expansion.", "reason": "r"},
        ],
    )
    _run(rules_db, [output])
    job = _job(rules_db, project)
    assert job.status == "failed"
    assert (
        job.error
        == "規則書裡找不到「獲勝方式」的內容，無法產生影片；請管理員確認規則書是否完整匯入"
    )
    assert "Nobody ever wins" in job.error_detail  # 沒採用的片段給開發者看


def test_rejected_script_hides_internal_codes(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    bad = whole_game_output()
    bad["segments"][0]["beats"][0]["narration"] = "每人只有一次機會。"
    _run(rules_db, [classify_output(), bad, bad])
    job = _job(rules_db, project)
    assert job.status == "failed"
    assert job.error == "AI 產生的草稿沒有通過檢查，請再產生一次；若一直失敗，請通知管理員"
    assert "請檢查規則書" not in job.error
    assert "s_win" not in job.error and "s_win" in job.error_detail
    assert "次" in job.error_detail


def test_regenerate_keeps_photos_and_regions(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    _run(rules_db, whole_game_llm_outputs())
    files = {"file": ("board.png", _png(), "image/png")}
    assert api.put(f"{URL}/{project}/assets/board/photo", files=files).status_code == 200
    body = {"regions": {"zone_a": [0.1, 0.1, 0.4, 0.4]}}
    assert api.patch(f"{URL}/{project}/assets/board", json=body).status_code == 200
    assert api.post(f"{URL}/{project}/jobs", json={"kind": "draft"}).status_code == 202
    _run(rules_db, whole_game_llm_outputs())
    board = api.get(f"{URL}/{project}/assets/board").json()
    assert board["has_photo"] is True
    assert board["regions"] == {"zone_a": [0.1, 0.1, 0.4, 0.4]}


def _png() -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 10)).save(out, "PNG")
    return out.getvalue()


# --- 素材頁的錯誤要指出是哪一個素材 ---


def test_asset_errors_name_the_asset(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    _run(rules_db, whole_game_llm_outputs())
    files = {"file": ("x.gif", b"GIF89a not really", "image/gif")}
    response = api.put(f"{URL}/{project}/assets/board/photo", files=files)
    assert response.status_code == 422
    message = response.json()["error"]["message"]
    assert "「盤面」" in message and "JPEG" in message
    response = api.patch(f"{URL}/{project}/assets/board", json={"regions": {"nope": None}})
    assert response.status_code == 422
    assert "「盤面」" in response.json()["error"]["message"]
    response = api.patch(f"{URL}/{project}/assets/board", json={"skipped": True})
    assert "「盤面」" in response.json()["error"]["message"]


def test_unknown_asset_message_has_no_internal_key(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    _run(rules_db, whole_game_llm_outputs())
    response = api.put(
        f"{URL}/{project}/assets/no_such_key/photo", files={"file": ("a.png", _png(), "image/png")}
    )
    assert response.status_code == 404
    assert "no_such_key" not in response.json()["error"]["message"]


def test_project_id_is_uuid(api, as_shop_staff, game):
    assert uuid.UUID(_create(api, game)["id"])


# --- 分類的完整性、已標的區域 ---


def test_page_without_place_fails_job(api, as_shop_staff, rules_db, game):
    project = _create(api, game)["id"]
    missing_page_4 = classify_output(excluded=[])
    _run(rules_db, [missing_page_4, missing_page_4])
    job = _job(rules_db, project)
    assert job.status == "failed"
    assert job.error == (
        "規則書第 4 頁沒有分到開局、走完一輪、獲勝方式，也不在不講的清單裡，無法產生影片；"
        "請再產生一次，若一直發生請通知管理員"
    )
    assert "4" in job.error_detail


def test_draft_lists_marked_regions(api, as_shop_staff, rules_db, game):
    # 重新產生前，手機頁要知道哪些區域已經標好（重新產生後可能要重標）
    project = _create(api, game)["id"]
    _run(rules_db, whole_game_llm_outputs())
    board = {a["asset_key"]: a for a in api.get(f"{URL}/{project}/draft").json()["assets"]}["board"]
    assert board["marked_regions"] == []
    body = {"regions": {"zone_a": [0.1, 0.1, 0.4, 0.4]}}
    assert api.patch(f"{URL}/{project}/assets/board", json=body).status_code == 200
    board = {a["asset_key"]: a for a in api.get(f"{URL}/{project}/draft").json()["assets"]}["board"]
    assert board["marked_regions"] == ["zone_a"]


def test_draft_assets_show_skippable(api, as_shop_staff, rules_db, game):
    # 草稿摘要的「可略過」由程式判斷：blue 只是一排牌的其中一張；red、back、board 有段只靠它
    project = _create(api, game)["id"]
    _run(rules_db, whole_game_llm_outputs())
    assets = {a["asset_key"]: a for a in api.get(f"{URL}/{project}/draft").json()["assets"]}
    assert {key for key, a in assets.items() if a["skippable"]} == {"blue"}
