"""0016：rules_qa_video_jobs（add-rules-video-mobile MR 2，design.md D2）。"""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from tests.db_utils import recreate_database
from tests.migrations.test_matches_tables import migrate

TABLE = "rules_qa_video_jobs"


@pytest.fixture(scope="module")
def url() -> str:
    url = recreate_database(Settings().database_url, "rules_qa_video_jobs")
    migrate(url, "upgrade", "0016")
    return url


@pytest.fixture
def engine(url: str) -> Iterator[Engine]:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE games, auth_users, booking_shops RESTART IDENTITY CASCADE"))
    yield engine
    engine.dispose()


def seed(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    game = conn.scalar(
        text(
            "INSERT INTO games (bgg_id, name, english_name, min_players, max_players, "
            "min_playtime, max_playtime, min_age, weight, categories, mechanics) "
            "VALUES (1, '假遊戲', 'Fake', 2, 4, 30, 60, 10, 2.0, '{}', '{}') RETURNING id"
        )
    )
    shop = conn.scalar(text("INSERT INTO booking_shops (name) VALUES ('店') RETURNING id"))
    user = conn.scalar(
        text(
            "INSERT INTO auth_users (display_name, role, shop_id) "
            "VALUES ('店員', 'shop_staff', :s) RETURNING id"
        ),
        {"s": shop},
    )
    project = conn.scalar(
        text(
            "INSERT INTO rules_qa_video_projects "
            "(game_id, shop_id, created_by, chapter_number, chapter_title) "
            "VALUES (:g, :s, :u, 11, '步驟三') RETURNING id"
        ),
        {"g": game, "s": shop, "u": user},
    )
    return project, user


def insert_job(
    conn: Connection,
    project: uuid.UUID,
    user: uuid.UUID,
    *,
    status: str = "queued",
    kind: str = "draft",
    progress: float = 0,
) -> uuid.UUID:
    return conn.scalar(
        text(
            f"INSERT INTO {TABLE} (project_id, kind, status, progress, created_by) "
            "VALUES (:p, :k, :s, :g, :u) RETURNING id"
        ),
        {"p": project, "k": kind, "s": status, "g": progress, "u": user},
    )


def test_table_and_columns_have_chinese_comments(engine: Engine):
    inspector = inspect(engine)
    assert inspector.get_table_comment(TABLE)["text"]
    columns = {c["name"]: c for c in inspector.get_columns(TABLE)}
    assert set(columns) == {
        "id",
        "project_id",
        "kind",
        "status",
        "progress",
        "message",
        "error",
        "error_detail",
        "result",
        "created_by",
        "created_at",
        "started_at",
        "finished_at",
    }
    for column in columns.values():
        assert column["comment"], column["name"]
    # kind、status 的每個值都有中文註解（AGENTS.md 4.4）
    for value in ("draft", "render", "revise"):
        assert value in columns["kind"]["comment"]
    for value in ("queued", "running", "succeeded", "failed"):
        assert value in columns["status"]["comment"]
    for name in ("message", "error", "error_detail", "result", "started_at", "finished_at"):
        assert columns[name]["nullable"], name
        assert "空值" in columns[name]["comment"], name


def test_insert_defaults(engine: Engine):
    with engine.begin() as conn:
        project, user = seed(conn)
        job = insert_job(conn, project, user)
        row = conn.execute(text(f"SELECT * FROM {TABLE} WHERE id = :i"), {"i": job}).one()
    assert row.status == "queued" and row.progress == 0
    assert row.created_at is not None and row.started_at is None and row.finished_at is None


@pytest.mark.parametrize(
    "change",
    [{"kind": "publish"}, {"status": "paused"}, {"progress": -0.1}, {"progress": 1.1}],
    ids=["unknown_kind", "unknown_status", "progress_below_0", "progress_above_1"],
)
def test_invalid_values_are_rejected(engine: Engine, change: dict[str, object]):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        project, user = seed(conn)
        insert_job(conn, project, user, **change)  # type: ignore[arg-type]


@pytest.mark.parametrize("kind", ["draft", "render", "revise"])
def test_all_kinds_are_accepted(engine: Engine, kind: str):
    with engine.begin() as conn:
        project, user = seed(conn)
        insert_job(conn, project, user, kind=kind)


@pytest.mark.parametrize(
    "first, second", [("queued", "queued"), ("queued", "running"), ("running", "running")]
)
def test_only_one_active_job_per_project(engine: Engine, first: str, second: str):
    with pytest.raises(IntegrityError), engine.begin() as conn:
        project, user = seed(conn)
        insert_job(conn, project, user, status=first)
        insert_job(conn, project, user, status=second)


def test_finished_jobs_do_not_block(engine: Engine):
    with engine.begin() as conn:
        project, user = seed(conn)
        for status in ("succeeded", "succeeded", "failed", "failed", "queued"):
            insert_job(conn, project, user, status=status)
        assert conn.scalar(text(f"SELECT count(*) FROM {TABLE}")) == 5


def test_downgrade_removes_table(url: str):
    try:
        migrate(url, "downgrade", "0015")
        engine = create_engine(url)
        try:
            assert TABLE not in inspect(engine).get_table_names()
        finally:
            engine.dispose()
    finally:
        migrate(url, "upgrade", "0016")
