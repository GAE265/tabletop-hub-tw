"""開發用 seed 的桌遊步驟：寫入共用桌遊資料與推薦 Agent 的資料。

資料檔放在 seed_data/（來源與重新產生的方法見 seed_data/README.md、
docs/adr/0004-seed-data-in-repo.md）：

- games-export.json：共用桌遊資料（games、game_genres 與 games.id 的計數器），export-games 的輸出。
- games_advisor_data.sql：推薦 Agent 自己的 4 張表（標籤、每款桌遊的標籤、心得摘要、心得片段），
  只有 INSERT。

只寫這 6 張表，不動其他 domain 的資料表。整個步驟是一個交易：先用 sync-games 背後的 service
同步共用桌遊資料，再清空推薦 Agent 的 4 張表、執行 SQL 檔；任何一步失敗就全部退回。
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import create_db_engine
from app.core.games.repository import GameRepository
from app.domains.games_advisor import service
from app.domains.games_advisor.service import Refused, SyncResult

DEFAULT_DATA_DIR = Path(__file__).parent / "seed_data"
GAMES_FILE = "games-export.json"
ADVISOR_FILE = "games_advisor_data.sql"

# 推薦 Agent 自己的 4 張表，只有 games_advisor 會寫入。一次清空、不加 CASCADE：
# 之後如果有其他資料表用外鍵指到它們，資料庫會擋下，不會連別人的資料一起清掉
_TRUNCATE_ADVISOR_TABLES = (
    "TRUNCATE TABLE games_advisor_game_tags, games_advisor_review_excerpts, "
    "games_advisor_review_summaries, games_advisor_tags"
)
_COUNT_ADVISOR_ROWS = (
    "SELECT (SELECT count(*) FROM games_advisor_tags) "
    "+ (SELECT count(*) FROM games_advisor_game_tags) "
    "+ (SELECT count(*) FROM games_advisor_review_summaries) "
    "+ (SELECT count(*) FROM games_advisor_review_excerpts)"
)


class GamesDataFailed(Exception):
    """桌遊步驟沒有完成，資料庫已經退回原狀。reasons 是要印給執行的人看的原因，一行一個。"""

    def __init__(self, *reasons: str) -> None:
        super().__init__("\n".join(reasons))
        self.reasons = list(reasons)


@dataclass(frozen=True)
class GamesDataResult:
    games: int
    next_id: int
    advisor_rows: int


def seed_games_data(database_url: str, data_dir: Path = DEFAULT_DATA_DIR) -> GamesDataResult:
    """讓 games、game_genres 與推薦 Agent 的 4 張表和 data_dir 的資料檔一致。

    失敗時拋 GamesDataFailed，這 6 張表維持原狀。
    """
    games_path = data_dir / GAMES_FILE
    advisor_path = data_dir / ADVISOR_FILE
    # 兩個檔都先讀進來：缺檔或讀不到時還沒有動資料庫
    try:
        export = service.read_json(games_path)
    except Refused as exc:
        raise GamesDataFailed(*exc.reasons) from exc
    advisor_sql = _read_sql(advisor_path)

    # 用自己的 engine：SQL 檔若帶有連線層級的設定，不會留給 seed 的其他步驟
    engine = create_db_engine(database_url)
    try:
        # 一個交易：區塊正常結束才提交，拋出例外就全部退回
        with engine.begin() as connection:
            synced = _sync_games(connection, export, games_path)
            _replace_advisor_data(connection, advisor_sql, advisor_path)
            advisor_rows = connection.scalar(text(_COUNT_ADVISOR_ROWS)) or 0
    except SQLAlchemyError as exc:
        raise GamesDataFailed(f"寫入資料庫失敗：{_short(exc)}") from exc
    finally:
        engine.dispose()
    return GamesDataResult(
        games=synced.added + synced.updated, next_id=synced.next_id, advisor_rows=advisor_rows
    )


def _sync_games(connection: Connection, export: object, games_path: Path) -> SyncResult:
    """呼叫 sync-games 背後的 service，規則完全相同（ADR 0003）。"""
    # sync_games 會自己提交。讓 session 加入外層的交易，它的提交只是放掉儲存點；
    # 真正的提交與退回由外層決定，桌遊與推薦資料才會一起成功或一起退回
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        try:
            return service.sync_games(GameRepository(session), export)
        except Refused as exc:
            raise GamesDataFailed(*(f"{games_path}：{reason}" for reason in exc.reasons)) from exc


def _replace_advisor_data(connection: Connection, advisor_sql: str, advisor_path: Path) -> None:
    connection.execute(text(_TRUNCATE_ADVISOR_TABLES))
    try:
        # no_parameters：整份 SQL 原樣送出，心得原文裡的 % 不會被當成參數
        connection.execution_options(no_parameters=True).exec_driver_sql(advisor_sql)
    except SQLAlchemyError as exc:
        raise GamesDataFailed(f"{advisor_path} 執行失敗：{_short(exc)}") from exc


def _read_sql(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GamesDataFailed(f"讀不到檔案 {path}：{exc.strerror}") from exc
    except UnicodeDecodeError as exc:
        raise GamesDataFailed(f"{path} 不是 UTF-8 文字檔：{exc.reason}") from exc


def _short(exc: SQLAlchemyError) -> str:
    """資料庫錯誤的原因。不印 SQLAlchemy 附上的整句 SQL：推薦資料檔有好幾 MB。"""
    cause = exc.orig if isinstance(exc, DBAPIError) and exc.orig is not None else exc
    return str(cause).strip()
