"""逐格渲染與段影片快取（spec rules-video-maker「完整影片輸出」）。

每段編成一個 mp4，以 content_hash 快取：段內容、用到的素材檔、風格、字型、各句長度都沒變時直接沿用。
段影片不含進度條（串接後才由 progress.py 疊上去），所以全片長度或其他段改變，不會讓這段重做
（第 2 階段 add-rules-video-revision D1）。
"""

import dataclasses
import glob
import hashlib
import json
import tempfile
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
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
# 2：段影片不再畫進度條（第 2 階段）
ENGINE_VERSION = 2

# 段影片的編碼設定（libx264、crf 18、veryfast、yuv420p）
SEGMENT_VIDEO_ARGS = ("-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p")


class SegmentEncoder(ABC):
    @abstractmethod
    def encode(self, timing: SegmentTiming, renderer: Renderer, target: Path) -> None:
        """把一段畫成影片寫到 target；失敗時不留下 target。"""


class FfmpegSegmentEncoder(SegmentEncoder):
    """逐格產生 rgb24 → 管線送 ffmpeg（SEGMENT_VIDEO_ARGS）→ 先寫暫存檔再改名。段影片不畫進度條。"""

    def __init__(self, ffmpeg: Ffmpeg, style: Style) -> None:
        self.ffmpeg = ffmpeg
        self.style = style

    def encode(self, timing: SegmentTiming, renderer: Renderer, target: Path) -> None:
        style = self.style
        args = [
            "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{style.width}x{style.height}", "-r", str(style.fps),
            "-i", "-",
            *SEGMENT_VIDEO_ARGS,
        ]  # fmt: skip
        frames = (
            renderer.render(t, progress=False).tobytes() for t in frame_times(timing, style.fps)
        )
        pipe_frames(self.ffmpeg, args, frames, target, what=f"編碼段 {timing.segment.segment_key} ")


def pipe_frames(
    ffmpeg: Ffmpeg, args: list[str], frames: Iterable[bytes], target: Path, *, what: str
) -> None:
    """把逐格畫面從標準輸入送進 ffmpeg，輸出先寫暫存檔，成功才改名成 target。

    args 不含輸出路徑（這裡補上暫存檔）。失敗時不留下暫存檔，拋 VideoRenderError。
    """
    temporary = target.with_name(target.stem + ".tmp.mp4")
    with tempfile.TemporaryFile() as errors:
        process = ffmpeg.popen([*args, str(temporary)], errors)
        # 逾時：時間到就結束子程序（寫入畫面卡在管線時也會因此解開）
        timed_out = threading.Event()

        def stop() -> None:
            timed_out.set()
            process.kill()

        watchdog = (
            threading.Timer(ffmpeg.timeout_seconds, stop)
            if ffmpeg.timeout_seconds is not None
            else None
        )
        if watchdog is not None:
            watchdog.daemon = True
            watchdog.start()
        try:
            assert process.stdin is not None
            try:
                for frame in frames:
                    if timed_out.is_set():
                        break
                    process.stdin.write(frame)
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass  # ffmpeg 提早結束，下面依結束代碼回報
            code = process.wait()
        except BaseException:
            process.kill()
            process.wait()
            temporary.unlink(missing_ok=True)
            raise
        finally:
            if watchdog is not None:
                watchdog.cancel()
        if timed_out.is_set():
            temporary.unlink(missing_ok=True)
            raise ffmpeg.timeout_error(what)
        if code != 0:
            temporary.unlink(missing_ok=True)
            errors.seek(0)
            raise VideoRenderError(f"ffmpeg {what}失敗：\n{stderr_tail(errors.read())}")
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
    content_hash: str = ""  # 段影片的完整內容雜湊（修改流程記在段的 state.content_hash）


def encode_segments(
    video: Video,
    timeline: Timeline,
    renderer: Renderer,
    encoder: SegmentEncoder,
    cache_dir: Path,
    style: Style,
    *,
    on_segment: Callable[[int, int, bool], None] | None = None,
) -> list[EncodedSegment]:
    """依序取得每段的影片：快取裡有相同 content_hash 的就沿用，否則重新編碼。

    on_segment(第幾段, 共幾段, 是否沿用快取)：每段開始前呼叫，給進度回報用。
    """
    folder = cache_dir / "segments"
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    total = len(timeline.segments)
    for index, timing in enumerate(timeline.segments, start=1):
        key = timing.segment.segment_key
        # 檔名＝安全檔名＋key 的短雜湊＋內容雜湊。key 的短雜湊讓「開頭相同」（s1 與 s1_2）
        # 或「轉成檔名後相同」（s/1 與 s-1）的段各有自己的檔名前綴，清舊快取時不會互刪（#75 審核）
        key_id = hashlib.sha256(key.encode()).hexdigest()[:8]
        prefix = f"{safe_file_part(key)}__{key_id}__"
        full_hash = segment_hash(video, timing, style, renderer)
        path = folder / f"{prefix}{full_hash[:16]}.mp4"
        reused = path.is_file()
        if on_segment is not None:
            on_segment(index, total, reused)
        if not reused:
            encoder.encode(timing, renderer, path)
            if not path.is_file():
                raise VideoRenderError(f"段 {key} 編碼後沒有產生影片檔")
            for old in folder.glob(f"{glob.escape(prefix)}*.mp4"):
                if old != path and not old.name.endswith(".tmp.mp4"):
                    old.unlink()
        results.append(EncodedSegment(key, path, reused, full_hash))
    return results


def segment_hash(video: Video, timing: SegmentTiming, style: Style, renderer: Renderer) -> str:
    """段影片的內容雜湊：任何會改變這段畫面的東西都算進來。

    不含全片長度、這段的開始秒數與各章範圍：進度條串接後才疊上去，這段的畫面與它們無關。
    """
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
