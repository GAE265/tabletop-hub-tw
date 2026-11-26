"""0023：rules_qa_video_jobs 加上 input（add-rules-video-mobile MR 11，用一句話修改）。

修改的工作要知道店員的修改要求與指定段；草稿、產生影片的工作不需要輸入，維持空值。
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_matches_tables import migrate

TABLE = "rules_qa_video_jobs"


@pytest.fixture
def url() -> str:
    return recreate_database(Settings().database_url, "rules_qa_video_job_input")


@pytest.fixture
def engine(url: str) -> Iterator[Engine]:
    engine = create_engine(url)
    yield engine
    engine.dispose()


def _column(engine: Engine) -> tuple[str, str, str | None] | None:
    sql = text(
        "SELECT c.data_type, c.is_nullable, "
        f"col_description('{TABLE}'::regclass, c.ordinal_position) "
        "FROM information_schema.columns c "
        f"WHERE c.table_name = '{TABLE}' AND c.column_name = 'input'"
    )
    with engine.connect() as conn:
        row = conn.execute(sql).one_or_none()
    return None if row is None else (row[0], row[1], row[2])


def test_upgrade_adds_nullable_jsonb_input_with_comment(url, engine):
    migrate(url, "upgrade", "0023")
    column = _column(engine)
    assert column is not None
    data_type, nullable, comment = column
    assert (data_type, nullable) == ("jsonb", "YES")
    assert comment and "修改要求" in comment and "空值" in comment


def test_downgrade_removes_input(url, engine):
    migrate(url, "upgrade", "0023")
    migrate(url, "downgrade", "0022")
    assert _column(engine) is None
