"""詞彙表的兩個指令經過 main() 與真的資料庫的行為（spec §7.2、§8.6）。

連測試用的 PostgreSQL；LLM 是 fake。
"""

from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.domains.games_advisor import service
from tests.games_advisor.conftest import RunCommand
from tests.games_advisor.support import (
    make_game,
    make_review,
    make_tag,
    read_game_tags,
    read_tags,
    seed_game,
    seed_game_tag,
    seed_tag,
    vocabulary_data,
    write_reviews_file,
    write_vocabulary_file,
)


def test_draft_vocabulary_refuses_fake_llm(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_game(games_db, make_game(1))
    reviews = write_reviews_file(tmp_path, [make_review(1, 1)])
    out_path, report_path = tmp_path / "draft.json", tmp_path / "report.md"

    result = run_command(
        "draft-vocabulary", str(reviews), "--out", str(out_path), "--report", str(report_path)
    )

    assert result.code == 1
    assert "需要真的模型，請設定 LLM_*" in result.err
    assert not out_path.exists()
    assert not report_path.exists()


def test_sync_vocabulary_runs_with_fake_llm(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    tags = [make_tag("laughter"), make_tag("scheming"), make_tag("luck")]

    result = run_command("sync-vocabulary", str(write_vocabulary_file(tmp_path, *tags)))

    assert result.code == 0, result.err
    assert read_tags(games_db) == sorted(tags, key=lambda tag: tag["code"])
    # 有新增的標籤：提醒重跑上標籤
    assert "重跑上標籤" in result.out


def test_sync_vocabulary_refuses_file_that_is_not_valid_json(
    games_db: Engine, run_command: RunCommand, tmp_path: Path
) -> None:
    seed_tag(games_db, make_tag("laughter"))
    path = tmp_path / "tag_vocabulary.json"
    path.write_text('{"tags": [', encoding="utf-8")

    result = run_command("sync-vocabulary", str(path))

    assert result.code == 1
    assert "JSON" in result.err
    assert "usage" not in result.err
    assert read_tags(games_db) == [make_tag("laughter")]


def test_failure_midway_rolls_back_the_whole_sync(games_db: Engine, session: Session) -> None:
    from app.domains.games_advisor.repository import TagRepository

    class FakeFailingTagRepository(TagRepository):
        """真的 TagRepository，但第 2 次寫入時失敗：模擬同步到一半資料庫出錯。"""

        writes = 0

        def _count(self) -> None:
            self.writes += 1
            if self.writes == 2:
                raise RuntimeError("寫入失敗")

        def add_tag(self, code: str, name: str, definition: str) -> None:
            self._count()
            super().add_tag(code, name, definition)

        def update_tag(self, code: str, name: str, definition: str) -> None:
            self._count()
            super().update_tag(code, name, definition)

        def delete_tag(self, code: str) -> list:
            self._count()
            return super().delete_tag(code)

    seed_game(games_db, make_game(1))
    seed_tag(games_db, make_tag("laughter"))
    seed_tag(games_db, make_tag("scheming"))
    seed_game_tag(games_db, 1, "scheming", confidence=0.6)
    before = (read_tags(games_db), read_game_tags(games_db))
    # 這份檔案要做 3 次寫入：刪掉 scheming、更新 laughter、新增 luck
    data = vocabulary_data(make_tag("laughter", definition="新的定義"), make_tag("luck"))

    with pytest.raises(RuntimeError, match="寫入失敗"):
        service.sync_vocabulary(FakeFailingTagRepository(session), data)

    assert (read_tags(games_db), read_game_tags(games_db)) == before
