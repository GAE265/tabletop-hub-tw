"""規則問答的後端指令：建立規則書的檢索索引（spec rules-qa「建立規則書索引」）。

用法（在 backend/）：uv run python -m app.domains.rules_qa.commands index --game-id <遊戲編號>

規則書頁面重新入庫或換了 embedding 模型後，要再執行一次；可以重複執行，結果相同。
"""

import argparse
import sys

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import create_db_engine
from app.domains.rules_ingest.repository import ManualPageRepository
from app.domains.rules_ingest.service import read_manual_pages
from app.domains.rules_qa.repository import RulesQaRepository
from app.domains.rules_qa.service import NoRulebookPages, build_index
from app.integrations.embedding import EmbeddingConfig, EmbeddingError, get_embedding_provider

EXIT_OK = 0
EXIT_FAILED = 1


def embedding_config(settings: Settings) -> EmbeddingConfig:
    return EmbeddingConfig(
        provider=settings.rules_qa_embedding_provider,
        dim=settings.rules_qa_embedding_dim,
        endpoint=settings.rules_qa_embedding_endpoint,
        api_key=settings.rules_qa_embedding_api_key,
        model=settings.rules_qa_embedding_model,
    )


def embedding_model_name(config: EmbeddingConfig) -> str:
    """記在每個段落上的模型名稱；用 fake 時記 fake（與推薦 Agent 相同）。"""
    return "fake" if config.provider == "fake" or config.model is None else config.model


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rules_qa", description="規則問答的後端指令")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<子指令>")
    index = commands.add_parser("index", help="建立某款遊戲的規則書檢索索引")
    index.add_argument("--game-id", type=int, required=True, metavar="<遊戲編號>")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = get_settings()
    config = embedding_config(settings)
    embedding = get_embedding_provider(config)
    engine = create_db_engine(settings.database_url)
    try:
        with Session(engine) as session:
            repository = RulesQaRepository(session)
            if repository.game_name(args.game_id) is None:
                print(f"找不到桌遊 {args.game_id}", file=sys.stderr)
                return EXIT_FAILED
            pages = ManualPageRepository(session)
            count = build_index(
                repository,
                lambda game_id: read_manual_pages(pages, game_id),
                embedding,
                embedding_model_name(config),
                args.game_id,
            )
    except NoRulebookPages:
        print("這款遊戲還沒有規則書頁面，請先用規則書入庫匯入", file=sys.stderr)
        return EXIT_FAILED
    except EmbeddingError as exc:
        print(f"embedding 服務暫時無法使用：{exc}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        engine.dispose()
    print(f"已建立 {count} 個段落")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
