"""靜態圖與對照圖（spec rules-video-maker「本機指令與靜態圖」）。

每句開始後 0.8 秒一張、每個 cue 完成時一張（標題字卡一張），另拼成一張對照圖。
不需要 ffmpeg；旁白長度由呼叫端提供（沒有 TTS 時用估計值）。
"""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from app.integrations.video.assets import AssetLibrary
from app.integrations.video.fonts import FontSet
from app.integrations.video.layout import layout_video
from app.integrations.video.model import Video
from app.integrations.video.render import Renderer
from app.integrations.video.style import DEFAULT_STYLE, Style
from app.integrations.video.timeline import (
    NarrationSeconds,
    Timeline,
    build_timeline,
    estimate_narration_seconds,
    write_timing_csv,
)

BEAT_STILL_OFFSET = 0.8
SHEET_THUMB = (480, 270)
SHEET_COLUMNS = 4
SHEET_CAPTION = 30


@dataclass(frozen=True)
class StillsResult:
    stills: tuple[Path, ...]
    sheet: Path
    timing_csv: Path
    report: Path
    warnings: tuple[str, ...]
    total_seconds: float


_UNSAFE = re.compile(r'[\\/:*?"<>|\s]+')


def safe_file_part(text: str) -> str:
    """把 key 轉成可以放進檔名的字串：路徑分隔字元、Windows 不允許的字元與空白改成「-」。"""
    return _UNSAFE.sub("-", text).strip("-.") or "_"


def still_times(timeline: Timeline) -> list[tuple[float, str]]:
    """依時間排序；同一時間點（例如同時開始、同樣長度的兩個 cue）只留第一張。"""
    times: list[tuple[float, str]] = []
    for seg in timeline.segments:
        key = seg.segment.segment_key
        if not seg.beats:
            times.append((seg.start + seg.duration / 2, key))
        for beat in seg.beats:
            times.append(
                (
                    min(beat.start + BEAT_STILL_OFFSET, beat.end - 0.01),
                    f"{key}_{beat.beat.beat_key}",
                )
            )
            for n, cue in enumerate(beat.cues, start=1):
                t = min(cue.end + 0.02, seg.end - 0.01)
                times.append((t, f"{key}_{beat.beat.beat_key}_cue{n}"))
    unique: list[tuple[float, str]] = []
    for t, tag in sorted(times, key=lambda pair: pair[0]):
        if not unique or abs(t - unique[-1][0]) > 1e-6:
            unique.append((t, tag))
    return unique


def render_stills(
    video: Video,
    out_dir: Path,
    fonts: FontSet,
    style: Style = DEFAULT_STYLE,
    narration_seconds: NarrationSeconds | None = None,
) -> StillsResult:
    """先排好所有段（放不下就在輸出任何檔案前失敗），再輸出靜態圖、對照圖與時間報表。"""
    library = AssetLibrary(video)
    layouts = layout_video(video, fonts, style, library)
    timeline = build_timeline(
        video,
        narration_seconds or (lambda beat: estimate_narration_seconds(beat.narration)),
        style,
    )
    renderer = Renderer(video, timeline, layouts, fonts, style, library)

    # 先輸出到暫存資料夾，全部成功才換掉舊圖；中途失敗時舊圖保持原樣
    stills_dir = out_dir / "stills"
    staging = out_dir / "stills.tmp"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    names: list[str] = []
    captions: list[str] = []
    try:
        for n, (t, tag) in enumerate(still_times(timeline), start=1):
            name = f"{n:03d}_{safe_file_part(tag)}_{t:06.2f}s.png"
            renderer.render(t).save(staging / name)
            names.append(name)
            captions.append(f"{t:6.2f}s  {tag}")
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(stills_dir, ignore_errors=True)
    staging.rename(stills_dir)
    paths = [stills_dir / name for name in names]

    sheet = out_dir / "sheet.png"
    _write_sheet(paths, captions, sheet, fonts)
    timing_csv = out_dir / "timing.csv"
    write_timing_csv(timeline, timing_csv)

    warnings = [w for layout in layouts.values() for w in layout.warnings]
    if fonts.warning:
        warnings.insert(0, fonts.warning)
    report = out_dir / "report.txt"
    lines = [
        f"影片：{video.title}",
        f"總長（旁白為估計值）：{timeline.total:.2f} 秒",
        f"段數：{len(video.segments)}，靜態圖：{len(paths)} 張",
        "",
        "警告：" if warnings else "警告：無",
        *(f"- {w}" for w in warnings),
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return StillsResult(tuple(paths), sheet, timing_csv, report, tuple(warnings), timeline.total)


def _write_sheet(paths: list[Path], captions: list[str], target: Path, fonts: FontSet) -> None:
    tw, th = SHEET_THUMB
    rows = max(1, (len(paths) + SHEET_COLUMNS - 1) // SHEET_COLUMNS)
    cols = min(SHEET_COLUMNS, max(1, len(paths)))
    sheet = Image.new("RGB", (cols * tw, rows * (th + SHEET_CAPTION)), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    font = fonts.get(18)
    for i, (path, caption) in enumerate(zip(paths, captions, strict=True)):
        x, y = (i % SHEET_COLUMNS) * tw, (i // SHEET_COLUMNS) * (th + SHEET_CAPTION)
        with Image.open(path) as still:
            sheet.paste(still.resize(SHEET_THUMB, Image.Resampling.LANCZOS), (x, y))
        draw.text((x + 8, y + th + 4), caption, font=font, fill=(220, 220, 220))
    sheet.save(target)
