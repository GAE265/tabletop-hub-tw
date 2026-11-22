"""把第 t 秒的狀態與排版合在一起：每個元素在畫面上的位置、透明度、顯示正面或背面。

不畫圖，方便測試；render.py 依這個結果畫出畫面。
"""

from dataclasses import dataclass

from app.integrations.video.geometry import Rect, fit
from app.integrations.video.layout import SegmentLayout
from app.integrations.video.model import Video
from app.integrations.video.state import ItemState, Visibility, segment_state
from app.integrations.video.style import DEFAULT_STYLE, Style
from app.integrations.video.timeline import BeatTiming, SegmentTiming, Timeline


@dataclass(frozen=True)
class PlacedItem:
    item_key: str
    slot: str
    asset_key: str  # 目前顯示的面（正面或背面）
    rect: Rect
    alpha: float
    moving: bool  # 正在移動或已移進區域：畫在側欄之上


@dataclass(frozen=True)
class Frame:
    t: float
    segment: SegmentTiming
    beat: BeatTiming | None  # 標題字卡沒有句
    layout: SegmentLayout
    slots: dict[str, Visibility]
    items: dict[str, PlacedItem]
    highlights: dict[str, Visibility]
    labels: dict[str, Visibility]

    @property
    def segment_key(self) -> str:
        return self.segment.segment.segment_key

    @property
    def local_t(self) -> float:
        return self.t - self.segment.start


def frame_at(
    video: Video,
    timeline: Timeline,
    layouts: dict[str, SegmentLayout],
    t: float,
    style: Style = DEFAULT_STYLE,
) -> Frame:
    seg_timing = timeline.segment_at(t)
    segment = seg_timing.segment
    layout = layouts[segment.segment_key]
    state = segment_state(seg_timing, video.assets, t)
    last_beat = seg_timing.beats[-1] if seg_timing.beats else None
    beat = next((b for b in seg_timing.beats if t < b.end), last_beat)

    items: dict[str, PlacedItem] = {}
    for name, slot in segment.slots.items():
        if slot.kind != "items":
            continue
        rects = [layout.item_rects[i.item_key] for i in slot.items]
        row_cx = (rects[0].x0 + rects[-1].x1) / 2 if rects else 0.0
        for index, item in enumerate(slot.items):
            item_state = state.items[item.item_key]
            rect = _item_rect(
                layout, layout.item_rects[item.item_key], item_state, index, row_cx, style
            )
            face = item.asset_key if item_state.face_up else (item.back_asset_key or item.asset_key)
            items[item.item_key] = PlacedItem(
                item_key=item.item_key,
                slot=name,
                asset_key=face,
                rect=rect,
                alpha=item_state.alpha * state.slots[name].alpha,
                moving=item_state.move_to is not None,
            )
    return Frame(
        t=t,
        segment=seg_timing,
        beat=beat,
        layout=layout,
        slots=state.slots,
        items=items,
        highlights=state.highlights,
        labels=state.labels,
    )


def _item_rect(
    layout: SegmentLayout, home: Rect, state: ItemState, index: int, row_cx: float, style: Style
) -> Rect:
    rect = home
    if state.shuffle:
        # 洗牌：往整排中心聚攏，並上下交錯，結束時回到原位
        dx = (row_cx - home.center[0]) * 0.85 * state.shuffle
        dy = (1 if index % 2 == 0 else -1) * 0.12 * home.h * state.shuffle
        rect = rect.translate(dx, dy)
    if state.move_to is not None:
        region = layout.region_rects[state.move_to]
        inset = region.inset(region.w * style.move_inset_ratio, region.h * style.move_inset_ratio)
        destination = fit((home.w, home.h), inset)
        rect = rect.lerp(destination, state.move_progress)
    if state.scale != 1.0:
        cx, cy = rect.center
        half_w, half_h = rect.w * state.scale / 2, rect.h * state.scale / 2
        rect = Rect(cx - half_w, cy - half_h, cx + half_w, cy + half_h)
    if state.flip_width != 1.0:
        rect = rect.scale_width(max(state.flip_width, 0.02))
    return rect
