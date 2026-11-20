"""規則影片的本機指令（spec rules-video-maker「本機指令與靜態圖」「完整影片輸出」）。

用法（在 backend/）：
    uv run python -m app.domains.rules_qa.video_commands check  <資料夾>   # 只驗證段資料
    uv run python -m app.domains.rules_qa.video_commands stills <資料夾>   # 靜態圖與對照圖
    uv run python -m app.domains.rules_qa.video_commands render <資料夾>   # 完整影片

<資料夾> 內有 video.json 與 assets/，輸出寫到 <資料夾>/out/，旁白與段影片快取在 <資料夾>/cache/。
check、stills 不連資料庫、不需要 ffmpeg 與金鑰，旁白長度用估計值（每 4 個字 1 秒）。
render 需要 ffmpeg（FFMPEG_PATH）；TTS 用 .env 的 TTS_PROVIDER，未設定時旁白為靜音、時間為估計值。
規則書、素材與段資料只放本機（backend/.local/），不提交。
"""

import argparse
import sys
from pathlib import Path

from app.core.config import Settings, get_settings
from app.integrations.tts import TTSConfig, TTSError, get_tts_provider
from app.integrations.video import (
    DEFAULT_STYLE,
    FontConfigError,
    FontSet,
    LayoutError,
    VideoDataError,
    VideoRenderError,
    load_video,
    render_stills,
)
from app.integrations.video.ffmpeg import Ffmpeg
from app.integrations.video.pipeline import render_video

EXIT_OK = 0
EXIT_FAILED = 1
FAKE_TTS_WARNING = "未設定文字轉語音（TTS_PROVIDER），旁白為靜音，時間為估計值"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="video_commands", description="規則影片的本機指令")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<子指令>")
    for name, help_text in (
        ("check", "只驗證段資料"),
        ("stills", "輸出每句與每個動作的靜態圖、對照圖與時間報表"),
        ("render", "輸出含旁白與背景音樂的完整影片"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("folder", type=Path, metavar="<資料夾>")
    return parser


def main(
    argv: list[str] | None = None,
    settings: Settings | None = None,
    ffmpeg: list[str] | None = None,
) -> int:
    """ffmpeg 只給測試用：換成手寫的假 ffmpeg 指令；平常從 FFMPEG_PATH 讀。"""
    args = _build_parser().parse_args(argv)
    try:
        video = load_video(args.folder)
    except VideoDataError as exc:
        print(exc, file=sys.stderr)
        return EXIT_FAILED

    if args.command == "check":
        beats = sum(len(s.beats) for s in video.segments)
        print(f"段資料正確：{len(video.segments)} 段、{beats} 句、{len(video.assets)} 個素材")
        return EXIT_OK

    settings = settings or get_settings()
    try:
        fonts = FontSet(
            settings.video_font_regular, settings.video_font_bold, settings.video_font_index
        )
    except FontConfigError as exc:
        print(f"字型設定錯誤：{exc}", file=sys.stderr)
        return EXIT_FAILED
    if fonts.warning:
        print(f"警告：{fonts.warning}", file=sys.stderr)

    if args.command == "stills":
        return _stills(video, args.folder, fonts)
    return _render(video, args.folder, fonts, settings, ffmpeg)


def _stills(video, folder: Path, fonts: FontSet) -> int:
    try:
        result = render_stills(video, folder / "out", fonts, DEFAULT_STYLE)
    except LayoutError as exc:
        print(f"排版失敗：{exc}", file=sys.stderr)
        return EXIT_FAILED
    for warning in result.warnings:
        if warning != fonts.warning:
            print(f"警告：{warning}", file=sys.stderr)
    print(
        f"已輸出 {len(result.stills)} 張靜態圖"
        f"（總長約 {result.total_seconds:.1f} 秒，旁白為估計值）"
    )
    print(f"對照圖：{result.sheet}")
    print(f"時間報表：{result.timing_csv}")
    return EXIT_OK


def _render(
    video, folder: Path, fonts: FontSet, settings: Settings, ffmpeg: list[str] | None
) -> int:
    config = TTSConfig(
        provider=settings.tts_provider,
        region=settings.tts_region,
        api_key=settings.tts_api_key,
        voice=settings.tts_voice,
    )
    estimated = config.provider == "fake"
    try:
        tts = get_tts_provider(config)
    except (TTSError, ValueError) as exc:
        print(f"文字轉語音設定錯誤：{exc}", file=sys.stderr)
        return EXIT_FAILED
    if estimated:
        print(f"警告：{FAKE_TTS_WARNING}", file=sys.stderr)

    try:
        result = render_video(
            video,
            folder / "out",
            fonts,
            DEFAULT_STYLE,
            tts,
            Ffmpeg(ffmpeg or [settings.ffmpeg_path]),
            cache_dir=folder / "cache",
            music_volume=settings.video_music_volume,
            estimated=estimated,
        )
    except LayoutError as exc:
        print(f"排版失敗：{exc}", file=sys.stderr)
        return EXIT_FAILED
    except VideoRenderError as exc:
        print(f"影片輸出失敗：{exc}", file=sys.stderr)
        return EXIT_FAILED
    except TTSError as exc:
        print(f"文字轉語音失敗：{exc}（已合成的旁白保留在快取，下次只補缺的）", file=sys.stderr)
        return EXIT_FAILED

    shown = {fonts.warning}
    for warning in result.warnings:
        if warning not in shown and not (estimated and "時間為估計值" in warning):
            print(f"警告：{warning}", file=sys.stderr)
    encoded = sum(1 for s in result.segments if not s.reused)
    suffix = "，時間為估計值" if estimated else ""
    print(f"已輸出影片：{result.video}（總長 {result.total_seconds:.1f} 秒{suffix}）")
    print(f"段影片：重新編碼 {encoded} 段、沿用快取 {len(result.segments) - encoded} 段")
    print(f"時間報表：{result.timing_csv}")
    print(f"報告：{result.report}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
