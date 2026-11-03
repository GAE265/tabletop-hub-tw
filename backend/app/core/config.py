from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        extra="ignore",
        env_ignore_empty=True,
    )

    database_url: str
    # 預設 jwt，避免忘了設定時意外開啟開發用的身分標頭與 /api/v1/dev
    auth_mode: Literal["dev", "jwt"] = "jwt"
    # AUTH_MODE=dev 且未帶 X-Dev-User 時使用的預設玩家；app/dev 的 player 帳號也用這個值
    dev_default_user_id: UUID = UUID("11111111-1111-4111-8111-111111111111")
    llm_provider: str = "fake"
    embedding_dim: int = 1536
    # 允許跨來源呼叫 API 的前端網址，逗號分隔。預設是本機 Flutter Web 固定的 port；
    # 部署時必須改成實際的前端網址
    cors_allow_origins: str = "http://localhost:5000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
