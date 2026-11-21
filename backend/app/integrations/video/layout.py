"""版型排版（spec rules-video-maker「main_with_sidebar 版型」）。

所有位置都由內容區、槽位與圖片實際貼上的位置算出，不用絕對座標，所以不會因縮放而漂移。
區域、highlight、label、move 的目的地都依圖片實際貼上的位置換算。
"""

from dataclasses import dataclass, field

from app.integrations.video.assets import AssetLibrary
from app.integrations.video.errors import LayoutError
from app.integrations.video.fonts import Font, FontSet, text_width, wrap
from app.integrations.video.geometry import Rect, fit
from app.integrations.video.model import Segment, Slot, Video, region_in_crop, resolve_target
from app.integrations.video.style import SUBTITLE_PADDING, Style

LINE_HEIGHT = 1.4
SUBTITLE_BREAKS = "，。；：、！？,.;:!?"


@dataclass(frozen=True)
class TextBlock:
    rect: Rect
    lines: tuple[str, ...]
    size: int
    bold: bool = False
    title_lines: tuple[str, ...] = ()
    title_size: int = 0
    emphasis: tuple[str, ...] = ()


@dataclass(frozen=True)
class LabelBox:
    rect: Rect
    text: str
    size: int
    style: str


@dataclass
class SegmentLayout:
    segment_key: str
    content: Rect
    slot_rects: dict[str, Rect] = field(default_factory=dict)
    image_rects: dict[str, Rect] = field(default_factory=dict)  # asset 槽位實際貼上的圖片
    item_rects: dict[str, Rect] = field(default_factory=dict)
    region_rects: dict[str, Rect] = field(default_factory=dict)  # key：`<槽位>@<區域>`
    texts: dict[str, TextBlock] = field(default_factory=dict)
    highlight_rects: dict[str, Rect] = field(default_factory=dict)
    labels: dict[str, LabelBox] = field(default_factory=dict)
    # 每一句字幕斷好的行（key：beat_key），畫圖時直接使用
    subtitle_lines: dict[str, tuple[str, ...]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def text_rects(self) -> dict[str, Rect]:
        return {name: block.rect for name, block in self.texts.items()}

    @property
    def label_rects(self) -> dict[str, Rect]:
        return {key: box.rect for key, box in self.labels.items()}


def layout_video(
    video: Video, fonts: FontSet, style: Style, library: AssetLibrary | None = None
) -> dict[str, SegmentLayout]:
    """排好每一段；任何一段放不下就拋 LayoutError（在輸出任何圖片之前）。"""
    library = library or AssetLibrary(video)
    return {
        seg.segment_key: layout_segment(video, seg, fonts, style, library) for seg in video.segments
    }


def layout_segment(
    video: Video, segment: Segment, fonts: FontSet, style: Style, library: AssetLibrary
) -> SegmentLayout:
    layout = SegmentLayout(segment.segment_key, style.content_rect)
    _layout_subtitles(layout, segment, fonts, style)
    if segment.template == "title_card":
        return layout

    content = style.content_rect
    if "sidebar" in segment.slots:
        sidebar_w = content.w * style.sidebar_ratio
        sidebar = Rect(content.x1 - sidebar_w, content.y0, content.x1, content.y1)
        main = Rect(content.x0, content.y0, sidebar.x0 - style.sidebar_gap, content.y1)
        layout.slot_rects["sidebar"] = sidebar
    else:
        main = content
    layout.slot_rects["main"] = main

    main_area = main
    title = segment.slots.get("main_title")
    if title is not None:
        block = _fit_line(fonts, title.text or "", main, style, segment.segment_key)
        layout.texts["main_title"] = block
        main_area = Rect(main.x0, block.rect.y1, main.x1, main.y1)

    _place_slot(layout, video, segment, "main", main_area, style, library)
    if "sidebar" in segment.slots:
        _place_slot(layout, video, segment, "sidebar", layout.slot_rects["sidebar"], style, library)
        sidebar_slot = segment.slots["sidebar"]
        if sidebar_slot.kind in ("text", "bullets"):
            layout.texts["sidebar"] = _fit_text(
                fonts, sidebar_slot, layout.slot_rects["sidebar"], style, segment.segment_key
            )

    for h in segment.highlights:
        layout.highlight_rects[h.key] = _target_rect(layout, video, segment, h.target)
    for lab in segment.labels:
        layout.labels[lab.key] = _place_label(
            layout,
            fonts,
            style,
            lab.text,
            lab.style,
            lab.position,
            _target_rect(layout, video, segment, lab.target),
            segment.segment_key,
            lab.key,
        )
    return layout


def _place_slot(
    layout: SegmentLayout,
    video: Video,
    segment: Segment,
    name: str,
    area: Rect,
    style: Style,
    library: AssetLibrary,
) -> None:
    slot = segment.slots[name]
    if slot.kind == "asset" and slot.asset_key:
        size = library.size(slot.asset_key, slot.crop)
        image = fit(size, area)
        if name == "sidebar" and style.sidebar_valign == "top":
            image = image.translate(0, area.y0 - image.y0)
        layout.image_rects[name] = image
        _check_resolution(layout, segment, name, slot.asset_key, size, image, style)
        for region_name, region in video.assets[slot.asset_key].regions.items():
            # 區域以原圖為準記錄；有 crop 時換算成裁切後的位置，看不到的區域不放進來
            if region is None:  # 待量測只會出現在草稿，草稿不排版
                continue
            visible = region_in_crop(region, slot.crop)
            if visible is not None:
                layout.region_rects[f"{name}@{region_name}"] = image.sub(
                    visible.x, visible.y, visible.w, visible.h
                )
    elif slot.kind == "items":
        _place_items(layout, segment, name, slot, area, style, library)


def _place_items(
    layout: SegmentLayout,
    segment: Segment,
    name: str,
    slot: Slot,
    area: Rect,
    style: Style,
    library: AssetLibrary,
) -> None:
    aspects = []
    for item in slot.items:
        w, h = library.size(item.asset_key)
        aspects.append(w / h)
    gap_ratio = style.items_gap_ratio
    width_units = sum(aspects) + gap_ratio * (len(aspects) - 1)
    height = min(area.h * style.items_max_height_ratio, area.w * 0.96 / width_units)
    total = width_units * height
    cx, cy = area.center
    x = cx - total / 2
    for item, aspect in zip(slot.items, aspects, strict=True):
        rect = Rect(x, cy - height / 2, x + aspect * height, cy + height / 2)
        layout.item_rects[item.item_key] = rect
        for key in (item.asset_key, item.back_asset_key):
            if key:
                _check_resolution(layout, segment, name, key, library.size(key), rect, style)
        x = rect.x1 + gap_ratio * height


def _check_resolution(
    layout: SegmentLayout,
    segment: Segment,
    slot: str,
    asset_key: str,
    size: tuple[int, int],
    placed: Rect,
    style: Style,
) -> None:
    factor = style.low_resolution_factor
    if placed.w > size[0] * factor or placed.h > size[1] * factor:
        layout.warnings.append(
            f"段 {segment.segment_key} 槽位 {slot} 的素材 {asset_key} 放大超過 {factor:g} 倍"
            f"（原圖 {size[0]}×{size[1]}，貼上 {placed.w:.0f}×{placed.h:.0f}），"
            "照常使用一般放大，不使用 AI 放大"
        )


def _target_rect(layout: SegmentLayout, video: Video, segment: Segment, text: str) -> Rect:
    target = resolve_target(segment, video.assets, text)
    if target is None:  # 載入時已驗證，不會發生
        raise LayoutError(f"段 {segment.segment_key} 找不到 target {text}")
    if target.kind == "item":
        return layout.item_rects[target.name or ""]
    if target.kind == "region":
        return layout.region_rects[text]
    name = target.slot or text
    if name in layout.image_rects:
        return layout.image_rects[name]
    slot = segment.slots[name]
    if slot.kind == "items":
        # 一排物件：以整排牌的範圍為準，不是整個槽位
        rects = [layout.item_rects[i.item_key] for i in slot.items]
        return Rect(
            min(r.x0 for r in rects),
            min(r.y0 for r in rects),
            max(r.x1 for r in rects),
            max(r.y1 for r in rects),
        )
    if name in layout.texts:
        return layout.texts[name].rect
    return layout.slot_rects[name]


def _fit_line(fonts: FontSet, text: str, area: Rect, style: Style, segment_key: str) -> TextBlock:
    """主體標題：一行，放不下就縮字級。"""
    for size in range(style.title_size, style.title_min_size - 1, -2):
        font = fonts.get(size, bold=True)
        width = text_width(font, text)
        if width <= area.w:
            band = size * style.title_band_ratio
            cx = area.center[0]
            rect = Rect(cx - width / 2, area.y0, cx + width / 2, area.y0 + band)
            return TextBlock(rect, (text,), size, bold=True)
    raise LayoutError(
        f"段 {segment_key} 槽位 main_title 的文字放不下：縮到最小字級 {style.title_min_size} 仍超出"
    )


def _fit_text(fonts: FontSet, slot: Slot, area: Rect, style: Style, segment_key: str) -> TextBlock:
    """側欄文字：換行、再縮字級；縮到最小字級仍放不下就報錯，不讓文字超出槽位。"""
    box = area.inset(12)
    for size in range(style.text_size, style.text_min_size - 1, -2):
        font = fonts.get(size)
        title_size = round(size * 1.2)
        title_lines = (
            tuple(wrap(fonts.get(title_size, bold=True), slot.title, box.w)) if slot.title else ()
        )
        if slot.kind == "bullets":
            lines: list[str] = []
            for bullet in slot.bullets:
                lines.extend(wrap(font, f"• {bullet}", box.w))
        else:
            lines = wrap(font, slot.text or "", box.w)
        title_h = len(title_lines) * title_size * LINE_HEIGHT + (size * 0.5 if title_lines else 0)
        height = title_h + len(lines) * size * LINE_HEIGHT
        widest = max(
            [text_width(font, line) for line in lines]
            + [text_width(fonts.get(title_size, bold=True), line) for line in title_lines]
        )
        if height <= box.h and widest <= box.w:
            y0 = box.center[1] - height / 2
            rect = Rect(box.x0, y0, box.x0 + widest, y0 + height)
            return TextBlock(
                rect,
                tuple(lines),
                size,
                title_lines=title_lines,
                title_size=title_size,
                emphasis=slot.emphasis,
            )
    raise LayoutError(
        f"段 {segment_key} 槽位 sidebar 的文字放不下：縮到最小字級 {style.text_min_size} 仍超出"
    )


def _place_label(
    layout: SegmentLayout,
    fonts: FontSet,
    style: Style,
    text: str,
    label_style: str,
    position: str,
    target: Rect,
    segment_key: str,
    key: str,
) -> LabelBox:
    size = style.plain_label_size if label_style == "plain" else style.label_size
    pad_x, pad_y = (4, 2) if label_style == "plain" else (20, 8)
    width = text_width(fonts.get(size, bold=label_style != "plain"), text) + 2 * pad_x
    height = size * 1.3 + 2 * pad_y
    content = layout.content
    if width > content.w:
        raise LayoutError(f"段 {segment_key} label {key} 的文字太長，超出內容區")
    cx = target.center[0]
    if position == "below":
        y0 = target.y1 + 12
    elif position == "above":
        y0 = target.y0 - 12 - height
    else:
        y0 = target.center[1] - height / 2
    x0 = min(max(cx - width / 2, content.x0), content.x1 - width)
    y0 = min(max(y0, content.y0), content.y1 - height)
    return LabelBox(Rect(x0, y0, x0 + width, y0 + height), text, size, label_style)


def _layout_subtitles(
    layout: SegmentLayout, segment: Segment, fonts: FontSet, style: Style
) -> None:
    """字幕最多 subtitle_max_lines 行；超過就報錯，否則字幕框會往上蓋到內容區。"""
    font = fonts.get(style.subtitle_size)
    for beat in segment.beats:
        lines = subtitle_lines(font, beat.subtitle, style.subtitle_max_width)
        if len(lines) > style.subtitle_max_lines:
            raise LayoutError(
                f"段 {segment.segment_key} 句 {beat.beat_key} 的字幕太長："
                f"斷行後有 {len(lines)} 行，最多兩行，請縮短字幕"
            )
        layout.subtitle_lines[beat.beat_key] = tuple(lines)


def subtitle_lines(font: Font, text: str, max_width: float) -> list[str]:
    """字幕超過寬度時斷行，兩行時優先在接近中間的標點後斷開。"""
    if text_width(font, text) <= max_width:
        return [text]
    middle = len(text) / 2
    breaks = [i + 1 for i, ch in enumerate(text[:-1]) if ch in SUBTITLE_BREAKS]
    if breaks:
        cut = min(breaks, key=lambda i: abs(i - middle))
        first, second = text[:cut], text[cut:]
        if text_width(font, first) <= max_width and text_width(font, second) <= max_width:
            return [first, second]
    return wrap(font, text, max_width)


def subtitle_box(style: Style, lines: int, width: float | None = None) -> Rect:
    """字幕框：下緣固定在 subtitle_bottom，依行數往上長。width 沒給時用最大寬度。"""
    height = lines * style.subtitle_line_height + SUBTITLE_PADDING
    w = width if width is not None else style.subtitle_max_width + 64
    cx = style.width / 2
    return Rect(cx - w / 2, style.subtitle_bottom - height, cx + w / 2, style.subtitle_bottom)
