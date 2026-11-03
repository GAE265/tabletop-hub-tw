"""測試用的資料庫輔助函式：建立獨立的測試資料庫、執行 Alembic migration。"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]


def recreate_database(base_url: str, suffix: str) -> str:
    """以 `<原資料庫名>_<suffix>` 重建一個空資料庫，回傳它的連線字串。"""
    base = make_url(base_url)
    target = base.set(database=f"{base.database}_{suffix}")
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()
    return target.render_as_string(hide_password=False)


def run_migrations(url: str, action: str = "upgrade", revision: str = "head") -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    getattr(command, action)(config, revision)
