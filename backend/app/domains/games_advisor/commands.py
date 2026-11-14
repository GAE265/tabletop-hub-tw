"""games_advisor 的批次指令（spec §7）。在本機手動執行，沒有登入者。

執行方式：uv run python -m app.domains.games_advisor.commands <子指令> <參數>

角色和 router 相同：只解析參數、讀寫檔案、建立 provider、呼叫 service、印出結果。

結束碼：0 全部完成；1 沒有完成（拒絕執行或參數不對，什麼都沒寫）；2 部分完成（有款被跳過）。
"""

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import create_db_engine
from app.core.games.repository import GameRepository
from app.domains.games_advisor import service
from app.domains.games_advisor.repository import ReviewRepository, TagRepository
from app.domains.games_advisor.service import BatchResult, Refused, SkippedGame
from app.integrations.embedding.base import EmbeddingProvider
from app.integrations.embedding.factory import EmbeddingConfig, get_embedding_provider
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.factory import get_llm_provider

EXIT_OK = 0
EXIT_FAILED = 1

# 批次指令一次讀完一款的全部心得，固定等 300 秒，不讀 LLM_TIMEOUT_SECONDS（spec §4.1）
BATCH_LLM_TIMEOUT_SECONDS = 300


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


# --- 建立 provider ---


def batch_llm_settings(settings: Settings) -> Settings:
    """批次指令用的 LLM 設定：複製一份 settings、換掉三個值（spec §7.2 規則 4）。

    模型用 LLM_BATCH_MODEL（沒填就用 LLM_MODEL）、推理強度用模型預設、逾時固定 300 秒。
    """
    return settings.model_copy(
        update={
            "llm_model": settings.llm_batch_model or settings.llm_model,
            "llm_reasoning_effort": None,
            "llm_timeout_seconds": BATCH_LLM_TIMEOUT_SECONDS,
        }
    )


def _batch_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        raise Refused("需要真的模型，請設定 LLM_*")
    try:
        return get_llm_provider(settings.llm_provider, batch_llm_settings(settings))
    except (ValueError, NotImplementedError) as exc:
        raise Refused(str(exc)) from exc


def _embedding(settings: Settings) -> tuple[EmbeddingProvider, EmbeddingConfig]:
    """games_advisor 自己的 embedding：只讀 GAMES_ADVISOR_EMBEDDING_*（spec §7.2 規則 5）。"""
    config = EmbeddingConfig(
        provider=settings.games_advisor_embedding_provider,
        dim=settings.games_advisor_embedding_dim,
        endpoint=settings.games_advisor_embedding_endpoint,
        api_key=settings.games_advisor_embedding_api_key,
        model=settings.games_advisor_embedding_model,
    )
    try:
        return get_embedding_provider(config), config
    except ValueError as exc:
        raise Refused(str(exc)) from exc


# --- 各個子指令 ---


def _import_games(args: argparse.Namespace, session: Session, settings: Settings) -> int:
    result = service.import_games(
        GameRepository(session), service.read_json(args.games_json), args.first_four
    )
    print(f"已匯入 {result.count} 款桌遊。")
    for game_id, name in result.first_four:
        print(f"  {game_id} 號：{name}")
    print("記得執行 export-games，把匯出檔放進 GAE265G5。")
    return EXIT_OK


def _export_games(args: argparse.Namespace, session: Session, settings: Settings) -> int:
    export = service.export_games(GameRepository(session))
    content = json.dumps(export.to_json(), ensure_ascii=False, indent=2)
    args.out.write_text(content + "\n", encoding="utf-8")
    print(f"已匯出 {len(export.games)} 款桌遊到 {args.out}，next_id 是 {export.next_id}。")
    print("把匯出檔放進 GAE265G5，覆蓋舊的那份。")
    return EXIT_OK


def _sync_games(args: argparse.Namespace, session: Session, settings: Settings) -> int:
    result = service.sync_games(GameRepository(session), service.read_json(args.export_json))
    print(
        f"同步完成：新增 {result.added} 款、更新 {result.updated} 款、"
        f"刪除 {result.deleted} 款，next_id 是 {result.next_id}。"
    )
    return EXIT_OK


def _print_skipped(skipped: list[SkippedGame], note: str) -> None:
    """跳過的款在指令結束時列出來，附上原因（spec §7.2 規則 6）。"""
    if skipped:
        print(f"跳過 {len(skipped)} 款，{note}：", file=sys.stderr)
        for game in skipped:
            print(f"  bgg_id {game.bgg_id}「{game.name}」：{game.reason}", file=sys.stderr)


def _report(result: BatchResult, what: str) -> int:
    """印出一款一個交易的指令跑完的結果。"""
    print(f"{what}：完成 {result.done} 款。")
    _print_skipped(result.skipped, "它們的舊資料沒有變")
    return result.exit_code


def _summarize_reviews(args: argparse.Namespace, session: Session, settings: Settings) -> int:
    # 先確認有真的模型，再讀檔案
    llm = _batch_llm(settings)
    embedding, embedding_config = _embedding(settings)
    result = service.summarize_reviews(
        GameRepository(session),
        ReviewRepository(session),
        service.read_json(args.reviews_json),
        llm=llm,
        embedding=embedding,
        embedding_config=embedding_config,
        only_bgg_ids=args.bgg_id,
    )
    return _report(result, "心得摘要")


def _build_excerpts(args: argparse.Namespace, session: Session, settings: Settings) -> int:
    embedding, embedding_config = _embedding(settings)
    result = service.build_excerpts(
        GameRepository(session),
        ReviewRepository(session),
        service.read_json(args.reviews_json),
        embedding=embedding,
        embedding_config=embedding_config,
        only_bgg_ids=args.bgg_id,
    )
    return _report(result, "心得片段")


def _draft_vocabulary(args: argparse.Namespace, session: Session, settings: Settings) -> int:
    # 先確認有真的模型，再讀檔案
    llm = _batch_llm(settings)
    result = service.draft_vocabulary(
        GameRepository(session),
        service.read_json(args.reviews_json),
        llm=llm,
        out_path=args.out,
        report_path=args.report,
    )
    print(f"{result.candidates} 個候選詞合併成 {result.tags} 個標籤。")
    print(f"詞彙表草稿：{args.out}")
    print(f"歸納報告：{args.report}")
    print("請參考歸納報告編輯草稿，存成 tag_vocabulary.json 後走 MR，再執行 sync-vocabulary。")
    _print_skipped(result.skipped, "它們的心得沒有算進這份草稿")
    return result.exit_code


def _sync_vocabulary(args: argparse.Namespace, session: Session, settings: Settings) -> int:
    result = service.sync_vocabulary(
        TagRepository(session), service.read_json(args.vocabulary_json)
    )
    for line in result.lines:
        print(line)
    return EXIT_OK


def _draft_tags(args: argparse.Namespace, session: Session, settings: Settings) -> int:
    # 先確認有真的模型，再讀檔案
    llm = _batch_llm(settings)
    result = service.draft_tags(
        GameRepository(session),
        TagRepository(session),
        service.read_json(args.reviews_json),
        llm=llm,
        out_path=args.out,
        only_bgg_ids=args.bgg_id,
    )
    print(f"標籤草稿：{args.out}（{result.games} 款桌遊）")
    print(f"原始檔：{service.original_path(args.out)}（不要編輯，匯入時用來比對）")
    for line in result.lines:
        print(line)
    print("請刪掉不對的標籤（只能刪除，不能新增或改分數），再執行 import-tags。")
    _print_skipped(result.skipped, "它們不在草稿裡，匯入時不會動它們的標籤")
    return result.exit_code


def _import_tags(args: argparse.Namespace, session: Session, settings: Settings) -> int:
    result = service.import_tags(GameRepository(session), TagRepository(session), args.draft_json)
    print(f"已匯入 {result.games} 款桌遊的標籤，共 {result.tags} 個。")
    return EXIT_OK


def _add_reviews_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("reviews_json", type=Path, metavar="<reviews.json>")
    parser.add_argument(
        "--bgg-id",
        type=_bgg_ids,
        metavar="<bgg_id>",
        help="只跑指定的桌遊，用來補跑失敗的那幾款；多款用逗號分開。沒給就跑全部桌遊",
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

    summarize_reviews = commands.add_parser("summarize-reviews", help="產生心得摘要：需要真的 LLM")
    _add_reviews_arguments(summarize_reviews)
    summarize_reviews.set_defaults(handler=_summarize_reviews)

    build_excerpts = commands.add_parser("build-excerpts", help="產生心得片段：不用 LLM")
    _add_reviews_arguments(build_excerpts)
    build_excerpts.set_defaults(handler=_build_excerpts)

    draft_vocabulary = commands.add_parser(
        "draft-vocabulary", help="歸納詞彙表草稿與歸納報告：需要真的 LLM，不寫資料庫"
    )
    draft_vocabulary.add_argument("reviews_json", type=Path, metavar="<reviews.json>")
    draft_vocabulary.add_argument("--out", type=Path, required=True, metavar="<詞彙表草稿>")
    draft_vocabulary.add_argument("--report", type=Path, required=True, metavar="<歸納報告>")
    draft_vocabulary.set_defaults(handler=_draft_vocabulary)

    sync_vocabulary = commands.add_parser(
        "sync-vocabulary", help="同步詞彙表：照 tag_vocabulary.json 改寫資料庫的標籤"
    )
    sync_vocabulary.add_argument("vocabulary_json", type=Path, metavar="<tag_vocabulary.json>")
    sync_vocabulary.set_defaults(handler=_sync_vocabulary)

    draft_tags = commands.add_parser(
        "draft-tags", help="上標籤：產生標籤草稿與原始檔，需要真的 LLM，不寫資料庫"
    )
    _add_reviews_arguments(draft_tags)
    draft_tags.add_argument("--out", type=Path, required=True, metavar="<標籤草稿>")
    draft_tags.set_defaults(handler=_draft_tags)

    import_tags = commands.add_parser("import-tags", help="匯入標籤草稿：把審核過的標籤寫進資料庫")
    import_tags.add_argument("draft_json", type=Path, metavar="<標籤草稿>")
    import_tags.set_defaults(handler=_import_tags)

    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except _UsageError as exc:
        print(exc, file=sys.stderr)
        return EXIT_FAILED

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    try:
        with Session(engine) as session:
            return args.handler(args, session, settings)
    except Refused as exc:
        for reason in exc.reasons:
            print(reason, file=sys.stderr)
        return EXIT_FAILED
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
