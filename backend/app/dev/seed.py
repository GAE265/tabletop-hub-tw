"""開發用 seed：建立固定 UUID 的測試帳號。可重複執行；AUTH_MODE 不是 dev 時拒絕執行。

帳號已經存在時不改動，只在電話是空的時候補上假電話（舊資料庫重跑一次就能訂位）。
另外替 Demo 遊戲登記規則教學影片（清單在 lesson_videos.py）：已經有影片的遊戲不覆蓋，
資料庫裡沒有的遊戲印出提示並略過。

也會寫入共用桌遊資料與推薦 Agent 的資料（games_data.py，資料檔在 seed_data/）。這一步排在
最前面，教學影片才找得到遊戲；它自成一個交易，失敗時只有它退回、結束碼是 1，帳號、店家與
教學影片照常處理。

執行方式：uv run python -m app.dev.seed
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import create_db_engine
from app.core.games.models import Game
from app.dev.accounts import TEST_SHOP_ID, TEST_SHOP_NAME, get_test_accounts
from app.dev.games_data import DEFAULT_DATA_DIR, GamesDataFailed, seed_games_data
from app.dev.lesson_videos import LESSON_VIDEOS, LessonVideo
from app.domains.auth.models import AuthUser
from app.domains.booking.models import BookingShop
from app.domains.rules_qa.models import RulesQaVideo


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()
    if settings.auth_mode != "dev":
        print("拒絕執行：seed 只能在 AUTH_MODE=dev 時使用。", file=sys.stderr)
        return 1

    # 桌遊要在教學影片之前寫入；失敗不影響後面的步驟，最後才回報結束碼
    games_ok = _seed_games_data(settings.database_url, args.data_dir)

    engine = create_db_engine(settings.database_url)
    with Session(engine) as session, session.begin():
        session.execute(
            insert(BookingShop)
            .values(id=TEST_SHOP_ID, name=TEST_SHOP_NAME)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        for account in get_test_accounts(settings):
            statement = insert(AuthUser).values(
                id=account.id,
                display_name=account.display_name,
                role=account.role,
                shop_id=account.shop_id,
                phone=account.phone,
            )
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["id"],
                    set_={"phone": func.coalesce(AuthUser.phone, statement.excluded.phone)},
                )
            )
        missing = _seed_lesson_videos(session)
    engine.dispose()
    print("已建立（或確認存在）3 個測試帳號與 1 間測試店家。")
    print(f"已登記（或確認存在）{len(LESSON_VIDEOS) - len(missing)} 支規則教學影片。")
    for video in missing:
        print(
            f"找不到《{video.game_name}》（bgg_id {video.bgg_id}），略過它的教學影片；"
            "請先同步桌遊資料再重跑 seed。"
        )
    return 0 if games_ok else 1


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.dev.seed", description="開發用 seed")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        metavar="<資料夾>",
        help="桌遊與推薦資料檔所在的資料夾；不用給，預設是 repo 的 app/dev/seed_data（測試用）",
    )
    return parser.parse_args(argv)


def _seed_games_data(database_url: str, data_dir: Path) -> bool:
    """寫入共用桌遊資料與推薦 Agent 的資料；回傳有沒有成功。失敗時印出原因，資料維持原狀。"""
    try:
        result = seed_games_data(database_url, data_dir)
    except GamesDataFailed as exc:
        print(
            "桌遊與推薦 Agent 的資料沒有寫入，這幾張表維持原狀；"
            "測試帳號、測試店家與教學影片照常處理。原因：",
            file=sys.stderr,
        )
        for reason in exc.reasons:
            print(f"  {reason}", file=sys.stderr)
        return False
    print(
        f"已寫入（或確認一致）{result.games} 款桌遊與推薦 Agent 的資料 {result.advisor_rows} 筆，"
        f"下一個桌遊編號是 {result.next_id}。"
    )
    return True


def _seed_lesson_videos(session: Session) -> list[LessonVideo]:
    """替 Demo 遊戲登記教學影片；已經有影片的遊戲不覆蓋。回傳找不到的遊戲。"""
    missing = []
    for video in LESSON_VIDEOS:
        game_id = session.scalar(select(Game.id).where(Game.bgg_id == video.bgg_id))
        if game_id is None:
            missing.append(video)
            continue
        session.execute(
            insert(RulesQaVideo)
            .values(
                game_id=game_id,
                source="youtube",
                video_url=video.video_url,
                youtube_id=video.youtube_id,
                title=video.title,
            )
            .on_conflict_do_nothing(index_elements=["game_id"])
        )
    return missing


if __name__ == "__main__":
    sys.exit(main())
