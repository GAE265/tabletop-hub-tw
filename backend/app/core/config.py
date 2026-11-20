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
    # --- LLM（全域，所有 domain 共用） ---
    llm_provider: str = "fake"
    llm_endpoint: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    # 批次指令用的部署名稱；沒填就用 llm_model
    llm_batch_model: str | None = None
    # ⚠️ 合法值要和 Azure 的 reasoning.effort 一致。
    # 沒填就不帶 reasoning，用模型預設；非推理模型要留空
    llm_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] | None = None
    llm_timeout_seconds: float = 30
    # 全域向量維度；games_advisor 不讀它，改讀 games_advisor_embedding_dim
    embedding_dim: int = 1536
    # --- games_advisor 自己的 embedding；沒填不退回任何全域設定 ---
    games_advisor_embedding_provider: str = "fake"
    games_advisor_embedding_endpoint: str | None = None
    games_advisor_embedding_api_key: str | None = None
    games_advisor_embedding_model: str | None = None
    games_advisor_embedding_dim: int = 1536
    # --- OCR 與視覺模型（integrations/ocr；規則書圖片入庫用） ---
    # fake：測試用，沒有腳本時呼叫會回 503；cloud：Azure Document Intelligence + Azure OpenAI 視覺
    ocr_provider: str = "fake"
    # 金鑰全部沿用 llm_api_key；端點各自獨立設定。
    # Document Intelligence（cognitiveservices.azure.com）的端點
    ocr_di_endpoint: str | None = None
    # 視覺模型的端點；沒填就用 llm_endpoint
    ocr_vision_endpoint: str | None = None
    # 視覺模型的部署名稱；沒填就用 llm_model
    ocr_vision_model: str | None = None
    # 逐頁轉錄單次約 30 秒，加上上傳大圖，所以比 llm_timeout_seconds 長
    ocr_vision_timeout_seconds: float = 120
    # --- rules_qa 自己的 embedding；沒填不退回任何全域設定 ---
    rules_qa_embedding_provider: str = "fake"
    rules_qa_embedding_endpoint: str | None = None
    rules_qa_embedding_api_key: str | None = None
    rules_qa_embedding_model: str | None = None
    rules_qa_embedding_dim: int = 1536
    # --- 文字轉語音（integrations/tts；影片生產器的旁白） ---
    # fake：產生靜音音檔（測試與開發用）；azure：Azure AI Speech
    tts_provider: str = "fake"
    # Azure AI Speech 資源的區域代碼，例如 eastasia
    tts_region: str | None = None
    tts_api_key: str | None = None
    # 預設聲音；段資料指定的 voice 優先
    tts_voice: str = "zh-TW-YunJheNeural"
    # --- 檔案儲存（影片生產器的素材照片、旁白與影片） ---
    # fake：存在記憶體（測試用）；local：存在本機資料夾（開發用）；cloud：Azure Blob Storage
    storage_provider: str = "fake"
    storage_local_dir: str | None = None
    # local 時回傳的檔案網址前綴，例如 http://localhost:8000/media
    storage_public_base_url: str | None = None
    storage_connection_string: str | None = None
    storage_container: str | None = None
    # --- 規則影片的字型（integrations/video；本機指令輸出畫面用） ---
    # 直接指定字型檔，例如 Windows 的微軟正黑體 C:\Windows\Fonts\msjh.ttc；
    # 兩個都沒填時改用 Pillow 內建字型（中文無法正確顯示），並印出警告
    video_font_regular: str | None = None
    # 粗體（標題、標籤）；沒填就用 video_font_regular
    video_font_bold: str | None = None
    # .ttc 字型集合檔內要用第幾個字型；.ttf／.otf 忽略
    video_font_index: int = 0
    # ffmpeg 執行檔；在 PATH 裡就填 ffmpeg，否則填完整路徑
    ffmpeg_path: str = "ffmpeg"
    # 背景音樂音量（0–1）；旁白出現時還會再自動壓低
    video_music_volume: float = 0.25
    # 允許跨來源呼叫 API 的前端網址，逗號分隔。預設是本機 Flutter Web 固定的 port；
    # 部署時必須改成實際的前端網址
    cors_allow_origins: str = "http://localhost:5000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
