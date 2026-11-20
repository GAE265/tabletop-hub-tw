"""排版用的矩形。座標單位是畫面像素（1920×1080），浮點數。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def inside(self, other: "Rect", tolerance: float = 0.5) -> bool:
        return (
            self.x0 >= other.x0 - tolerance
            and self.y0 >= other.y0 - tolerance
            and self.x1 <= other.x1 + tolerance
            and self.y1 <= other.y1 + tolerance
        )

    def intersects(self, other: "Rect") -> bool:
        return not (
            self.x1 <= other.x0 or other.x1 <= self.x0 or self.y1 <= other.y0 or other.y1 <= self.y0
        )

    def inset(self, dx: float, dy: float | None = None) -> "Rect":
        dy = dx if dy is None else dy
        return Rect(self.x0 + dx, self.y0 + dy, self.x1 - dx, self.y1 - dy)

    def translate(self, dx: float, dy: float) -> "Rect":
        return Rect(self.x0 + dx, self.y0 + dy, self.x1 + dx, self.y1 + dy)

    def scale_width(self, factor: float) -> "Rect":
        """以中心為準縮放寬度（翻牌用）。"""
        cx = self.center[0]
        half = self.w * factor / 2
        return Rect(cx - half, self.y0, cx + half, self.y1)

    def sub(self, x: float, y: float, w: float, h: float) -> "Rect":
        """以 0–1 比例取出子區域。"""
        return Rect(
            self.x0 + x * self.w,
            self.y0 + y * self.h,
            self.x0 + (x + w) * self.w,
            self.y0 + (y + h) * self.h,
        )

    def lerp(self, other: "Rect", p: float) -> "Rect":
        return Rect(
            self.x0 + (other.x0 - self.x0) * p,
            self.y0 + (other.y0 - self.y0) * p,
            self.x1 + (other.x1 - self.x1) * p,
            self.y1 + (other.y1 - self.y1) * p,
        )


def fit(size: tuple[float, float], box: Rect, *, max_scale: float | None = None) -> Rect:
    """把 size（寬、高）等比例縮放到 box 內並置中。"""
    w, h = size
    scale = min(box.w / w, box.h / h)
    if max_scale is not None:
        scale = min(scale, max_scale)
    fw, fh = w * scale, h * scale
    cx, cy = box.center
    return Rect(cx - fw / 2, cy - fh / 2, cx + fw / 2, cy + fh / 2)
