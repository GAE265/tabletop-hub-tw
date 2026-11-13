"""標籤的兩個指令經過 main() 與真的資料庫的行為（spec §7.2 規則 3）。

連測試用的 PostgreSQL；LLM 是 fake。
"""

from pathlib import Path

from sqlalchemy import Engine

from tests.games_advisor.conftest import RunCommand
from tests.games_advisor.support import (
    make_game,
    make_review,
    make_tag,
    read_game_tags,
    seed_game,
    seed_game_tag,
    seed_tag,
    write_json,
    write_reviews_file,
)


def test_draft_tags_refuses_fake_llm(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_game(games_db, make_game(1))
    seed_tag(games_db, make_tag("laughter"))
    reviews = write_reviews_file(tmp_path, [make_review(1, 1)])
    out_path = tmp_path / "tags-draft.json"

    result = run_command("draft-tags", str(reviews), "--out", str(out_path))

    assert result.code == 1
    assert "需要真的模型，請設定 LLM_*" in result.err
    assert not out_path.exists()
    assert not (tmp_path / "tags-draft.original.json").exists()
    assert read_game_tags(games_db) == []


def test_import_tags_runs_with_fake_llm(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    for number in (1, 2):
        seed_game(games_db, make_game(number))
    for code in ("laughter", "luck", "tense"):
        seed_tag(games_db, make_tag(code))
    seed_game_tag(games_db, 1, "tense", confidence=0.9)
    seed_game_tag(games_db, 2, "tense", confidence=0.9)
    url = make_review(1, 1)["source_url"]
    # 草稿只有第 1 款：第 2 款的標籤不動
    draft = {
        "games": [
            {
                "bgg_id": 900001,
                "name": make_game(1)["name"],
                "tags": [
                    {"code": "laughter", "confidence": 0.8, "source_urls": [url]},
                    {"code": "luck", "confidence": 0.3, "source_urls": [url]},
                ],
            }
        ]
    }
    write_json(tmp_path / "tags-draft.original.json", draft)
    draft_path = write_json(tmp_path / "tags-draft.json", draft)

    result = run_command("import-tags", str(draft_path))

    assert result.code == 0, result.err
    assert read_game_tags(games_db) == [
        (1, "laughter", 0.8),
        (1, "luck", 0.3),
        (2, "tense", 0.9),
    ]
    assert "1 款" in result.out
