"""games_advisor 的批次指令（spec §7）。在本機手動執行，沒有登入者。

執行方式：uv run python -m app.domains.games_advisor.commands <子指令> <參數>

角色和 router 相同：只解析參數、讀寫檔案、呼叫 service、印出結果。

結束碼：0 全部完成；1 沒有完成（拒絕執行或參數不對，什麼都沒寫）。
"""

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import create_db_engine
from app.domains.games_advisor import service
from app.domains.games_advisor.repository import GameRepository
from app.domains.games_advisor.service import Refused

EXIT_OK = 0
EXIT_FAILED = 1


class _UsageError(Exception):
    """參數不對。"""


class _ArgumentParser(argparse.ArgumentParser):
    """參數不對時不直接結束程式：argparse 預設的結束碼 2 在 spec §7.2 代表「部分完成」。"""

    def error(self, message: str) -> NoReturn:
        raise _UsageError(f"{self.format_usage()}{self.prog}: error: {message}")


def _bgg_ids(value: str) -> list[int]:
    try:
        return [int(part) for part in value.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(
            "要是用逗號分開的 bgg_id，例如 900001,900002,900003,900004"
        ) from None


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise Refused(f"讀不到檔案 {path}：{exc.strerror}") from exc
    except ValueError as exc:
        raise Refused(f"{path} 不是合法的 JSON：{exc}") from exc


def _import_games(args: argparse.Namespace, repository: GameRepository) -> None:
    result = service.import_games(repository, _read_json(args.games_json), args.first_four)
    print(f"已匯入 {result.count} 款桌遊。")
    for game_id, name in result.first_four:
        print(f"  {game_id} 號：{name}")
    print("記得執行 export-games，把匯出檔放進 GAE265G5。")


def _export_games(args: argparse.Namespace, repository: GameRepository) -> None:
    export = service.export_games(repository)
    content = json.dumps(export.to_json(), ensure_ascii=False, indent=2)
    args.out.write_text(content + "\n", encoding="utf-8")
    print(f"已匯出 {len(export.games)} 款桌遊到 {args.out}，next_id 是 {export.next_id}。")
    print("把匯出檔放進 GAE265G5，覆蓋舊的那份。")


def _sync_games(args: argparse.Namespace, repository: GameRepository) -> None:
    result = service.sync_games(repository, _read_json(args.export_json))
    print(
        f"同步完成：新增 {result.added} 款、更新 {result.updated} 款、"
        f"刪除 {result.deleted} 款，next_id 是 {result.next_id}。"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="python -m app.domains.games_advisor.commands",
        description="games_advisor 的批次指令",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="<子指令>")

    import_games = commands.add_parser(
        "import-games", help="匯入桌遊：只有立倫在空的資料庫執行一次"
    )
    import_games.add_argument("games_json", type=Path, metavar="<games.json>")
    import_games.add_argument(
        "--first-four",
        type=_bgg_ids,
        required=True,
        metavar="<4 個 bgg_id>",
        help="1–4 號的 4 款桌遊，用逗號分開，照順序給號",
    )
    import_games.set_defaults(handler=_import_games)

    export_games = commands.add_parser("export-games", help="匯出共用桌遊資料：只有立倫執行")
    export_games.add_argument("--out", type=Path, required=True, metavar="<匯出檔>")
    export_games.set_defaults(handler=_export_games)

    sync_games = commands.add_parser(
        "sync-games", help="同步共用桌遊資料：照匯出檔改寫自己的資料庫"
    )
    sync_games.add_argument("export_json", type=Path, metavar="<匯出檔>")
    sync_games.set_defaults(handler=_sync_games)

    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except _UsageError as exc:
        print(exc, file=sys.stderr)
        return EXIT_FAILED

    engine = create_db_engine(get_settings().database_url)
    try:
        with Session(engine) as session:
            args.handler(args, GameRepository(session))
    except Refused as exc:
        for reason in exc.reasons:
            print(reason, file=sys.stderr)
        return EXIT_FAILED
    finally:
        engine.dispose()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
