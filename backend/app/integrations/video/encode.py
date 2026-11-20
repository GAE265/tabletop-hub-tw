"""逐格渲染與段影片快取（spec rules-video-maker「完整影片輸出」）。

每段編成一個 mp4，以 content_hash 快取：段內容、用到的素材檔、風格、字型、各句長度都沒變時直接沿用。
第 1 階段的限制：每段畫面都畫了全片進度條，所以全片或章的長度一變，同一章的段都會重做
（第 2 階段的前置項目會把進度條改成最後才疊上去）。
"""

import dataclasses
import hashlib
import json
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.integrations.video.errors import VideoRenderError
from app.integrations.video.ffmpeg import Ffmpeg, stderr_tail
from app.integrations.video.model import Segment, Video
from app.integrations.video.render import Renderer
from app.integrations.video.stills import safe_file_part
from app.integrations.video.style import Style
from app.integrations.video.timeline import SegmentTiming, Timeline

# 渲染程式本身改變、會讓舊的段影片不再正確時，把這個數字加 1
ENGINE_VERSION = 1


class SegmentEncoder(ABC):
    @abstractmethod
    def encode(self, timing: SegmentTiming, renderer: Renderer, target: Path) -> None:
        """把一段畫成影片寫到 target；失敗時不留下 target。"""


class FfmpegSegmentEncoder(SegmentEncoder):
    """逐格產生 rgb24 → 管線送 ffmpeg（libx264、crf 18、veryfast、yuv420p）→ 先寫暫存檔再改名。"""

    def __init__(self, ffmpeg: Ffmpeg, style: Style) -> None:
        self.ffmpeg = ffmpeg
        self.style = style

    def encode(self, timing: SegmentTiming, renderer: Renderer, target: Path) -> None:
        style = self.style
        temporary = target.with_name(target.stem + ".tmp.mp4")
        args = [
            "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{style.width}x{style.height}", "-r", str(style.fps),
            "-i", "-",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            str(temporary),
        ]  # fmt: skip
        with tempfile.TemporaryFile() as errors:
            process = self.ffmpeg.popen(args, errors)
            try:
                assert process.stdin is not None
                try:
                    for t in frame_times(timing, style.fps):
                        process.stdin.write(renderer.render(t).tobytes())
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass  # ffmpeg 提早結束，下面依結束代碼回報
                code = process.wait()
            except BaseException:
                process.kill()
                process.wait()
                temporary.unlink(missing_ok=True)
                raise
            if code != 0:
                temporary.unlink(missing_ok=True)
                errors.seek(0)
                key = timing.segment.segment_key
                tail = stderr_tail(errors.read())
                raise VideoRenderError(f"ffmpeg 編碼段 {key} 失敗：\n{tail}")
        temporary.replace(target)


def frame_times(timing: SegmentTiming, fps: int) -> list[float]:
    """這一段每一格的時間點。用全片的格數切段，串接後總格數不會因四捨五入而飄移。"""
    first, last = round(timing.start * fps), round(timing.end * fps)
    upper = timing.end - 1e-6
    return [min(max(i / fps, timing.start), upper) for i in range(first, last)]


@dataclass(frozen=True)
class EncodedSegment:
    segment_key: str
    path: Path
    reused: bool


def encode_segments(
    video: Video,
    timeline: Timeline,
    renderer: Renderer,
    encoder: SegmentEncoder,
    cache_dir: Path,
    style: Style,
) -> list[EncodedSegment]:
    """依序取得每段的影片：快取裡有相同 content_hash 的就沿用，否則重新編碼。"""
    folder = cache_dir / "segments"
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for timing in timeline.segments:
        key = timing.segment.segment_key
        prefix = safe_file_part(key)
        path = (
            folder / f"{prefix}_{segment_hash(video, timing, timeline, style, renderer)[:16]}.mp4"
        )
        reused = path.is_file()
        if not reused:
            encoder.encode(timing, renderer, path)
            if not path.is_file():
                raise VideoRenderError(f"段 {key} 編碼後沒有產生影片檔")
            for old in folder.glob(f"{prefix}_*.mp4"):
                if old != path and not old.name.endswith(".tmp.mp4"):
                    old.unlink()
        results.append(EncodedSegment(key, path, reused))
    return results


def segment_hash(
    video: Video, timing: SegmentTiming, timeline: Timeline, style: Style, renderer: Renderer
) -> str:
    """段影片的內容雜湊：任何會改變這段畫面的東西都算進來。"""
    segment = timing.segment
    payload = {
        "engine": ENGINE_VERSION,
        "segment": _segment_data(segment),
        "chapter": dataclasses.asdict(video.chapter(segment.chapter_key)),
        "title": video.title,
        "assets": {key: _asset_digest(video, key) for key in sorted(_asset_keys(segment))},
        "beats": [
            {
                "start": round(b.start - timing.start, 4),
                "duration": round(b.duration, 4),
                "cues": [round(c.start - timing.start, 4) for c in b.cues],
            }
            for b in timing.beats
        ],
        "duration": round(timing.duration, 4),
        # 進度條：依全片長度與各章範圍畫出（第 1 階段的限制）
        "progress": {
            "start": round(timing.start, 4),
            "total": round(timeline.total, 4),
            "chapters": [[k, round(s, 4), round(e, 4)] for k, s, e in timeline.chapter_spans],
        },
        "style": dataclasses.asdict(style),
        "fonts": renderer.fonts.cache_key,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _segment_data(segment: Segment) -> dict:
    data = dataclasses.asdict(segment)
    # 狀態與修改紀錄不影響畫面
    data.pop("state", None)
    data.pop("revisions", None)
    return data


def _asset_keys(segment: Segment) -> set[str]:
    keys = set()
    for slot in segment.slots.values():
        if slot.asset_key:
            keys.add(slot.asset_key)
        for item in slot.items:
            keys.add(item.asset_key)
            if item.back_asset_key:
                keys.add(item.back_asset_key)
    return keys


def _asset_digest(video: Video, asset_key: str) -> dict:
    asset = video.assets[asset_key]
    digest = hashlib.sha256(video.asset_path(asset_key).read_bytes()).hexdigest()
    return {"file": digest, "asset": dataclasses.asdict(asset)}
