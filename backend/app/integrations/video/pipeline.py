"""完整影片輸出（spec rules-video-maker「完整影片輸出」）。

順序：排版（放不下就在任何輸出前失敗）→ 確認 ffmpeg → 合成旁白（快取）→ 依實際長度算時間軸
→ 逐段編碼（快取）→ 串接成無聲版 → 合成背景音樂 → 混音（旁白出現時壓低音樂）。
"""

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
from app.integrations.video.render import Renderer
from app.integrations.video.stills import safe_file_part
from app.integrations.video.style import Style
from app.integrations.video.timeline import Timeline, build_timeline, write_timing_csv

DEFAULT_MUSIC_VOLUME = 0.25
ESTIMATED_NOTE = "時間為估計值：未設定文字轉語音（TTS_PROVIDER），旁白為靜音，每句長度依字數估計"
PROGRESS_NOTE = (
    "段快取的限制（第 1 階段）：每段畫面都畫了全片進度條，旁白長度一變，同一章的段都會重新編碼"
)


@dataclass(frozen=True)
class RenderResult:
    video: Path
    silent: Path
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
) -> RenderResult:
    cache_dir = cache_dir or video.base_dir / "cache"
    library = AssetLibrary(video)
    layouts = layout_video(video, fonts, style, library)
    ffmpeg.check()

    clips = prepare_narration(video, tts, cache_dir)
    timeline = build_timeline(video, lambda beat: clips[beat.beat_key].seconds, style)
    renderer = Renderer(video, timeline, layouts, fonts, style, library)
    segments = encode_segments(
        video,
        timeline,
        renderer,
        encoder or FfmpegSegmentEncoder(ffmpeg, style),
        cache_dir,
        style,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    silent = out_dir / "silent.mp4"
    _concat(ffmpeg, [s.path for s in segments], silent, cache_dir)

    bgm = out_dir / "bgm.wav"
    starts = tuple(start for _, start, _ in timeline.chapter_spans)
    bgm.write_bytes(to_wav(synthesize_bgm(timeline.total, starts)))

    final = out_dir / f"{safe_file_part(video.game_key)}.mp4"
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
    ffmpeg.run(
        ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(temporary)],
        what="串接段影片",
    )  # fmt: skip
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
    ffmpeg.run(args, what="混音")
    temporary.replace(target)


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
