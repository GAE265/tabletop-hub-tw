"""規則影片的版型引擎（spec：openspec/changes/add-rules-video-maker/specs/rules-video-maker）。

用宣告式的段資料描述影片，依版型排版、依句內動作計算畫面狀態並畫出畫面。
不知道任何遊戲或 domain；設定值由呼叫方傳入，不讀 Settings。
"""

from app.integrations.video.compose import Frame, PlacedItem, frame_at
from app.integrations.video.errors import (
    FontConfigError,
    LayoutError,
    VideoDataError,
    VideoError,
    VideoRenderError,
    VideoTimeoutError,
)
from app.integrations.video.fonts import FontSet
from app.integrations.video.geometry import Rect
from app.integrations.video.layout import SegmentLayout, layout_video
from app.integrations.video.model import Video, load_video, parse_video
from app.integrations.video.render import Renderer
from app.integrations.video.stills import StillsResult, render_stills, still_times
from app.integrations.video.style import DEFAULT_STYLE, Style
from app.integrations.video.timeline import (
    Timeline,
    build_timeline,
    estimate_narration_seconds,
    write_timing_csv,
)

__all__ = [
    "DEFAULT_STYLE",
    "FontConfigError",
    "FontSet",
    "Frame",
    "LayoutError",
    "PlacedItem",
    "Rect",
    "Renderer",
    "SegmentLayout",
    "StillsResult",
    "Style",
    "Timeline",
    "Video",
    "VideoDataError",
    "VideoError",
    "VideoRenderError",
    "VideoTimeoutError",
    "build_timeline",
    "estimate_narration_seconds",
    "frame_at",
    "layout_video",
    "load_video",
    "parse_video",
    "render_stills",
    "still_times",
    "write_timing_csv",
]
