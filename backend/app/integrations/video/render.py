"""依 Frame 畫出 1920×1080 的畫面（Pillow）。風格數值全部來自 Style。"""

import numpy as np
from PIL import Image, ImageDraw

from app.integrations.video.assets import AssetLibrary
from app.integrations.video.compose import Frame, frame_at
from app.integrations.video.fonts import Font, FontSet, text_width, wrap
from app.integrations.video.geometry import Rect
from app.integrations.video.layout import SegmentLayout, TextBlock, subtitle_box
from app.integrations.video.model import Video
from app.integrations.video.style import RGB, Style
from app.integrations.video.timeline import Timeline

LINE_HEIGHT = 1.4


def _rgba(color: RGB, alpha: float) -> tuple[int, int, int, int]:
    return (*color, max(0, min(255, round(255 * alpha))))


class Renderer:
    def __init__(
        self,
        video: Video,
        timeline: Timeline,
        layouts: dict[str, SegmentLayout],
        fonts: FontSet,
        style: Style,
        library: AssetLibrary | None = None,
    ) -> None:
        self.video = video
        self.timeline = timeline
        self.layouts = layouts
        self.fonts = fonts
        self.style = style
        self.library = library or AssetLibrary(video)
        self.background = _background(style)

    def frame(self, t: float) -> Frame:
        return frame_at(self.video, self.timeline, self.layouts, t, self.style)

    def render(self, t: float) -> Image.Image:
        frame = self.frame(t)
        canvas = self.background.copy()
        self._canvas = canvas
        draw = ImageDraw.Draw(canvas, "RGBA")
        segment = frame.segment.segment
        if segment.template == "title_card":
            self._title_card(draw, frame)
        else:
            self._slots(canvas, draw, frame)
            self._items(canvas, draw, frame, moving=False)
            self._items(canvas, draw, frame, moving=True)
            self._highlights(draw, frame)
            self._labels(draw, frame)
            self._header(draw, frame)
            self._subtitle(draw, frame)
        self._progress(draw, frame)
        if segment.transition_in == "fade" and frame.local_t < self.style.transition_seconds:
            alpha = 1 - frame.local_t / self.style.transition_seconds
            draw.rectangle(
                (0, 0, self.style.width, self.style.height), fill=(0, 0, 0, round(255 * alpha))
            )
        return canvas

    # ------------------------------------------------------------------ 元素

    def _text(
        self,
        xy: tuple[float, float],
        text: str,
        font: Font,
        fill: tuple[int, int, int, int],
    ) -> None:
        """畫文字並套用透明度。

        Pillow 在 RGB 畫布上畫文字時會忽略填色的透明度，所以半透明的文字先畫成遮罩再貼上。
        """
        alpha = fill[3]
        if alpha <= 0 or not text:
            return
        canvas = self._canvas
        if alpha >= 255:
            ImageDraw.Draw(canvas).text(xy, text, font=font, fill=fill[:3])
            return
        left, top, right, bottom = ImageDraw.Draw(canvas).textbbox(xy, text, font=font)
        left, top = int(left) - 1, int(top) - 1
        size = (int(right) - left + 2, int(bottom) - top + 2)
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).text((xy[0] - left, xy[1] - top), text, font=font, fill=alpha)
        canvas.paste(Image.new("RGB", size, fill[:3]), (left, top), mask)

    def _paste(
        self, canvas: Image.Image, asset_key: str, rect: Rect, alpha: float, crop=None
    ) -> None:
        w, h = round(rect.w), round(rect.h)
        if alpha <= 0 or w <= 0 or h <= 0:
            return
        image = self.library.resized(asset_key, w, h, crop)
        mask = image.getchannel("A")
        if alpha < 1:
            mask = mask.point(lambda v: round(v * alpha))
        canvas.paste(image, (round(rect.x0), round(rect.y0)), mask)

    def _slots(self, canvas: Image.Image, draw: ImageDraw.ImageDraw, frame: Frame) -> None:
        segment = frame.segment.segment
        layout = frame.layout
        for name in ("sidebar", "main"):
            slot = segment.slots.get(name)
            if slot is None:
                continue
            alpha = frame.slots[name].alpha
            if slot.kind == "asset" and slot.asset_key:
                self._paste(canvas, slot.asset_key, layout.image_rects[name], alpha, slot.crop)
            elif name in layout.texts:
                self._text_block(draw, layout.texts[name], alpha)
        if "main_title" in layout.texts:
            block = layout.texts["main_title"]
            font = self.fonts.get(block.size, bold=True)
            x = block.rect.x0
            y = block.rect.y0 + (block.rect.h - block.size * 1.2) / 2
            alpha = frame.slots["main_title"].alpha
            self._text(
                (x + 2, y + 3), block.lines[0], font=font, fill=(0, 0, 0, round(150 * alpha))
            )
            self._text((x, y), block.lines[0], font=font, fill=_rgba(self.style.gold, alpha))

    def _text_block(self, draw: ImageDraw.ImageDraw, block: TextBlock, alpha: float) -> None:
        y = block.rect.y0
        title_font = self.fonts.get(block.title_size, bold=True) if block.title_lines else None
        for line in block.title_lines:
            self._text(
                (block.rect.x0, y), line, font=title_font, fill=_rgba(self.style.gold, alpha)
            )
            y += block.title_size * LINE_HEIGHT
        if block.title_lines:
            y += block.size * 0.5
        font = self.fonts.get(block.size)
        for line in block.lines:
            self._runs(draw, block.rect.x0, y, line, font, block.emphasis, alpha)
            y += block.size * LINE_HEIGHT

    def _items(
        self, canvas: Image.Image, draw: ImageDraw.ImageDraw, frame: Frame, *, moving: bool
    ) -> None:
        for item in frame.items.values():
            if item.moving != moving or item.alpha <= 0:
                continue
            shadow = item.rect.translate(6, 9)
            draw.rounded_rectangle(
                (shadow.x0, shadow.y0, shadow.x1, shadow.y1),
                radius=max(2, round(item.rect.w * 0.06)),
                fill=(0, 0, 0, round(110 * item.alpha)),
            )
            self._paste(canvas, item.asset_key, item.rect, item.alpha)

    def _highlights(self, draw: ImageDraw.ImageDraw, frame: Frame) -> None:
        segment = frame.segment.segment
        for h in segment.highlights:
            alpha = frame.highlights[h.key].alpha
            if alpha <= 0:
                continue
            rect = self._live_target_rect(frame, h.target, frame.layout.highlight_rects[h.key])
            color = self.style.gold if h.style == "gold" else self.style.red
            if h.shape == "cross":
                inner = rect.inset(rect.w * 0.04, rect.h * 0.04)
                width = max(6, round(rect.w * 0.07))
                for line in (
                    (inner.x0, inner.y0, inner.x1, inner.y1),
                    (inner.x0, inner.y1, inner.x1, inner.y0),
                ):
                    draw.line(line, fill=_rgba(color, alpha * 0.9), width=width)
            else:
                draw.rounded_rectangle(
                    (rect.x0, rect.y0, rect.x1, rect.y1),
                    radius=10,
                    outline=_rgba(color, alpha),
                    width=self.style.highlight_width,
                    fill=_rgba(color, alpha * 0.08),
                )

    def _live_target_rect(self, frame: Frame, target: str, default: Rect) -> Rect:
        """highlight 指向某一項時，跟著該項目前的位置（例如翻牌、移動中）。"""
        if "." in target:
            item_key = target.partition(".")[2]
            if item_key in frame.items:
                return frame.items[item_key].rect
        return default

    def _labels(self, draw: ImageDraw.ImageDraw, frame: Frame) -> None:
        for key, box in frame.layout.labels.items():
            alpha = frame.labels[key].alpha
            if alpha <= 0:
                continue
            rect = box.rect
            bold = box.style != "plain"
            font = self.fonts.get(box.size, bold=bold)
            if box.style == "plain":
                fill_text = _rgba(self.style.text_color, alpha)
            else:
                background = self.style.red if box.style == "red" else self.style.gold
                draw.rounded_rectangle(
                    (rect.x0, rect.y0, rect.x1, rect.y1),
                    radius=round(rect.h / 2),
                    fill=_rgba(background, alpha * 0.95),
                )
                fill_text = (
                    (255, 255, 255, round(255 * alpha))
                    if box.style == "red"
                    else (30, 24, 10, round(255 * alpha))
                )
            tw = text_width(font, box.text)
            x = rect.center[0] - tw / 2
            y = rect.center[1] - box.size * 0.62
            self._text((x, y), box.text, font=font, fill=fill_text)

    def _header(self, draw: ImageDraw.ImageDraw, frame: Frame) -> None:
        chapter = self.video.chapter(frame.segment.segment.chapter_key)
        style = self.style
        font = self.fonts.get(style.header_size, bold=True)
        text = f"{chapter.number}   {chapter.title}"
        rect = style.header_rect
        width = max(text_width(font, text) + 44, 120)
        draw.rounded_rectangle(
            (rect.x0, rect.y0, rect.x0 + width, rect.y1),
            radius=round(rect.h / 2),
            fill=(0, 0, 0, 120),
            outline=(225, 222, 210, 220),
            width=2,
        )
        self._text(
            (rect.x0 + 22, rect.center[1] - style.header_size * 0.62),
            text,
            font=font,
            fill=_rgba(style.text_color, 1),
        )

    def _subtitle(self, draw: ImageDraw.ImageDraw, frame: Frame) -> None:
        beat = frame.beat
        if beat is None:
            return
        style = self.style
        elapsed = frame.t - beat.start
        alpha = min(1.0, max(0.0, elapsed / style.subtitle_fade_seconds))
        rise = (1 - alpha) * style.subtitle_rise
        font = self.fonts.get(style.subtitle_size)
        lines = frame.layout.subtitle_lines[beat.beat.beat_key]
        line_h = style.subtitle_line_height
        width = max(text_width(font, line) for line in lines) + 64
        box = subtitle_box(style, len(lines), width).translate(0, rise)
        cx = style.width / 2
        draw.rounded_rectangle(
            (box.x0, box.y0, box.x1, box.y1),
            radius=16,
            fill=(*style.subtitle_box[:3], round(style.subtitle_box[3] * alpha)),
            outline=(*style.subtitle_border[:3], round(style.subtitle_border[3] * alpha)),
            width=2,
        )
        y = box.y0 + 15 + (line_h - style.subtitle_size * 1.2) / 2
        for line in lines:
            x = cx - text_width(font, line) / 2
            self._runs(draw, x, y, line, font, beat.beat.keywords, alpha)
            y += line_h

    def _runs(
        self,
        draw: ImageDraw.ImageDraw,
        x: float,
        y: float,
        line: str,
        font: Font,
        keywords: tuple[str, ...],
        alpha: float,
    ) -> None:
        """一行文字，其中的關鍵字用金色。"""
        for text, is_keyword in _split_keywords(line, keywords):
            color = self.style.gold if is_keyword else self.style.text_color
            self._text((x, y), text, font=font, fill=_rgba(color, alpha))
            x += text_width(font, text)

    def _progress(self, draw: ImageDraw.ImageDraw, frame: Frame) -> None:
        style = self.style
        rect = style.progress_rect
        spans = self.timeline.chapter_spans
        total = self.timeline.total or 1.0
        gap = 10
        usable = rect.w - gap * (len(spans) - 1)
        x = rect.x0
        for _, start, end in spans:
            width = usable * (end - start) / total
            draw.rounded_rectangle(
                (x, rect.y0, x + width, rect.y1), radius=3, fill=style.progress_empty
            )
            if frame.t >= end:
                filled = width
            elif frame.t > start:
                filled = width * (frame.t - start) / (end - start)
            else:
                filled = 0
            if filled > 0:
                draw.rounded_rectangle(
                    (x, rect.y0, x + filled, rect.y1), radius=3, fill=_rgba(style.gold, 1)
                )
            x += width + gap

    def _title_card(self, draw: ImageDraw.ImageDraw, frame: Frame) -> None:
        style = self.style
        chapter = self.video.chapter(frame.segment.segment.chapter_key)
        alpha = min(1.0, frame.local_t / style.transition_seconds)
        title_font = self.fonts.get(style.title_card_size, bold=True)
        lines = wrap(title_font, self.video.title, style.content_rect.w)
        y = style.height / 2 - len(lines) * style.title_card_size * 0.8
        for line in lines:
            x = style.width / 2 - text_width(title_font, line) / 2
            self._text((x, y), line, font=title_font, fill=_rgba(style.gold, alpha))
            y += style.title_card_size * LINE_HEIGHT
        sub_font = self.fonts.get(style.text_size)
        sub = f"{chapter.number}   {chapter.title}"
        self._text(
            (style.width / 2 - text_width(sub_font, sub) / 2, y + 20),
            sub,
            font=sub_font,
            fill=_rgba(style.text_color, alpha),
        )


def _background(style: Style) -> Image.Image:
    """暗色漸層加暗角（沒有背景圖時使用）。"""
    h, w = style.height, style.width
    y = np.linspace(0.0, 1.0, h)[:, None]
    x = np.linspace(0.0, 1.0, w)[None, :]
    top = np.array(style.background_top, dtype=np.float32)
    bottom = np.array(style.background_bottom, dtype=np.float32)
    gradient = top[None, None, :] * (1 - y[..., None]) + bottom[None, None, :] * y[..., None]
    radius = np.sqrt(((x - 0.5) / 0.62) ** 2 + ((y - 0.42) / 0.75) ** 2)
    vignette = 1 - style.vignette_strength * np.clip(radius - 0.35, 0, 1) ** 1.4
    image = np.clip(gradient * vignette[..., None], 0, 255).astype(np.uint8)
    return Image.fromarray(image, "RGB")


def _split_keywords(line: str, keywords: tuple[str, ...]) -> list[tuple[str, bool]]:
    if not keywords:
        return [(line, False)]
    parts: list[tuple[str, bool]] = []
    i = 0
    while i < len(line):
        match = next((k for k in keywords if k and line.startswith(k, i)), None)
        if match:
            parts.append((match, True))
            i += len(match)
            continue
        if parts and not parts[-1][1]:
            parts[-1] = (parts[-1][0] + line[i], False)
        else:
            parts.append((line[i], False))
        i += 1
    return parts
