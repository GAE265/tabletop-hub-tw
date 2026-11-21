"""串接後疊上進度條（spec rules-video-revision「進度條最後才疊上去」，第 2 階段 MR 1）。

段影片不含進度條；串接成整支影片後，逐格畫出只有進度條那一條的 RGBA 圖，
從標準輸入送進 ffmpeg，用 overlay 疊到對應位置。疊加需要重新編碼整支影片一次。
"""

from collections.abc import Iterator
from pathlib import Path

from app.integrations.video.encode import frame_times, pipe_frames
from app.integrations.video.ffmpeg import Ffmpeg
from app.integrations.video.render import progress_box, progress_strip
from app.integrations.video.style import Style
from app.integrations.video.timeline import Timeline

# 疊加這一步的編碼設定（MR 說明列出）。依本機量測決定，見 add-rules-video-revision design.md D1
OVERLAY_VIDEO_ARGS = ("-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p")


def video_frame_times(timeline: Timeline, fps: int) -> list[float]:
    """整支影片每一格的時間點，和逐段編碼時切的格完全一致。"""
    return [t for segment in timeline.segments for t in frame_times(segment, fps)]


def overlay_progress(
    ffmpeg: Ffmpeg, source: Path, target: Path, timeline: Timeline, style: Style
) -> None:
    """把進度條疊到串接好的影片 source 上，寫到 target；失敗時不留下暫存檔與 target。"""
    x, y, w, h = progress_box(style)
    args = [
        "-y", "-loglevel", "error",
        "-i", str(source),
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", str(style.fps),
        "-i", "-",
        "-filter_complex", f"[0:v][1:v]overlay={x}:{y}:eof_action=pass[v]",
        "-map", "[v]",
        *OVERLAY_VIDEO_ARGS,
    ]  # fmt: skip
    pipe_frames(ffmpeg, args, _strips(timeline, style), target, what="疊加進度條")


def _strips(timeline: Timeline, style: Style) -> Iterator[bytes]:
    for t in video_frame_times(timeline, style.fps):
        yield progress_strip(timeline, style, t).tobytes()
