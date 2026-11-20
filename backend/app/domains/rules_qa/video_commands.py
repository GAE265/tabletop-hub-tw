"""規則影片的本機指令（spec rules-video-maker「本機指令與靜態圖」）。

用法（在 backend/）：
    uv run python -m app.domains.rules_qa.video_commands check  <資料夾>   # 只驗證段資料
    uv run python -m app.domains.rules_qa.video_commands stills <資料夾>   # 靜態圖與對照圖

<資料夾> 內有 video.json 與 assets/，輸出寫到 <資料夾>/out/。不連資料庫、不需要 ffmpeg 與金鑰；
旁白長度先用估計值（每 4 個字 1 秒），接上 TTS 後改用實際長度。
規則書、素材與段資料只放本機（backend/.local/），不提交。
"""

import argparse
import sys
from pathlib import Path

from app.core.config import Settings, get_settings
from app.integrations.video import (
    DEFAULT_STYLE,
    FontConfigError,
    FontSet,
    LayoutError,
    VideoDataError,
    load_video,
    render_stills,
)

EXIT_OK = 0
EXIT_FAILED = 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="video_commands", description="規則影片的本機指令")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<子指令>")
    for name, help_text in (
        ("check", "只驗證段資料"),
        ("stills", "輸出每句與每個動作的靜態圖、對照圖與時間報表"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("folder", type=Path, metavar="<資料夾>")
    return parser


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
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

    try:
        result = render_stills(video, args.folder / "out", fonts, DEFAULT_STYLE)
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


if __name__ == "__main__":
    sys.exit(main())
