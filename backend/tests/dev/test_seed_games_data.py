"""開發用 seed 會寫入共用桌遊資料與推薦 Agent 的資料（docs/adr/0004-seed-data-in-repo.md）。

跑一次 seed，games、game_genres 與 4 張 games_advisor_ 表就和 repo 的資料檔
（app/dev/seed_data/）一致。桌遊步驟自成一個交易：失敗時整個退回、結束碼非 0，
但測試帳號、測試店家、教學影片照常完成。

錯誤情境用 tmp_path 裡自己編的小型假資料，不使用心得原文。
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text

from tests.db_utils import BACKEND_DIR
from tests.dev.conftest import RunSeed
from tests.dev.support import (
    ADVISOR_FILE,
    GAMES_FILE,
    GAMES_STEP_TABLES,
    fake_game,
    fake_tag_sql,
    fingerprints,
    next_game_id,
    other_domain_tables,
    table_counts,
    write_seed_data,
)

# repo 的資料檔寫入後，7 張表各有幾筆（genres 的 8 筆由 migration 寫入）
SEEDED_COUNTS = {
    "games": 16,
    "game_genres": 21,
    "genres": 8,
    "games_advisor_tags": 30,
    "games_advisor_game_tags": 114,
    "games_advisor_review_summaries": 16,
    "games_advisor_review_excerpts": 128,
}
SEEDED_NEXT_GAME_ID = 17
NOTHING_SEEDED = {**dict.fromkeys(SEEDED_COUNTS, 0), "genres": 8}

LESSON_VIDEO_COUNT = 3

REPO_GAMES_FILE = BACKEND_DIR / "app" / "dev" / "seed_data" / GAMES_FILE


def games_state(engine: Engine) -> dict[str, object]:
    """桌遊步驟那 6 張表的內容雜湊與 games.id 計數器，用來確認「桌遊與推薦資料都不變」。"""
    return {**fingerprints(engine, GAMES_STEP_TABLES), "next_id": next_game_id(engine)}


def account_counts(engine: Engine) -> dict[str, int]:
    return table_counts(engine, ("auth_users", "booking_shops"))


def remove_accounts(engine: Engine) -> None:
    """清掉測試帳號與測試店家，之後才看得出 seed 有沒有把它們建回來。"""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE auth_users, booking_shops CASCADE"))


def add_extra_game(engine: Engine) -> int:
    """組員自己在本機新增的桌遊（資料檔裡沒有），由資料庫自動給號；回傳 id。"""
    with engine.begin() as conn:
        return conn.scalar(
            text(
                "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
                "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
                "VALUES (999001, '本機自己加的桌遊', 'Local Only Game', 2, 4, 30, 60, 10, 2.0, "
                "'{}', '{}') RETURNING id"
            )
        )


# --- 正常情況 ---


def test_fresh_database_gets_games_and_advisor_data(db: Engine, run_seed: RunSeed) -> None:
    result = run_seed()

    assert result.returncode == 0, result.stderr
    assert table_counts(db, tuple(SEEDED_COUNTS)) == SEEDED_COUNTS
    assert next_game_id(db) == SEEDED_NEXT_GAME_ID
    # 既有步驟照舊：3 個測試帳號、1 間測試店家
    assert account_counts(db) == {"auth_users": 3, "booking_shops": 1}
    # 桌遊在教學影片之前寫入，同一次執行就登記完成，不會再印「找不到…略過」
    assert table_counts(db, ("rules_qa_videos",)) == {"rules_qa_videos": LESSON_VIDEO_COUNT}
    assert "找不到" not in result.stdout


def test_seeded_games_keep_the_ids_from_the_data_file(db: Engine, run_seed: RunSeed) -> None:
    assert run_seed().returncode == 0

    with db.connect() as conn:
        rows = conn.execute(text("SELECT id, bgg_id FROM games WHERE id <= 4 ORDER BY id")).all()
    # 1–4 號固定是 4 款 Demo 遊戲（ADR 0003）
    assert [tuple(row) for row in rows] == [(1, 400566), (2, 144734), (3, 171623), (4, 128882)]


def test_second_run_changes_nothing(db: Engine, run_seed: RunSeed) -> None:
    assert run_seed().returncode == 0
    counts = table_counts(db, tuple(SEEDED_COUNTS))
    # game_genres 的 id 每次同步都重新產生，所以只比桌遊與類型的對應
    advisor_tables = tuple(table for table in GAMES_STEP_TABLES if table != "game_genres")
    before = fingerprints(db, advisor_tables)

    result = run_seed()

    assert result.returncode == 0, result.stderr
    assert table_counts(db, tuple(SEEDED_COUNTS)) == counts == SEEDED_COUNTS
    assert fingerprints(db, advisor_tables) == before
    assert next_game_id(db) == SEEDED_NEXT_GAME_ID
    assert account_counts(db) == {"auth_users": 3, "booking_shops": 1}
    assert table_counts(db, ("rules_qa_videos",)) == {"rules_qa_videos": LESSON_VIDEO_COUNT}


def test_data_dir_option_reads_another_folder(
    db: Engine, run_seed: RunSeed, tmp_path: Path
) -> None:
    data_dir = write_seed_data(
        tmp_path / "data",
        games=[fake_game(1, 900001, "假桌遊甲"), fake_game(2, 900002, "假桌遊乙")],
        advisor_sql=fake_tag_sql(),
    )

    result = run_seed(data_dir=data_dir)

    assert result.returncode == 0, result.stderr
    assert table_counts(db, ("games", "game_genres", "games_advisor_tags")) == {
        "games": 2,
        "game_genres": 2,
        "games_advisor_tags": 1,
    }
    assert next_game_id(db) == 3


# --- 本機多了一款被其他資料用到的桌遊 ---


def test_extra_game_in_use_stops_games_step_only(db: Engine, run_seed: RunSeed) -> None:
    assert run_seed().returncode == 0
    extra_id = add_extra_game(db)
    with db.begin() as conn:
        # 其他 domain 的資料用到這款：參照 games.id，桌遊刪掉時不跟著刪（ADR 0003）
        conn.execute(
            text(
                "INSERT INTO rules_qa_videos (game_id, source, video_url, youtube_id, title) "
                "VALUES (:id, 'youtube', 'https://youtu.be/abcdefghijk', 'abcdefghijk', '自己的')"
            ),
            {"id": extra_id},
        )
    remove_accounts(db)
    before = games_state(db)

    result = run_seed()

    assert result.returncode != 0
    # 說明誰在用
    assert "本機自己加的桌遊" in result.stderr
    assert "rules_qa_videos" in result.stderr
    # 桌遊與推薦資料都不變，多的那款與用到它的資料也還在
    assert games_state(db) == before
    assert table_counts(db, ("games", "rules_qa_videos")) == {
        "games": 17,
        "rules_qa_videos": LESSON_VIDEO_COUNT + 1,
    }
    # 帳號等既有步驟仍完成
    assert account_counts(db) == {"auth_users": 3, "booking_shops": 1}
    assert "測試帳號" in result.stdout


# --- 資料檔損壞或缺少 ---


def _renamed_games() -> list[dict[str, Any]]:
    """repo 資料檔的 16 款，只把 16 號改名：同步會成功並改到資料，之後失敗時要一起退回。"""
    games = json.loads(REPO_GAMES_FILE.read_text(encoding="utf-8"))["games"]
    return [{**game, "name": "改過名字的桌遊"} if game["id"] == 16 else game for game in games]


def _broken_games_file(folder: Path) -> Path:
    return write_seed_data(folder, games_text="{ 這不是 JSON", advisor_sql=fake_tag_sql())


def _missing_games_file(folder: Path) -> Path:
    return write_seed_data(folder, advisor_sql=fake_tag_sql())


def _games_file_with_wrong_content(folder: Path) -> Path:
    games = [{**fake_game(1, 900001, "假桌遊甲"), "min_players": 9}]
    return write_seed_data(folder, games=games, advisor_sql=fake_tag_sql())


def _broken_advisor_file(folder: Path) -> Path:
    # 桌遊檔是好的：同步桌遊成功之後才失敗，也要連同步一起退回
    return write_seed_data(folder, games=_renamed_games(), advisor_sql="INSERT INTO 寫到一半")


def _missing_advisor_file(folder: Path) -> Path:
    return write_seed_data(folder, games=_renamed_games())


def _advisor_file_for_unknown_game(folder: Path) -> Path:
    sql = (
        "INSERT INTO public.games_advisor_game_tags (id, game_id, tag_id, confidence) VALUES "
        "('00000000-0000-4000-8000-000000000002', 999, "
        "'00000000-0000-4000-8000-000000000001', 0.5);\n"
    )
    return write_seed_data(folder, games=_renamed_games(), advisor_sql=fake_tag_sql() + sql)


@pytest.mark.parametrize(
    ("make_data_dir", "file_name"),
    [
        # 桌遊檔不是合法的 JSON
        pytest.param(_broken_games_file, GAMES_FILE, id="games-file-not-json"),
        # 缺少桌遊檔
        pytest.param(_missing_games_file, GAMES_FILE, id="games-file-missing"),
        # 桌遊檔的欄位不合規定
        pytest.param(_games_file_with_wrong_content, GAMES_FILE, id="games-file-invalid-game"),
        # 推薦資料檔的 SQL 壞掉
        pytest.param(_broken_advisor_file, ADVISOR_FILE, id="advisor-file-broken-sql"),
        # 缺少推薦資料檔
        pytest.param(_missing_advisor_file, ADVISOR_FILE, id="advisor-file-missing"),
        # 推薦資料指到桌遊檔沒有的桌遊
        pytest.param(_advisor_file_for_unknown_game, ADVISOR_FILE, id="advisor-file-unknown-game"),
    ],
)
def test_bad_data_file_stops_games_step_only(
    make_data_dir, file_name: str, db: Engine, run_seed: RunSeed, tmp_path: Path
) -> None:
    assert run_seed().returncode == 0
    remove_accounts(db)
    before = games_state(db)

    result = run_seed(data_dir=make_data_dir(tmp_path / "data"))

    assert result.returncode != 0
    # 說明哪個檔有問題
    assert file_name in result.stderr
    # 桌遊與推薦資料都不變：仍是第一次 seed 寫入的 16 款
    assert games_state(db) == before
    assert table_counts(db, tuple(SEEDED_COUNTS)) == SEEDED_COUNTS
    # 帳號等既有步驟仍完成
    assert account_counts(db) == {"auth_users": 3, "booking_shops": 1}
    assert table_counts(db, ("rules_qa_videos",)) == {"rules_qa_videos": LESSON_VIDEO_COUNT}
    assert "測試帳號" in result.stdout


def test_bad_data_file_on_fresh_database_still_creates_accounts(
    db: Engine, run_seed: RunSeed, tmp_path: Path
) -> None:
    result = run_seed(data_dir=_broken_advisor_file(tmp_path / "data"))

    assert result.returncode != 0
    assert table_counts(db, tuple(SEEDED_COUNTS)) == NOTHING_SEEDED
    assert account_counts(db) == {"auth_users": 3, "booking_shops": 1}
    # 桌遊沒寫入，教學影片「找不到就略過」的保護照舊
    assert "找不到" in result.stdout


# --- 資料庫已有其他 domain 的資料 ---


def test_other_domain_data_is_untouched(db: Engine, run_seed: RunSeed) -> None:
    assert run_seed().returncode == 0
    with db.begin() as conn:
        # 一筆揪團指定了 1 號桌遊；開團主與店家用 seed 建立的測試玩家、測試店家
        group_id = conn.scalar(
            text(
                "INSERT INTO groups (shop_id, organizer_id, title, start_at, end_at, capacity) "
                "SELECT s.id, u.id, '週末一起玩', '2026-12-05T06:00:00Z', "
                "'2026-12-05T09:00:00Z', 4 "
                "FROM booking_shops s, auth_users u WHERE u.role = 'player' RETURNING id"
            )
        )
        conn.execute(
            text("INSERT INTO group_games (group_id, game_id, position) VALUES (:g, 1, 1)"),
            {"g": group_id},
        )
        # 規則書頁面也指到 2 號桌遊
        conn.execute(
            text("INSERT INTO games_manual (games_id, page, content) VALUES (2, 1, '假的頁面')")
        )
    others = other_domain_tables(db)
    assert {"groups", "group_games", "games_manual", "rules_qa_videos", "auth_users"} <= set(others)
    before = fingerprints(db, others)

    result = run_seed()

    assert result.returncode == 0, result.stderr
    assert fingerprints(db, others) == before
    assert table_counts(db, tuple(SEEDED_COUNTS)) == SEEDED_COUNTS


# --- AUTH_MODE=jwt ---


def test_jwt_mode_writes_no_games_data(db: Engine, run_seed: RunSeed) -> None:
    result = run_seed("jwt")

    assert result.returncode != 0
    assert "AUTH_MODE" in result.stderr
    assert table_counts(db, tuple(SEEDED_COUNTS)) == NOTHING_SEEDED
    assert account_counts(db) == {"auth_users": 0, "booking_shops": 0}
