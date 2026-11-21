"""完整影片輸出（spec rules-video-maker「完整影片輸出」）。

順序：排版（放不下就在任何輸出前失敗）→ 確認 ffmpeg → 合成旁白（快取）→ 依實際長度算時間軸
→ 逐段編碼（快取，段影片不含進度條）→ 串接 → 疊上進度條成無聲版 → 合成背景音樂
→ 混音（旁白出現時壓低音樂）。
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.integrations.tts import TTSProvider
from app.integrations.video.assets import AssetLibrary
from app.integrations.video.bgm import synthesize_bgm, to_wav
from app.integrations.video.encode import (
    EncodedSegment,
    FfmpegSegmentEncoder,
    SegmentEncoder,
    encode_segments,
)
from app.integrations.video.ffmpeg import Ffmpeg
from app.integrations.video.fonts import FontSet
from app.integrations.video.layout import layout_video
from app.integrations.video.model import Video
from app.integrations.video.narration import NarrationClip, prepare_narration
from app.integrations.video.progress import OVERLAY_VIDEO_ARGS, overlay_progress
from app.integrations.video.render import Renderer
from app.integrations.video.stills import safe_file_part
from app.integrations.video.style import Style
from app.integrations.video.timeline import Timeline, build_timeline, write_timing_csv

DEFAULT_MUSIC_VOLUME = 0.25
ESTIMATED_NOTE = "時間為估計值：未設定文字轉語音（TTS_PROVIDER），旁白為靜音，每句長度依字數估計"
PROGRESS_NOTE = (
    "進度條：段影片不含進度條，串接後才疊上去（重新編碼整支影片一次："
    f"{' '.join(OVERLAY_VIDEO_ARGS)}）；改了某一段，只會重新編碼那一段"
)


# 進度回呼：(0–1 的進度, 目前在做什麼)
ProgressCallback = Callable[[float, str], None]

# 各步驟佔整體進度的區間：旁白（TTS 可能慢）、段影片（逐格編碼，最花時間）
NARRATION_SPAN = (0.02, 0.2)
SEGMENT_SPAN = (0.2, 0.85)


def _span(span: tuple[float, float], done: int, total: int) -> float:
    start, end = span
    return start + (end - start) * done / max(total, 1)


@dataclass(frozen=True)
class RenderResult:
    video: Path
    silent: Path  # 疊好進度條的無聲版
    joined: Path  # 串接好、還沒疊進度條的影片（在快取資料夾，畫質檢查用）
    bgm: Path
    timing_csv: Path
    report: Path
    total_seconds: float
    segments: tuple[EncodedSegment, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def render_video(
    video: Video,
    out_dir: Path,
    fonts: FontSet,
    style: Style,
    tts: TTSProvider,
    ffmpeg: Ffmpeg,
    *,
    cache_dir: Path | None = None,
    encoder: SegmentEncoder | None = None,
    music_volume: float = DEFAULT_MUSIC_VOLUME,
    estimated: bool = False,
    on_progress: ProgressCallback | None = None,
) -> RenderResult:
    """on_progress(0–1 的進度, 目前在做什麼)：每一步開始前呼叫（產生影片的工作用來回報進度）。"""
    report = on_progress or (lambda progress, message: None)
    cache_dir = cache_dir or video.base_dir / "cache"
    report(0.0, "排版")
    library = AssetLibrary(video)
    layouts = layout_video(video, fonts, style, library)
    ffmpeg.check()

    clips = prepare_narration(
        video,
        tts,
        cache_dir,
        on_clip=lambda i, n: report(_span(NARRATION_SPAN, i - 1, n), f"旁白 {i}／{n}"),
    )
    timeline = build_timeline(video, lambda beat: clips[beat.beat_key].seconds, style)
    renderer = Renderer(video, timeline, layouts, fonts, style, library)
    segments = encode_segments(
        video,
        timeline,
        renderer,
        encoder or FfmpegSegmentEncoder(ffmpeg, style),
        cache_dir,
        style,
        on_segment=lambda i, n, reused: report(
            _span(SEGMENT_SPAN, i - 1, n), f"段影片 {i}／{n}" + ("（沿用）" if reused else "")
        ),
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    joined = cache_dir / "joined.mp4"
    report(0.86, "串接段影片")
    _concat(ffmpeg, [s.path for s in segments], joined, cache_dir)
    silent = out_dir / "silent.mp4"
    report(0.9, "疊上進度條")
    overlay_progress(ffmpeg, joined, silent, timeline, style)

    bgm = out_dir / "bgm.wav"
    starts = tuple(start for _, start, _ in timeline.chapter_spans)
    bgm.write_bytes(to_wav(synthesize_bgm(timeline.total, starts)))

    final = out_dir / f"{safe_file_part(video.game_key)}.mp4"
    report(0.95, "混音")
    _mix(ffmpeg, silent, bgm, _narration_entries(timeline, clips), final, timeline, music_volume)

    timing_csv = out_dir / "timing.csv"
    write_timing_csv(timeline, timing_csv)
    warnings = [w for layout in layouts.values() for w in layout.warnings]
    if fonts.warning:
        warnings.insert(0, fonts.warning)
    if estimated:
        warnings.insert(0, ESTIMATED_NOTE)
    report = out_dir / "report.txt"
    _write_report(report, video, timeline, segments, warnings)
    return RenderResult(
        video=final,
        silent=silent,
        joined=joined,
        bgm=bgm,
        timing_csv=timing_csv,
        report=report,
        total_seconds=timeline.total,
        segments=tuple(segments),
        warnings=tuple(warnings),
    )


def _narration_entries(
    timeline: Timeline, clips: dict[str, NarrationClip]
) -> list[tuple[Path, float]]:
    """每句旁白的音檔與開始秒數（句開始＋前留白）。"""
    entries = []
    for seg in timeline.segments:
        pad = seg.segment.timing.pad_before
        for beat in seg.beats:
            entries.append((clips[beat.beat.beat_key].path, beat.start + pad))
    return entries


def _concat(ffmpeg: Ffmpeg, parts: list[Path], target: Path, cache_dir: Path) -> None:
    """concat demuxer，-c copy 不重新編碼。"""
    listing = cache_dir / "concat.txt"
    lines = []
    for part in parts:
        path = part.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{path}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary = target.with_name(target.stem + ".tmp.mp4")
    _run_to_temporary(
        ffmpeg,
        ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(temporary)],
        temporary,
        target,
        what="串接段影片",
    )  # fmt: skip


def _run_to_temporary(
    ffmpeg: Ffmpeg, args: list[str], temporary: Path, target: Path, *, what: str
) -> None:
    """ffmpeg 先寫暫存檔，成功才改名成正式檔；失敗時刪掉暫存檔再拋錯（#75 審核）。"""
    try:
        ffmpeg.run(args, what=what)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(target)


def mix_filter(delays_ms: list[int], music_volume: float) -> str:
    """混音的濾鏡（依《血與刃》製作紀錄第 8 節）。

    輸入 0：無聲影片；1：背景音樂；2 起：每句旁白。旁白出現時用 sidechaincompress 壓低音樂。
    """
    music = f"[1:a]volume={music_volume:g}[music]"
    if not delays_ms:
        return f"{music};[music]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]"
    voices = [
        f"[{i + 2}:a]adelay=delays={ms}:all=1,aformat=channel_layouts=stereo[v{i}]"
        for i, ms in enumerate(delays_ms)
    ]
    inputs = "".join(f"[v{i}]" for i in range(len(delays_ms)))
    return ";".join(
        [
            *voices,
            # apad：旁白在最後一句後就結束；補上無限長的靜音，sidechain 才會一直延續到片尾。
            # 否則 sidechaincompress 在旁白結束時就停止，背景音樂被截斷（#75 審核）
            f"{inputs}amix=inputs={len(delays_ms)}:normalize=0:duration=longest,"
            "loudnorm=I=-20:TP=-2:LRA=7,apad,asplit=2[voice][sidechain]",
            music,
            "[music][sidechain]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=900[ducked]",
            "[ducked][voice]amix=inputs=2:normalize=0:duration=first,"
            "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]",
        ]
    )


def _mix(
    ffmpeg: Ffmpeg,
    silent: Path,
    bgm: Path,
    narration: list[tuple[Path, float]],
    target: Path,
    timeline: Timeline,
    music_volume: float,
) -> None:
    args = ["-y", "-loglevel", "error", "-i", str(silent), "-i", str(bgm)]
    for path, _ in narration:
        args += ["-i", str(path)]
    delays = [round(start * 1000) for _, start in narration]
    temporary = target.with_name(target.stem + ".tmp.mp4")
    args += [
        "-filter_complex", mix_filter(delays, music_volume),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-t", f"{timeline.total:.3f}", "-movflags", "+faststart",
        str(temporary),
    ]  # fmt: skip
    _run_to_temporary(ffmpeg, args, temporary, target, what="混音")


def _write_report(
    path: Path,
    video: Video,
    timeline: Timeline,
    segments: list[EncodedSegment],
    warnings: list[str],
) -> None:
    encoded = [s.segment_key for s in segments if not s.reused]
    reused = [s.segment_key for s in segments if s.reused]
    lines = [
        f"影片：{video.title}",
        f"總長：{timeline.total:.2f} 秒",
        f"段數：{len(segments)}（重新編碼 {len(encoded)} 段、沿用快取 {len(reused)} 段）",
        f"重新編碼：{'、'.join(encoded) or '無'}",
        f"沿用快取：{'、'.join(reused) or '無'}",
        "",
        PROGRESS_NOTE,
        "",
        "警告：" if warnings else "警告：無",
        *(f"- {w}" for w in warnings),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
