"""main_with_sidebar 版型的排版（spec rules-video-maker「main_with_sidebar 版型」）。

字型一律用 Pillow 內建字型（CI 沒有中文字型），文字只用英數。
"""

from pathlib import Path
from typing import Any

import pytest

from app.integrations.video import (
    DEFAULT_STYLE,
    FontSet,
    LayoutError,
    build_timeline,
    estimate_narration_seconds,
    layout_video,
    load_video,
)
from app.integrations.video.fonts import text_width
from app.integrations.video.layout import subtitle_box
from tests.integrations.video.support import base_data, segment, write_game

STYLE = DEFAULT_STYLE
FONTS = FontSet(None, None)


def _layouts(tmp_path: Path, data: dict[str, Any], sizes: dict[str, tuple[int, int]] | None = None):
    video = load_video(write_game(tmp_path, data, sizes))
    return video, layout_video(video, FONTS, STYLE)


def _sidebar_as_text(data: dict[str, Any], slot: dict[str, Any]) -> dict[str, Any]:
    """把 s1 的側欄換成文字；原本指向盤面區域的 highlight 與 move 一併移除。"""
    s1 = segment(data, "s1")
    s1["slots"]["sidebar"] = slot
    s1["highlights"] = []
    s1["beats"][1]["cues"] = [c for c in s1["beats"][1]["cues"] if c["do"] != "move"]
    return data


def test_main_and_sidebar_inside_content(tmp_path: Path) -> None:
    _, layouts = _layouts(tmp_path, base_data())
    lay = layouts["s1"]
    main, sidebar = lay.slot_rects["main"], lay.slot_rects["sidebar"]
    assert not main.intersects(sidebar)
    assert main.inside(lay.content) and sidebar.inside(lay.content)
    assert lay.image_rects["sidebar"].inside(sidebar)
    # 內容區不壓到左上章節標籤與下方字幕列
    assert lay.content.y0 >= STYLE.header_rect.y1
    assert lay.content.y1 <= STYLE.subtitle_top


def test_main_expands_without_sidebar(tmp_path: Path) -> None:
    _, layouts = _layouts(tmp_path, base_data())
    lay = layouts["s2"]
    assert "sidebar" not in lay.slot_rects
    assert lay.slot_rects["main"] == lay.content


def test_sidebar_text_fits(tmp_path: Path) -> None:
    data = _sidebar_as_text(
        base_data(),
        {
            "kind": "bullets",
            "title": "Rules",
            "items": ["Keep at most two cards", "Reveal at the same time"],
        },
    )
    _, layouts = _layouts(tmp_path, data)
    lay = layouts["s1"]
    assert lay.text_rects["sidebar"].inside(lay.slot_rects["sidebar"])


@pytest.mark.parametrize("count", [2, 3])
def test_items_row_layout(tmp_path: Path, count: int) -> None:
    data = base_data()
    items = segment(data, "s1")["slots"]["main"]["items"][:count]
    segment(data, "s1")["slots"]["main"]["items"] = items
    # 被刪掉的項不能再被 cue 或 label 指到
    if count == 2:
        segment(data, "s1")["beats"][1]["cues"] = []
    _, layouts = _layouts(tmp_path, data)
    lay = layouts["s1"]
    rects = [lay.item_rects[item["item_key"]] for item in items]
    heights = {round(r.h, 3) for r in rects}
    assert len(heights) == 1
    gaps = [round(b.x0 - a.x1, 3) for a, b in zip(rects, rects[1:], strict=False)]
    assert len(set(gaps)) == 1 and gaps[0] > 0
    area = lay.slot_rects["main"]
    row_center = (rects[0].x0 + rects[-1].x1) / 2
    assert abs(row_center - area.center[0]) <= 1
    assert all(r.inside(area) for r in rects)


def test_main_title_above_items(tmp_path: Path) -> None:
    _, layouts = _layouts(tmp_path, base_data())
    lay = layouts["s1"]
    title = lay.text_rects["main_title"]
    assert title.inside(lay.slot_rects["main"])
    assert all(title.y1 <= r.y0 for r in lay.item_rects.values())


def test_region_follows_scaled_image(tmp_path: Path) -> None:
    data = base_data()
    # 同一張盤面：s1 縮在側欄、s2 放大成整個內容區
    segment(data, "s2")["slots"]["main"] = {"kind": "asset", "asset_key": "board"}
    _, layouts = _layouts(tmp_path, data)
    for key, slot in (("s1", "sidebar"), ("s2", "main")):
        image = layouts[key].image_rects[slot]
        region = layouts[key].region_rects[f"{slot}@zone_b"]
        assert abs(region.x0 - (image.x0 + 0.5 * image.w)) <= 2
        assert abs(region.y0 - (image.y0 + 0.5 * image.h)) <= 2
        assert abs(region.w - 0.5 * image.w) <= 2
    assert layouts["s1"].image_rects["sidebar"].w != layouts["s2"].image_rects["main"].w


def test_label_below_item(tmp_path: Path) -> None:
    _, layouts = _layouts(tmp_path, base_data())
    lay = layouts["s1"]
    label, item = lay.label_rects["l1"], lay.item_rects["c2"]
    assert label.y0 >= item.y1
    assert abs(label.center[0] - item.center[0]) <= 1
    assert label.inside(lay.content)


def test_text_overflow_rejected(tmp_path: Path) -> None:
    data = _sidebar_as_text(base_data(), {"kind": "text", "text": "word " * 3000})
    video = load_video(write_game(tmp_path, data))
    with pytest.raises(LayoutError) as exc:
        layout_video(video, FONTS, STYLE)
    assert "s1" in str(exc.value) and "sidebar" in str(exc.value)


def test_orientation_applied(tmp_path: Path) -> None:
    data = base_data()
    data["assets"][1]["orientation"] = 90  # red：100×160 直放 → 擺正後是橫的
    _, layouts = _layouts(tmp_path, data)
    image = layouts["s2"].image_rects["main"]
    assert image.w > image.h
    assert abs(image.w / image.h - 160 / 100) < 0.02


def test_low_resolution_warning(tmp_path: Path) -> None:
    _, layouts = _layouts(tmp_path, base_data(), sizes={"red.png": (20, 32)})
    warnings = " ".join(layouts["s2"].warnings)
    assert "red" in warnings and "2 倍" in warnings
    assert layouts["s2"].image_rects["main"].w > 40  # 照常排版


def test_title_card(tmp_path: Path) -> None:
    data = base_data()
    data["segments"].insert(0, {"segment_key": "t0", "chapter_key": "c1", "template": "title_card"})
    video, layouts = _layouts(tmp_path, data)
    assert layouts["t0"].slot_rects == {}
    timeline = build_timeline(video, lambda beat: estimate_narration_seconds(beat.narration), STYLE)
    assert timeline.segments[0].duration == pytest.approx(3.0)
    assert timeline.segments[0].beats == ()


# --- #71 審核修正 ---


@pytest.mark.parametrize("lines", [1, 2])
def test_subtitle_box_never_covers_content(lines: int) -> None:
    box = subtitle_box(STYLE, lines)
    assert box.y0 >= STYLE.content_rect.y1
    assert box.y1 <= STYLE.progress_rect.y0


def test_two_line_subtitle_fits(tmp_path: Path) -> None:
    data = base_data()
    # 量字寬組出約 1.5 倍最大寬度的字幕，一定會斷成兩行
    font = FONTS.get(STYLE.subtitle_size)
    text = "word"
    while text_width(font, text) < STYLE.subtitle_max_width * 1.5:
        text += " word"
    segment(data, "s2")["beats"][0]["subtitle"] = text
    video, layouts = _layouts(tmp_path, data)
    assert len(layouts["s2"].subtitle_lines["b3"]) == 2


def test_subtitle_over_two_lines_rejected(tmp_path: Path) -> None:
    data = base_data()
    segment(data, "s2")["beats"][0]["subtitle"] = "word " * 300
    video = load_video(write_game(tmp_path, data))
    with pytest.raises(LayoutError) as exc:
        layout_video(video, FONTS, STYLE)
    message = str(exc.value)
    assert "s2" in message and "b3" in message and "兩行" in message


def test_region_with_crop_maps_from_original_image(tmp_path: Path) -> None:
    data = base_data()
    s1 = segment(data, "s1")
    # 只顯示盤面右下四分之一；zone_b 正好是右下四分之一，換算後應該等於整張裁切後的圖
    s1["slots"]["sidebar"]["crop"] = [0.5, 0.5, 0.5, 0.5]
    s1["highlights"] = [{"key": "h1", "target": "sidebar@zone_b", "shape": "box"}]
    s1["beats"][1]["cues"] = [
        {"at": 1.0, "do": "move", "target": "main.c1", "to": "sidebar@zone_b"}
    ]
    _, layouts = _layouts(tmp_path, data)
    image = layouts["s1"].image_rects["sidebar"]
    region = layouts["s1"].region_rects["sidebar@zone_b"]
    for a, b in (
        (region.x0, image.x0),
        (region.y0, image.y0),
        (region.x1, image.x1),
        (region.y1, image.y1),
    ):
        assert abs(a - b) <= 2
