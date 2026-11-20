"""字型。

直接指定一般與粗體兩個字型檔（例如 Windows 的微軟正黑體 msjh.ttc、msjhbd.ttc）；
.ttc 是字型集合檔，用 index 選字型，.ttf／.otf 忽略 index。
兩個都沒設定時退回 Pillow 內建字型並給警告（CI 沒有中文字型）；有設定但檔案不存在或 index
超出範圍時直接失敗，不靜默退回。
"""

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from app.integrations.video.errors import FontConfigError

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont

FALLBACK_WARNING = (
    "未設定中文字型（VIDEO_FONT_REGULAR、VIDEO_FONT_BOLD），"
    "改用 Pillow 內建字型，中文會無法正確顯示"
)


class FontSet:
    def __init__(self, regular: str | None, bold: str | None, index: int = 0) -> None:
        self.index = index
        if regular is None and bold is None:
            self.fallback = True
            self._paths: dict[bool, str] = {}
            return
        if regular is None:
            raise FontConfigError("設定了 VIDEO_FONT_BOLD，但沒有設定 VIDEO_FONT_REGULAR")
        self.fallback = False
        self._paths = {False: regular, True: bold or regular}
        for name, path in (("VIDEO_FONT_REGULAR", regular), ("VIDEO_FONT_BOLD", bold)):
            if path is None:
                continue
            if not Path(path).is_file():
                raise FontConfigError(f"{name} 指向的字型檔不存在：{path}")
            try:
                ImageFont.truetype(path, 12, index=index)
            except (OSError, ValueError) as exc:
                raise FontConfigError(
                    f"VIDEO_FONT_INDEX={index} 無法從 {path} 載入字型"
                    f"（.ttc 的 index 可能超出範圍，或 {name} 不是字型檔）"
                ) from exc

    @property
    def cache_key(self) -> str:
        """字型的識別字串，段快取用：換了字型，畫面就不同。"""
        if self.fallback:
            return "pillow-default"
        return f"{self._paths[False]}|{self._paths[True]}|{self.index}"

    @property
    def warning(self) -> str | None:
        return FALLBACK_WARNING if self.fallback else None

    def get(self, size: int, bold: bool = False) -> Font:
        return _load(self._paths.get(bold), self.index, size)


@lru_cache(maxsize=256)
def _load(path: str | None, index: int, size: int) -> Font:
    if path is None:
        return ImageFont.load_default(size=size)
    return ImageFont.truetype(path, size, index=index)


def text_width(font: Font, text: str) -> float:
    if not text:
        return 0.0
    left, _, right, _ = font.getbbox(text)
    return float(right - left)


def wrap(font: Font, text: str, max_width: float) -> list[str]:
    """依寬度斷行：英文以字為單位，中文逐字；原有的換行保留。"""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for token in _tokens(paragraph):
            candidate = current + token
            if current and text_width(font, candidate.rstrip()) > max_width:
                lines.append(current.rstrip())
                current = token.lstrip()
            else:
                current = candidate
        lines.append(current.rstrip())
    return lines


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    word = ""
    for ch in text:
        if ch.isascii() and not ch.isspace():
            word += ch
            continue
        if word:
            tokens.append(word)
            word = ""
        if ch.isspace() and tokens:
            tokens[-1] += ch
        elif not ch.isspace():
            tokens.append(ch)
    if word:
        tokens.append(word)
    return tokens
