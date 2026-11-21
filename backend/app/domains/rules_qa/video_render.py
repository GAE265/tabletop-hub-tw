"""產生影片工作的處理函式（kind = render；add-rules-video-mobile design.md D15 與實作決定）。

1. 讀段資料，檢查還缺什麼（MR 7 的 readiness）；缺東西就失敗並列出。
2. 拿掉店員略過的選拍素材與引用它的地方（資料庫的草稿不改）。
3. 展開工作資料夾 `RULES_VIDEO_WORK_DIR/<專案>/`：寫 video.json，從存放介面放回缺的照片；
   cache/ 保留，才能只重做改過的段。
4. 呼叫 integrations/video 的 render_video，進度寫進工作。
5. 成品存到存放介面 `rules_videos/<專案>/renders/<工作 id>.mp4`；記下總長、重新編碼與沿用的段。
逾時：TTS 每句 30 秒（integrations/tts）；ffmpeg 每次呼叫 RENDER_FFMPEG_TIMEOUT_SECONDS；
整個工作仍受 JobRunner 的 30 分鐘限制。
"""

import csv
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.domains.rules_qa.repository import VideoDraftRepository
from app.domains.rules_qa.video_assets import (
    is_skipped,
    photo_key,
    readiness,
    skip_blocked_message,
    strip_skipped,
)
from app.domains.rules_qa.video_jobs import JobContext, JobFailed
from app.integrations.storage.base import FileStorage
from app.integrations.storage.errors import StorageError
from app.integrations.tts import TTSConfig, TTSError, TTSProvider, get_tts_provider
from app.integrations.video import (
    DEFAULT_STYLE,
    FontConfigError,
    FontSet,
    LayoutError,
    VideoDataError,
    VideoRenderError,
    VideoTimeoutError,
    load_video,
)
from app.integrations.video.ffmpeg import Ffmpeg
from app.integrations.video.pipeline import render_video

logger = logging.getLogger(__name__)

# 每次呼叫 ffmpeg 的上限；寫在這裡不加設定（design.md D15 實作決定）
RENDER_FFMPEG_TIMEOUT_SECONDS = 600

RENDER_NO_DRAFT_MESSAGE = "還沒有草稿，請先產生草稿"
RENDER_FAILED_MESSAGE = "影片輸出失敗，請再試一次；若一直發生請通知管理員"
RENDER_TIMEOUT_MESSAGE = "影片輸出超過時間沒有完成，已停止；請再試一次，若一直發生請通知管理員"
RENDER_TTS_MESSAGE = "旁白合成失敗（語音服務暫時無法使用），請稍後再試；已合成的旁白會保留"
RENDER_STORAGE_MESSAGE = "影片存放空間暫時無法使用，請稍後再試"
RENDER_SETUP_MESSAGE = "產生影片的設定有誤，請通知管理員"


@dataclass(frozen=True)
class RenderConfig:
    """產生影片需要的設定（從 Settings 組出來；測試直接建立）。"""

    work_dir: Path
    ffmpeg_command: list[str]
    ffmpeg_timeout_seconds: float
    font_regular: str | None
    font_bold: str | None
    font_index: int
    music_volume: float
    tts: TTSConfig = field(default_factory=lambda: TTSConfig(provider="fake"))

    @classmethod
    def from_settings(cls, settings: Settings) -> "RenderConfig":
        return cls(
            work_dir=Path(settings.rules_video_work_dir),
            ffmpeg_command=[settings.ffmpeg_path],
            ffmpeg_timeout_seconds=RENDER_FFMPEG_TIMEOUT_SECONDS,
            font_regular=settings.video_font_regular,
            font_bold=settings.video_font_bold,
            font_index=settings.video_font_index,
            music_volume=settings.video_music_volume,
            tts=TTSConfig(
                provider=settings.tts_provider,
                region=settings.tts_region,
                api_key=settings.tts_api_key,
                voice=settings.tts_voice,
            ),
        )


def not_ready_message(report: dict[str, Any]) -> str:
    parts = []
    if report["missing_photos"]:
        parts.append(f"{len(report['missing_photos'])} 個素材還沒有照片")
    if report["missing_regions"]:
        parts.append(f"{len(report['missing_regions'])} 個區域還沒標")
    if report["unsupported"]:
        parts.append(f"{len(report['unsupported'])} 個本版不支援的繪製素材")
    return f"還不能產生影片：{'、'.join(parts)}"


def segment_starts(timing_csv: Path) -> list[dict[str, Any]]:
    """每段第一句的開始秒數與字幕（看影片頁的段清單）；沒有旁白的段（例如標題字卡）不列。"""
    segments: dict[str, dict[str, Any]] = {}
    with timing_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = row["segment_key"]
            if key not in segments:
                segments[key] = {
                    "segment_key": key,
                    "start_seconds": float(row["start_sec"]),
                    "title": row["subtitle"],
                }
    return list(segments.values())


class RenderJobHandler:
    """產生影片的工作；後端啟動時註冊在 app.state.rules_video_job_handlers["render"]。

    字型與 TTS 在每次工作才建立：設定寫錯只讓這個工作失敗（附說明），不會讓後端起不來。
    tts 只給測試換成手寫的 fake。
    """

    def __init__(
        self, storage: FileStorage, config: RenderConfig, *, tts: TTSProvider | None = None
    ) -> None:
        self._storage = storage
        self._config = config
        self._tts = tts

    @classmethod
    def from_settings(cls, settings: Settings, storage: FileStorage) -> "RenderJobHandler":
        return cls(storage, RenderConfig.from_settings(settings))

    def __call__(self, ctx: JobContext) -> dict[str, Any]:
        ctx.report(0.02, "檢查素材")
        with ctx.session_factory() as session:
            state = VideoDraftRepository(session).get_state(ctx.project_id)
        if state is None or state.video is None:
            raise JobFailed(RENDER_NO_DRAFT_MESSAGE)
        report = readiness(state.video)
        if not report["ready"]:
            raise JobFailed(not_ready_message(report))
        skipped = {a["asset_key"] for a in state.video.get("assets", []) if is_skipped(a)}
        stripped = strip_skipped(state.video, skipped)
        if stripped.blocked:
            raise JobFailed(skip_blocked_message(stripped.blocked))

        folder = self._config.work_dir / str(ctx.project_id)
        self._expand(folder, ctx.project_id, stripped.video)
        try:
            video = load_video(folder)
        except VideoDataError as exc:
            raise JobFailed(f"段資料有問題，無法輸出：{exc}") from exc
        fonts, tts, estimated = self._tools()

        ffmpeg = Ffmpeg(
            self._config.ffmpeg_command, timeout_seconds=self._config.ffmpeg_timeout_seconds
        )
        try:
            result = render_video(
                video,
                folder / "out",
                fonts,
                DEFAULT_STYLE,
                tts,
                ffmpeg,
                cache_dir=folder / "cache",
                music_volume=self._config.music_volume,
                estimated=estimated,
                on_progress=lambda progress, message: ctx.report(0.05 + 0.85 * progress, message),
            )
        except LayoutError as exc:
            raise JobFailed(f"排版失敗：{exc}") from exc
        except VideoTimeoutError as exc:
            logger.warning("產生影片逾時（專案 %s）：%s", ctx.project_id, exc)
            raise JobFailed(RENDER_TIMEOUT_MESSAGE) from exc
        except VideoRenderError as exc:
            # 店員看得懂的說明；ffmpeg 的細節記 log 給管理員
            logger.warning("產生影片失敗（專案 %s）：%s", ctx.project_id, exc)
            raise JobFailed(RENDER_FAILED_MESSAGE) from exc
        except TTSError as exc:
            logger.warning("旁白合成失敗（專案 %s）：%s", ctx.project_id, exc)
            raise JobFailed(RENDER_TTS_MESSAGE) from exc

        ctx.report(0.95, "儲存影片")
        key = f"rules_videos/{ctx.project_id}/renders/{ctx.job_id}.mp4"
        try:
            self._storage.put(key, result.video.read_bytes(), "video/mp4")
        except StorageError as exc:
            raise JobFailed(RENDER_STORAGE_MESSAGE) from exc
        with ctx.session_factory() as session:
            repo = VideoDraftRepository(session)
            with repo.transaction():
                repo.touch(ctx.project_id)
        return {
            "video_key": key,
            "total_seconds": round(result.total_seconds, 3),
            "reencoded": [s.segment_key for s in result.segments if not s.reused],
            "reused": [s.segment_key for s in result.segments if s.reused],
            "skipped_assets": sorted(skipped),
            "estimated": estimated,
            "warnings": list(result.warnings),
            "video_version": state.video_version,
            "segments": segment_starts(result.timing_csv),
        }

    def _expand(self, folder: Path, project_id: uuid.UUID, video: dict[str, Any]) -> None:
        """寫 video.json，從存放介面放回缺的照片（檔名每次上傳都不同，已有的就是同一張）。"""
        assets = folder / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        (folder / "video.json").write_text(
            json.dumps(video, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for asset in video.get("assets", []):
            file = asset.get("file")
            if not file or (assets / file).is_file():
                continue
            try:
                data = self._storage.get(photo_key(project_id, file))
            except StorageError as exc:
                raise JobFailed(RENDER_STORAGE_MESSAGE) from exc
            temporary = assets / f"{file}.tmp"
            temporary.write_bytes(data)
            temporary.replace(assets / file)

    def _tools(self) -> tuple[FontSet, TTSProvider, bool]:
        config = self._config
        try:
            fonts = FontSet(config.font_regular, config.font_bold, config.font_index)
        except FontConfigError as exc:
            logger.warning("字型設定錯誤：%s", exc)
            raise JobFailed(RENDER_SETUP_MESSAGE) from exc
        if self._tts is not None:
            return fonts, self._tts, False
        try:
            tts = get_tts_provider(config.tts)
        except (TTSError, ValueError) as exc:
            logger.warning("文字轉語音設定錯誤：%s", exc)
            raise JobFailed(RENDER_SETUP_MESSAGE) from exc
        return fonts, tts, config.tts.provider == "fake"
