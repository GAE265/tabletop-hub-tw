import importlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import create_db_engine
from app.core.errors import register_error_handlers
from app.domains.health.router import router as health_router
from app.integrations.embedding import EmbeddingConfig, get_embedding_provider
from app.integrations.llm import get_llm_provider

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_db_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title="遊任有娛 tabletop-hub-tw", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = sessionmaker(engine)
    # LLM_PROVIDER、GAMES_ADVISOR_EMBEDDING_* 設錯時在啟動就明確報錯
    app.state.llm = get_llm_provider(settings.llm_provider, settings)
    app.state.games_advisor_embedding = get_embedding_provider(
        EmbeddingConfig(
            provider=settings.games_advisor_embedding_provider,
            dim=settings.games_advisor_embedding_dim,
            endpoint=settings.games_advisor_embedding_endpoint,
            api_key=settings.games_advisor_embedding_api_key,
            model=settings.games_advisor_embedding_model,
        )
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            # 身分走標頭（開發用 X-Dev-User、正式用 Authorization），不使用 cookie
            allow_headers=["X-Dev-User", "Authorization", "Content-Type", "Accept"],
        )
    register_error_handlers(app)
    app.include_router(health_router, prefix=API_PREFIX)

    if settings.auth_mode == "dev":
        # app/dev 任何地方都不得 import（AGENTS.md 4.2），所以只在 dev 模式動態載入
        dev_router = importlib.import_module("app.dev.router")
        app.include_router(dev_router.router, prefix=API_PREFIX)

    return app
