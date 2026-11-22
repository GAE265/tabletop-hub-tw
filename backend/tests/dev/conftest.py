"""tests/dev 共用的 fixture：seed 會寫入桌遊與推薦 Agent 的資料，這裡負責隔離與清理。

seed 會讓 games、game_genres 與 4 張 games_advisor_ 表和資料檔一致（資料檔沒有的桌遊會被刪），
所以這個資料夾的測試改用自己的資料庫，不和其他 domain 的測試共用 `_test`；每個測試結束後
再把 seed 寫入的資料清掉，測試之間互不影響。
"""

import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.config import Settings
from tests.db_utils import BACKEND_DIR, recreate_database, run_migrations

RunSeed = Callable[..., subprocess.CompletedProcess[str]]

# genres 是 migration 寫入的固定資料，不清；games.id 的計數器從 1 重新開始。
# 這個資料庫只有 tests/dev 使用，CASCADE 清掉的都是這個資料夾的測試自己放的資料
_CLEAN = "TRUNCATE games, games_advisor_tags RESTART IDENTITY CASCADE"


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """覆寫根目錄的 test_db_url：tests/dev 用自己的 `_test_dev` 資料庫。"""
    url = recreate_database(Settings().database_url, "test_dev")
    run_migrations(url)
    return url


@pytest.fixture
def run_seed(test_db_url: str) -> Iterator[RunSeed]:
    """覆寫根目錄的 run_seed：多一個 data_dir 參數，測試前後清掉桌遊與推薦資料。

    沒給 data_dir 時執行的指令和根目錄的 run_seed 相同（讀 repo 的資料檔）。
    """

    def _run(
        auth_mode: str = "dev", data_dir: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "DATABASE_URL": test_db_url,
            "AUTH_MODE": auth_mode,
            "PYTHONUTF8": "1",
        }
        command = [sys.executable, "-m", "app.dev.seed"]
        if data_dir is not None:
            command += ["--data-dir", str(data_dir)]
        return subprocess.run(
            command,
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    engine = create_engine(test_db_url)
    with engine.begin() as conn:
        conn.execute(text(_CLEAN))
    yield _run
    with engine.begin() as conn:
        conn.execute(text(_CLEAN))
    engine.dispose()
