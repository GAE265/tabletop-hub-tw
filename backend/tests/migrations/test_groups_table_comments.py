"""0009：替 groups、group_members 補上資料表與欄位的中文說明（AGENTS.md 4.4，1.10 版新增的規則）。

只改說明，不改結構；group_games 在 0007 建立時已經有說明。
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, inspect

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_groups_tables import migrate

TABLES = ("groups", "group_members")


def comments(engine: Engine, table: str) -> tuple[str | None, dict[str, str | None]]:
    inspector = inspect(engine)
    table_comment = inspector.get_table_comment(table)["text"]
    return table_comment, {c["name"]: c.get("comment") for c in inspector.get_columns(table)}


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    url = recreate_database(Settings().database_url, "groups_table_comments")
    migrate(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.mark.parametrize("table", TABLES)
def test_table_and_every_column_have_chinese_comment(engine: Engine, table: str) -> None:
    table_comment, columns = comments(engine, table)
    assert table_comment
    missing = [name for name, comment in columns.items() if not comment]
    assert missing == []


def test_status_comments_explain_every_value(engine: Engine) -> None:
    """Enum 的每個值都要說明代表什麼（AGENTS.md 4.4）。"""
    _, groups = comments(engine, "groups")
    _, members = comments(engine, "group_members")
    for value in ("open", "cancelled"):
        assert value in groups["status"]
    for value in ("member", "waitlisted"):
        assert value in members["status"]


def test_downgrade_removes_comments_and_upgrade_restores_them() -> None:
    url = recreate_database(Settings().database_url, "groups_table_comments_downgrade")
    migrate(url)
    migrate(url, "downgrade", "0008")
    engine = create_engine(url)
    try:
        for table in TABLES:
            table_comment, columns = comments(engine, table)
            assert table_comment is None
            assert all(c is None for c in columns.values())
        migrate(url)
        for table in TABLES:
            table_comment, columns = comments(engine, table)
            assert table_comment
            assert all(columns.values())
    finally:
        engine.dispose()
