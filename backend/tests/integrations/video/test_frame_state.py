"""句內動作與畫面狀態（spec rules-video-maker「句內動作與畫面狀態」）。

只計算第 t 秒各元素的狀態與位置，不畫圖。
"""

from pathlib import Path

import pytest

from app.integrations.video import (
    DEFAULT_STYLE,
    FontSet,
    Renderer,
    build_timeline,
    frame_at,
    layout_video,
    load_video,
)
from tests.integrations.video.support import base_data, segment, write_game


class Scene:
    def __init__(self, tmp_path: Path, data: dict | None = None) -> None:
        self.video = load_video(write_game(tmp_path, data or base_data()))
        self.timeline = build_timeline(self.video, lambda beat: 3.0, DEFAULT_STYLE)
        self.layouts = layout_video(self.video, FontSet(None, None), DEFAULT_STYLE)

    def cue(self, beat_key: str, index: int):
        beat = next(
            b for s in self.timeline.segments for b in s.beats if b.beat.beat_key == beat_key
        )
        return beat.cues[index]

    def frame(self, t: float):
        return frame_at(self.video, self.timeline, self.layouts, t)

    def segment_start(self, key: str) -> float:
        return next(s.start for s in self.timeline.segments if s.segment.segment_key == key)


def test_hidden_until_show(tmp_path: Path) -> None:
    data = base_data()
    beat = segment(data, "s1")["beats"][1]
    beat["cues"] = [
        {"at": 0.2, "do": "show", "target": "h1"},
        {"at": 0.4, "do": "show", "target": "l1", "anim": "fade"},
    ]
    scene = Scene(tmp_path, data)
    title_cue, h_cue, l_cue = scene.cue("b1", 1), scene.cue("b2", 0), scene.cue("b2", 1)
    early = scene.frame(title_cue.start - 0.05)
    assert early.slots["main_title"].alpha == 0
    assert early.highlights["h1"].alpha == 0 and early.labels["l1"].alpha == 0
    late = scene.frame(l_cue.end + 0.01)
    assert late.slots["main_title"].alpha == 1
    assert late.highlights["h1"].alpha == 1 and late.labels["l1"].alpha == 1
    assert scene.frame(h_cue.end + 0.01).highlights["h1"].alpha == 1


def test_hidden_text_not_drawn(tmp_path: Path) -> None:
    # 回歸測試：Pillow 在 RGB 畫布上畫文字會忽略透明度，隱藏的主體標題曾經被畫出來
    scene = Scene(tmp_path)
    renderer = Renderer(
        scene.video, scene.timeline, scene.layouts, FontSet(None, None), DEFAULT_STYLE
    )
    title_cue = scene.cue("b1", 1)
    rect = scene.layouts["s1"].text_rects["main_title"]
    box = (round(rect.x0), round(rect.y0), round(rect.x1), round(rect.y1))
    gold = DEFAULT_STYLE.gold

    def gold_pixels(t: float) -> int:
        region = renderer.render(t).crop(box)
        return sum(
            1
            for r, g, b in region.get_flattened_data()
            if abs(r - gold[0]) < 40 and abs(g - gold[1]) < 40 and abs(b - gold[2]) < 40
        )

    assert gold_pixels(title_cue.start - 0.05) == 0
    assert gold_pixels(title_cue.end + 0.01) > 0


def test_flip(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    flip = scene.cue("b1", 0)
    before = scene.frame(flip.start - 0.01).items["c1"]
    during = scene.frame(flip.start + (flip.end - flip.start) * 0.25).items["c1"]
    after = scene.frame(flip.end + 0.01).items["c1"]
    assert before.asset_key == "back" and before.rect.w == pytest.approx(after.rect.w)
    assert during.rect.w < before.rect.w
    assert after.asset_key == "red"


def test_shuffle(tmp_path: Path) -> None:
    data = base_data()
    segment(data, "s1")["beats"][0]["cues"] = [
        {"at": 0.2, "do": "shuffle", "target": "main", "duration": 1.0}
    ]
    scene = Scene(tmp_path, data)
    shuffle = scene.cue("b1", 0)
    start = scene.frame(shuffle.start - 0.01).items
    middle = scene.frame((shuffle.start + shuffle.end) / 2).items
    end = scene.frame(shuffle.end + 0.01).items
    for key in ("c1", "c2", "c3"):
        assert middle[key].rect != start[key].rect
        assert end[key].rect == start[key].rect
        assert end[key].asset_key == "back"


def test_hide_keeps_positions(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    hide = scene.cue("b2", 0)
    before = scene.frame(hide.start - 0.01).items
    after = scene.frame(hide.end + 0.01).items
    assert after["c2"].alpha == 0
    assert after["c1"].rect == before["c1"].rect
    assert after["c3"].rect == before["c3"].rect


def test_move_into_region(tmp_path: Path) -> None:
    scene = Scene(tmp_path)
    move = scene.cue("b2", 1)
    region = scene.layouts["s1"].region_rects["sidebar@zone_a"]
    after = scene.frame(move.end + 0.01).items["c1"]
    assert after.rect.inside(region)
    seg_end = scene.segment_start("s2")
    assert scene.frame(seg_end - 0.01).items["c1"].rect == after.rect


def test_state_resets_per_segment(tmp_path: Path) -> None:
    data = base_data()
    # 第 2 段也用同一組牌與盤面，確認前一段的移動、highlight、label 不會帶過來
    s1 = segment(data, "s1")
    s2 = segment(data, "s2")
    s2["slots"] = {k: v for k, v in s1["slots"].items()}
    s2["highlights"] = s1["highlights"]
    s2["labels"] = s1["labels"]
    s2["beats"][0]["cues"] = []
    s1["beats"][1]["cues"].append({"at": 1.2, "do": "show", "target": "h1"})
    s1["beats"][1]["cues"].append({"at": 1.2, "do": "show", "target": "l1"})
    scene = Scene(tmp_path, data)
    start = scene.frame(scene.segment_start("s2") + 0.01)
    assert start.segment_key == "s2"
    assert start.items["c1"].rect == scene.layouts["s2"].item_rects["c1"]
    assert start.items["c1"].asset_key == "back"
    assert start.items["c2"].alpha == 1
    assert start.highlights["h1"].alpha == 0 and start.labels["l1"].alpha == 0
    assert start.slots["main_title"].alpha == 0
