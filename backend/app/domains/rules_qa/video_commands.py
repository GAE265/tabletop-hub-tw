"""規則影片的本機指令（spec rules-video-maker「本機指令與靜態圖」「完整影片輸出」）。

用法（在 backend/）：
    uv run python -m app.domains.rules_qa.video_commands check  <資料夾>   # 只驗證段資料
    uv run python -m app.domains.rules_qa.video_commands stills <資料夾>   # 靜態圖與對照圖
    uv run python -m app.domains.rules_qa.video_commands render <資料夾>   # 完整影片
    uv run python -m app.domains.rules_qa.video_commands draft <資料夾> \
        --pages rulebook/en-005.txt --chapter-number 11 --chapter-title 步驟三 \
        [--reference-pages rulebook/en-003.txt] [--assets-from video.json]  # AI 產生草稿
    uv run python -m app.domains.rules_qa.video_commands compare <AI 草稿> <手寫>  # 逐項比對

<資料夾> 內有 video.json 與 assets/，輸出寫到 <資料夾>/out/，旁白與段影片快取在 <資料夾>/cache/。
check、stills 不連資料庫、不需要 ffmpeg 與金鑰，旁白長度用估計值（每 4 個字 1 秒）。
render 需要 ffmpeg（FFMPEG_PATH）；TTS 用 .env 的 TTS_PROVIDER，未設定時旁白為靜音、時間為估計值。
規則書、素材與段資料只放本機（backend/.local/），不提交。
"""

import argparse
import json
import sys
from pathlib import Path

from app.core.config import Settings, get_settings
from app.domains.rules_qa.video_coverage import check_coverage, markdown_from_json
from app.domains.rules_qa.video_script import (
    ScriptInputError,
    ScriptRejected,
    ScriptRequest,
    copy_assets_from,
    generate_script,
    load_pages,
    load_terms,
)
from app.integrations.llm import LLMProvider, get_llm_provider
from app.integrations.llm.errors import LLMError
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
from app.integrations.video.compare import compare_videos
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
    draft = commands.add_parser("draft", help="AI 從規則書頁面產生段資料草稿（寫到 draft/）")
    draft.add_argument("folder", type=Path, metavar="<資料夾>")
    draft.add_argument(
        "--pages",
        action="append",
        required=True,
        metavar="<頁面檔>",
        help="規則書頁面文字（相對資料夾），檔名 <語言>-<頁碼>.txt；可指定多次",
    )
    draft.add_argument(
        "--reference-pages",
        action="append",
        default=[],
        metavar="<頁面檔>",
        help="參考頁（相對資料夾）：只供查牌名與分類，不可寫成旁白；可指定多次",
    )
    draft.add_argument("--chapter-number", type=int, required=True)
    draft.add_argument("--chapter-title", required=True)
    draft.add_argument("--terms", default="terms.json", help="用語對照表（相對資料夾）")
    draft.add_argument(
        "--assets-from",
        metavar="<video.json>",
        help="從這份段資料借用同一個 asset_key 的照片檔與區域座標（相對資料夾）",
    )
    coverage = commands.add_parser(
        "coverage", help="規則涵蓋檢查：本章原文分別對照旁白與字幕，輸出 coverage.json、coverage.md"
    )
    coverage.add_argument("folder", type=Path, metavar="<草稿資料夾>")
    coverage.add_argument(
        "--pages",
        action="append",
        required=True,
        metavar="<頁面檔>",
        help="本章的規則書頁面（相對草稿資料夾，例如 ../rulebook/en-005.txt）；可指定多次",
    )
    compare = commands.add_parser("compare", help="逐項比對兩份段資料，輸出 compare.md")
    compare.add_argument("a", type=Path, metavar="<AI 草稿資料夾>")
    compare.add_argument("b", type=Path, metavar="<手寫資料夾>")
    return parser


def main(
    argv: list[str] | None = None,
    settings: Settings | None = None,
    ffmpeg: list[str] | None = None,
    llm: LLMProvider | None = None,
) -> int:
    """ffmpeg、llm 只給測試用：換成手寫的假 ffmpeg 與 FakeLLMProvider；平常從設定讀。"""
    args = _build_parser().parse_args(argv)
    if args.command == "draft":
        return _draft(args, settings or get_settings(), llm)
    if args.command == "compare":
        return _compare(args.a, args.b)
    if args.command == "coverage":
        return _coverage(args, settings or get_settings(), llm)
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


def _draft(args: argparse.Namespace, settings: Settings, llm: LLMProvider | None) -> int:
    folder: Path = args.folder
    try:
        request = ScriptRequest(
            chapter_number=args.chapter_number,
            chapter_title=args.chapter_title,
            pages=load_pages(folder, args.pages),
            reference_pages=(
                load_pages(folder, args.reference_pages) if args.reference_pages else []
            ),
            terms=load_terms(folder / args.terms),
            **_game_identity(folder),
        )
    except ScriptInputError as exc:
        print(f"輸入錯誤：{exc}", file=sys.stderr)
        return EXIT_FAILED

    draft_folder = folder / "draft"
    try:
        data = generate_script(
            llm or get_llm_provider(settings.llm_provider, settings), request, draft_folder
        )
    except LLMError as exc:
        print(f"LLM 暫時無法使用或拒絕輸出：{exc}", file=sys.stderr)
        return EXIT_FAILED
    except ScriptRejected as exc:
        draft_folder.mkdir(parents=True, exist_ok=True)
        for n, output in enumerate(exc.outputs, start=1):
            _write_json(draft_folder / f"rejected-{n}.json", output)
        print("AI 改寫一次後仍不通過檢查：", file=sys.stderr)
        for error in exc.errors:
            print(f"- {error}", file=sys.stderr)
        print(f"兩次原始輸出存在 {draft_folder}/rejected-1.json、rejected-2.json", file=sys.stderr)
        return EXIT_FAILED

    draft_folder.mkdir(parents=True, exist_ok=True)
    borrowed: list[str] = []
    if args.assets_from:
        hand = folder / args.assets_from
        try:
            borrowed = copy_assets_from(data, hand.parent, draft_folder)
        except VideoDataError as exc:
            print(f"借用照片與座標失敗（{hand}）：{exc}", file=sys.stderr)
            return EXIT_FAILED
    _write_json(draft_folder / "video.json", data)

    beats = sum(len(s["beats"]) for s in data["segments"])
    pending = [a["asset_key"] for a in data["assets"] if a["file"] is None]
    print(f"已產生草稿：{draft_folder / 'video.json'}（{len(data['segments'])} 段、{beats} 句）")
    print(f"素材 {len(data['assets'])} 項：借用 {len(borrowed)} 項、待拍 {len(pending)} 項")
    if pending:
        print(f"待拍：{'、'.join(pending)}")
    return EXIT_OK


def _game_identity(folder: Path) -> dict[str, str | None]:
    """草稿的 game_key、title、voice：沿用資料夾內手寫版的值；沒有手寫版就用資料夾名稱。"""
    try:
        raw = json.loads((folder / "video.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    return {
        "game_key": raw.get("game_key") or folder.name,
        "title": raw.get("title") or f"{folder.name} 規則教學",
        "voice": raw.get("voice"),
    }


def _compare(a: Path, b: Path) -> int:
    videos = []
    for folder in (a, b):
        try:
            videos.append(load_video(folder, draft=True))
        except VideoDataError as exc:
            print(f"{folder} 的段資料有錯：{exc}", file=sys.stderr)
            return EXIT_FAILED
    report = compare_videos(videos[0], videos[1])
    target = a / "compare.md"
    coverage = a / "coverage.json"
    if coverage.is_file():
        section = markdown_from_json(coverage.read_text(encoding="utf-8"))
    else:
        section = "## 規則陳述檢查\n\n未做規則涵蓋檢查（沒有 coverage.json）。\n"
    target.write_text(report.markdown() + "\n" + section, encoding="utf-8")
    print(f"已輸出比對報告：{target}")
    for category, counts in report.summary.items():
        print(
            f"  {category}：相同 {counts.same}、不同 {counts.different}、"
            f"缺少 {counts.missing}、多出 {counts.extra}"
        )
    return EXIT_OK


def _coverage(args: argparse.Namespace, settings: Settings, llm: LLMProvider | None) -> int:
    folder: Path = args.folder
    try:
        video = load_video(folder, draft=True)
        pages = load_pages(folder, args.pages)
    except VideoDataError as exc:
        print(f"{folder} 的段資料有錯或不存在：{exc}", file=sys.stderr)
        return EXIT_FAILED
    except ScriptInputError as exc:
        print(f"輸入錯誤：{exc}", file=sys.stderr)
        return EXIT_FAILED
    try:
        report = check_coverage(
            llm or get_llm_provider(settings.llm_provider, settings), video, pages
        )
    except LLMError as exc:
        print(f"LLM 暫時無法使用或拒絕輸出：{exc}", file=sys.stderr)
        return EXIT_FAILED
    except (KeyError, TypeError) as exc:
        print(f"LLM 的輸出格式不符：{exc!r}", file=sys.stderr)
        return EXIT_FAILED
    (folder / "coverage.json").write_text(report.to_json(), encoding="utf-8")
    (folder / "coverage.md").write_text(report.markdown(), encoding="utf-8")
    shorter = sum(1 for r in report.rules if r.narration_shorter)
    issues = sum(1 for r in report.rules if r.has_issue)
    print(f"已輸出規則涵蓋檢查：{folder / 'coverage.md'}（AI 檢查，僅供參考）")
    print(
        f"  規則 {len(report.rules)} 條：有問題 {issues} 條（旁白比字幕少條件 {shorter} 條）；"
        f"說反或規則書沒有的句子 {len(report.problems)} 句"
    )
    return EXIT_OK


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
