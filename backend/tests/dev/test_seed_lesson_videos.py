"""開發用 seed 會替 Demo 遊戲登記組內自製的規則教學影片（YouTube）。

遊戲依 bgg_id 尋找（games 唯一不重複的欄位，見 docs/adr/0003-shared-games-table.md）。
測試自己寫入只有必填欄位的假遊戲，結束後刪除，不動其他測試的資料。

seed 現在也會寫入共用桌遊資料（docs/adr/0005-seed-data-in-repo.md）：假遊戲用和資料檔相同的
編號，seed 才會把它們當成同一款、原地更新，掛在上面的影片不受影響。
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from sqlalchemy import Engine, text

from tests.dev.support import fake_game, fake_tag_sql, write_seed_data

# bgg_id → 預期的 YouTube 影片 ID
EXPECTED = {
    400566: "XE-Sw_FtFFs",  # 血與刃的白薔薇
    144734: "5nIdNY056Gw",  # 阿不思學院
    171623: "F5abxTqoEH8",  # 馬可波羅
}

# bgg_id → 這款遊戲在 seed 資料檔（app/dev/seed_data/games-export.json）裡的編號
SEED_GAME_IDS = {400566: 1, 144734: 2, 171623: 3}


def _cleanup(engine: Engine) -> None:
    with engine.begin() as conn:
        params = {"ids": list(EXPECTED)}
        conn.execute(
            text(
                "DELETE FROM rules_qa_videos WHERE game_id IN "
                "(SELECT id FROM games WHERE bgg_id = ANY(:ids))"
            ),
            params,
        )
        conn.execute(text("DELETE FROM games WHERE bgg_id = ANY(:ids)"), params)


@pytest.fixture
def add_games(db: Engine) -> Iterator[Callable[..., dict[int, int]]]:
    """寫入指定 bgg_id 的假遊戲，回傳 {bgg_id: games.id}。"""
    _cleanup(db)

    def _add(*bgg_ids: int) -> dict[int, int]:
        ids = {}
        with db.begin() as conn:
            for bgg_id in bgg_ids:
                ids[bgg_id] = conn.scalar(
                    text(
                        "INSERT INTO games (id, bgg_id, name, english_name, min_players, "
                        "max_players, min_playtime, max_playtime, min_age, weight, "
                        "categories, mechanics) VALUES (:id, :bgg, :name, :name, 2, 4, 30, 60, "
                        "10, 2.0, '{}', '{}') RETURNING id"
                    ),
                    {"id": SEED_GAME_IDS[bgg_id], "bgg": bgg_id, "name": f"假遊戲 {bgg_id}"},
                )
        return ids

    yield _add
    _cleanup(db)


def videos(engine: Engine) -> dict[int, tuple[str, str | None, str, str]]:
    """回傳 {bgg_id: (source, youtube_id, video_url, title)}。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT g.bgg_id, v.source, v.youtube_id, v.video_url, v.title "
                "FROM rules_qa_videos v JOIN games g ON g.id = v.game_id "
                "WHERE g.bgg_id = ANY(:ids)"
            ),
            {"ids": list(EXPECTED)},
        ).all()
    return {bgg: (source, yid, url, title) for bgg, source, yid, url, title in rows}


def test_registers_videos_for_demo_games(
    add_games: Callable[..., dict[int, int]],
    db: Engine,
    run_seed: Callable[..., CompletedProcess[str]],
) -> None:
    add_games(*EXPECTED)
    result = run_seed()
    assert result.returncode == 0, result.stderr
    found = videos(db)
    assert set(found) == set(EXPECTED)
    for bgg_id, (source, youtube_id, video_url, title) in found.items():
        assert source == "youtube"
        assert youtube_id == EXPECTED[bgg_id]
        assert EXPECTED[bgg_id] in video_url
        assert title


def test_keeps_existing_video(
    add_games: Callable[..., dict[int, int]],
    db: Engine,
    run_seed: Callable[..., CompletedProcess[str]],
) -> None:
    ids = add_games(*EXPECTED)
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO rules_qa_videos (game_id, source, video_url, youtube_id, title) "
                "VALUES (:id, 'youtube', :url, 'abcdefghijk', '店家自己的影片')"
            ),
            {"id": ids[144734], "url": "https://youtu.be/abcdefghijk"},
        )
    assert run_seed().returncode == 0
    found = videos(db)
    assert found[144734][1:] == ("abcdefghijk", "https://youtu.be/abcdefghijk", "店家自己的影片")
    assert found[400566][1] == EXPECTED[400566]


def test_rerun_keeps_one_video_per_game(
    add_games: Callable[..., dict[int, int]],
    db: Engine,
    run_seed: Callable[..., CompletedProcess[str]],
) -> None:
    add_games(*EXPECTED)
    assert run_seed().returncode == 0
    second = run_seed()
    assert second.returncode == 0, second.stderr
    assert len(videos(db)) == 3


def test_missing_game_is_skipped_with_notice(
    add_games: Callable[..., dict[int, int]],
    db: Engine,
    run_seed: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    add_games(400566, 144734)
    # repo 的資料檔有馬可波羅（171623），seed 會自己寫入；改用只有這 2 款的測試用資料檔
    data_dir = write_seed_data(
        tmp_path / "data",
        games=[fake_game(1, 400566, "假遊戲 400566"), fake_game(2, 144734, "假遊戲 144734")],
        advisor_sql=fake_tag_sql(),
    )
    result = run_seed(data_dir=data_dir)
    assert result.returncode == 0, result.stderr
    assert set(videos(db)) == {400566, 144734}
    assert "171623" in result.stdout
    assert "找不到" in result.stdout


def test_jwt_mode_registers_no_video(
    add_games: Callable[..., dict[int, int]],
    db: Engine,
    run_seed: Callable[..., CompletedProcess[str]],
) -> None:
    add_games(*EXPECTED)
    assert run_seed("jwt").returncode != 0
    assert videos(db) == {}
