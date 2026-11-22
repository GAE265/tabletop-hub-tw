import importlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.db import create_db_engine, create_session_factory
from app.core.errors import register_error_handlers
from app.core.games.router import router as games_router
from app.domains.booking.router import router as booking_router
from app.domains.games_advisor.router import router as games_advisor_router
from app.domains.groups.router import notifications_router as group_notifications_router
from app.domains.groups.router import router as groups_router
from app.domains.health.router import router as health_router
from app.domains.matches.router import router as matches_router
from app.domains.rules_ingest.router import router as rules_ingest_router
from app.domains.rules_qa.router import router as rules_qa_router
from app.domains.rules_qa.router import videos_router as rules_qa_videos_router
from app.domains.rules_qa.video_jobs import JobRunner, recover_interrupted_jobs
from app.domains.shops.router import router as shops_router
from app.integrations.embedding import EmbeddingConfig, get_embedding_provider
from app.integrations.llm import get_llm_provider
from app.integrations.ocr.factory import get_vision_provider

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_db_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        # 規則影片的背景工作（add-rules-video-mobile design.md D2）：先把中斷的工作標為失敗，
        # 再開執行緒；關閉時停止
        runner = None
        if settings.rules_video_worker:
            recover_interrupted_jobs(application.state.session_factory)
            runner = JobRunner(
                application.state.session_factory, application.state.rules_video_job_handlers
            )
            runner.start()
        application.state.rules_video_runner = runner
        try:
            yield
        finally:
            if runner is not None:
                runner.stop()
            engine.dispose()

    app = FastAPI(title="遊任有娛 tabletop-hub-tw", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = create_session_factory(engine)
    # 規則影片工作的處理函式（kind → 函式）；MR 4、MR 8、MR 10 依序註冊
    app.state.rules_video_job_handlers = {}
    app.state.rules_video_runner = None
    # LLM_PROVIDER、GAMES_ADVISOR_EMBEDDING_* 設錯時在啟動就明確報錯
    app.state.llm = get_llm_provider(settings.llm_provider, settings)
    app.state.vision = get_vision_provider(settings.ocr_provider, settings)
    app.state.games_advisor_embedding_config = EmbeddingConfig(
        provider=settings.games_advisor_embedding_provider,
        dim=settings.games_advisor_embedding_dim,
        endpoint=settings.games_advisor_embedding_endpoint,
        api_key=settings.games_advisor_embedding_api_key,
        model=settings.games_advisor_embedding_model,
    )
    app.state.games_advisor_embedding = get_embedding_provider(
        app.state.games_advisor_embedding_config
    )
    rules_qa_embedding_config = EmbeddingConfig(
        provider=settings.rules_qa_embedding_provider,
        dim=settings.rules_qa_embedding_dim,
        endpoint=settings.rules_qa_embedding_endpoint,
        api_key=settings.rules_qa_embedding_api_key,
        model=settings.rules_qa_embedding_model,
    )
    app.state.rules_qa_embedding = get_embedding_provider(rules_qa_embedding_config)
    # 問答時只檢索同一個模型建立的段落；與索引指令記錄的名稱一致（rules_qa/commands.py）
    app.state.rules_qa_embedding_model = (
        "fake"
        if rules_qa_embedding_config.provider == "fake" or rules_qa_embedding_config.model is None
        else rules_qa_embedding_config.model
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
    app.include_router(games_router, prefix=API_PREFIX)
    app.include_router(booking_router, prefix=API_PREFIX)
    app.include_router(groups_router, prefix=API_PREFIX)
    app.include_router(group_notifications_router, prefix=API_PREFIX)
    app.include_router(games_advisor_router, prefix=API_PREFIX)
    app.include_router(rules_ingest_router, prefix=API_PREFIX)
    app.include_router(rules_qa_router, prefix=API_PREFIX)
    app.include_router(rules_qa_videos_router, prefix=API_PREFIX)
    app.include_router(matches_router, prefix=API_PREFIX)
    app.include_router(shops_router, prefix=API_PREFIX)

    if settings.auth_mode == "dev":
        # app/dev 任何地方都不得 import（AGENTS.md 4.2），所以只在 dev 模式動態載入
        dev_router = importlib.import_module("app.dev.router")
        app.include_router(dev_router.router, prefix=API_PREFIX)

    return app
