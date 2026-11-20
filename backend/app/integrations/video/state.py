"""句內動作與畫面狀態（spec rules-video-maker「句內動作與畫面狀態」）。

依 cue 算出段內第 t 秒每個槽位、項、highlight、label 的狀態，不涉及位置與畫圖。
狀態以段為範圍：每段開始時重置。
"""

import math
from dataclasses import dataclass, field

from app.integrations.video.model import Asset, Segment, resolve_target
from app.integrations.video.timeline import SegmentTiming


@dataclass
class Visibility:
    alpha: float = 1.0
    scale: float = 1.0


@dataclass
class ItemState:
    face_up: bool
    alpha: float = 1.0
    scale: float = 1.0
    flip_width: float = 1.0  # 翻牌時的寬度比例（1＝原寬）
    shuffle: float = 0.0  # 洗牌偏移強度，0＝在原位
    move_progress: float = 0.0
    move_to: str | None = None  # `<槽位>@<區域>`


@dataclass
class SegmentState:
    slots: dict[str, Visibility] = field(default_factory=dict)
    items: dict[str, ItemState] = field(default_factory=dict)
    highlights: dict[str, Visibility] = field(default_factory=dict)
    labels: dict[str, Visibility] = field(default_factory=dict)


def ease_out_back(p: float) -> float:
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def ease_in_out(p: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * p)


def _progress(t: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0
    return min(1.0, max(0.0, (t - start) / (end - start)))


def _show(vis: Visibility | ItemState, anim: str, p: float) -> None:
    if anim == "fade":
        vis.alpha, vis.scale = p, 1.0
    else:  # pop：快速淡入並帶一點回彈
        vis.alpha = min(1.0, p * 2.5)
        vis.scale = 0.6 + 0.4 * ease_out_back(p) if p < 1 else 1.0


def initial_state(segment: Segment) -> SegmentState:
    state = SegmentState()
    for name, slot in segment.slots.items():
        state.slots[name] = Visibility(alpha=0.0 if slot.hidden else 1.0)
        for item in slot.items:
            state.items[item.item_key] = ItemState(
                face_up=item.back_asset_key is None, alpha=0.0 if item.hidden else 1.0
            )
    for h in segment.highlights:
        state.highlights[h.key] = Visibility(alpha=0.0)
    for lab in segment.labels:
        state.labels[lab.key] = Visibility(alpha=0.0)
    return state


def segment_state(timing: SegmentTiming, assets: dict[str, Asset], t: float) -> SegmentState:
    """t 是全片的絕對秒數；只套用 t 之前開始的 cue。"""
    segment = timing.segment
    state = initial_state(segment)
    cues = sorted((c for b in timing.beats for c in b.cues), key=lambda c: c.start)
    for cue_timing in cues:
        if cue_timing.start > t:
            break
        cue = cue_timing.cue
        p = _progress(t, cue_timing.start, cue_timing.end)
        target = resolve_target(segment, assets, cue.target)
        if target is None:  # 載入時已驗證，不會發生
            continue
        if target.kind == "slot" and cue.do in ("flip", "shuffle"):
            items = [state.items[i.item_key] for i in segment.slots[cue.target].items]
        elif target.kind == "item":
            items = [state.items[target.name or ""]]
        else:
            items = []

        if cue.do == "show":
            if target.kind == "slot":
                _show(state.slots[cue.target], cue.anim, p)
            elif target.kind == "item":
                _show(items[0], cue.anim, p)
            elif target.kind == "highlight":
                _show(state.highlights[cue.target], cue.anim, p)
            elif target.kind == "label":
                _show(state.labels[cue.target], cue.anim, p)
        elif cue.do == "hide":
            vis: Visibility | ItemState
            if target.kind == "item":
                vis = items[0]
            elif target.kind == "highlight":
                vis = state.highlights[cue.target]
            else:
                vis = state.labels[cue.target]
            vis.alpha = 1.0 - p
        elif cue.do == "flip":
            for item in items:
                if p >= 1:
                    item.face_up = not item.face_up
                    item.flip_width = 1.0
                else:
                    item.flip_width = abs(math.cos(math.pi * p))
                    if p >= 0.5:
                        item.face_up = not item.face_up
        elif cue.do == "shuffle":
            for item in items:
                item.shuffle = math.sin(math.pi * p) if p < 1 else 0.0
        elif cue.do == "move":
            items[0].move_to = cue.to
            items[0].move_progress = ease_in_out(p)
    return state
