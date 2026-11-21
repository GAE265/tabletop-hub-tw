"""規則影片專案與工作的測試共用資料（add-rules-video-mobile）。"""

import uuid

from sqlalchemy import Engine, text

from app.core.auth import CurrentUser
from tests.conftest import TEST_ADMIN, TEST_PLAYER, TEST_SHOP_ID, TEST_SHOP_STAFF

OTHER_SHOP_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
OTHER_STAFF = CurrentUser(
    id=uuid.UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"), role="shop_staff", shop_id=OTHER_SHOP_ID
)


def seed_people(engine: Engine) -> None:
    """兩間店；conftest 的三種測試身分，加上別家店的店員。"""
    with engine.begin() as conn:
        for shop, name in ((TEST_SHOP_ID, "測試店"), (OTHER_SHOP_ID, "別家店")):
            conn.execute(
                text("INSERT INTO booking_shops (id, name) VALUES (:i, :n)"), {"i": shop, "n": name}
            )
        for user, name in (
            (TEST_PLAYER, "玩家"),
            (TEST_SHOP_STAFF, "店員"),
            (TEST_ADMIN, "管理員"),
            (OTHER_STAFF, "別家店員"),
        ):
            conn.execute(
                text(
                    "INSERT INTO auth_users (id, display_name, role, shop_id) "
                    "VALUES (:i, :n, :r, :s)"
                ),
                {"i": user.id, "n": name, "r": user.role, "s": user.shop_id},
            )


def insert_project(engine: Engine, game: int, user: CurrentUser = TEST_SHOP_STAFF) -> uuid.UUID:
    with engine.begin() as conn:
        return conn.scalar(
            text(
                "INSERT INTO rules_qa_video_projects "
                "(game_id, shop_id, created_by, chapter_number, chapter_title) "
                "VALUES (:g, :s, :u, 11, '步驟三') RETURNING id"
            ),
            {"g": game, "s": user.shop_id, "u": user.id},
        )


def insert_job(
    engine: Engine,
    project: uuid.UUID,
    *,
    status: str = "queued",
    kind: str = "draft",
    started_minutes_ago: int | None = None,
) -> uuid.UUID:
    """直接寫入一個工作；started_minutes_ago 給定時，started_at 設成那麼多分鐘前。"""
    with engine.begin() as conn:
        return conn.scalar(
            text(
                "INSERT INTO rules_qa_video_jobs "
                "(project_id, kind, status, created_by, started_at) VALUES (:p, :k, :s, :u, "
                "CASE WHEN CAST(:m AS integer) IS NULL THEN NULL "
                "ELSE now() - make_interval(mins => CAST(:m AS integer)) END) RETURNING id"
            ),
            {
                "p": project,
                "k": kind,
                "s": status,
                "u": TEST_SHOP_STAFF.id,
                "m": started_minutes_ago,
            },
        )


def job_row(engine: Engine, job: uuid.UUID):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM rules_qa_video_jobs WHERE id = :i"), {"i": job}
        ).one()
