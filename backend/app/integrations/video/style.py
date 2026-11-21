"""風格資料（依《血與刃》製作紀錄 4.2）。

風格是一份資料，不寫在版型裡；之後換遊戲風格只換這份資料。數值對照手做版截圖調整。
"""

from dataclasses import dataclass

from app.integrations.video.geometry import Rect

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]

# 字幕框上下的留白合計（像素）
SUBTITLE_PADDING = 30


@dataclass(frozen=True)
class Style:
    width: int = 1920
    height: int = 1080
    fps: int = 30

    # --- 分區 ---
    # 左上章節標籤（「11 步驟三」）
    header_rect: Rect = Rect(40, 30, 320, 88)
    # 內容區：章節標籤之下、字幕列之上（下緣要高於兩行字幕框的上緣，見 subtitle_top）
    content_rect: Rect = Rect(90, 120, 1830, 796)
    # 字幕框的下緣；上緣依行數往上長，最多 subtitle_max_lines 行
    subtitle_bottom: float = 952
    subtitle_max_lines: int = 2
    # 進度條
    progress_rect: Rect = Rect(330, 982, 1590, 990)

    # --- main_with_sidebar ---
    sidebar_ratio: float = 0.30  # 側欄寬度占內容區的比例
    sidebar_gap: float = 90  # 主體區與側欄的間距
    sidebar_valign: str = "top"  # 側欄圖片的垂直對齊：top | center
    title_band_ratio: float = 1.7  # 主體標題列高度＝字級 × 這個倍數
    items_max_height_ratio: float = 0.5  # 一排物件的高度上限（占主體區高度）
    items_gap_ratio: float = 0.14  # 物件間距（占物件高度）
    move_inset_ratio: float = 0.08  # 物件移進區域時，四周留白（占區域寬高）
    low_resolution_factor: float = 2.0  # 貼上大小超過原圖幾倍時警告

    # --- 字級（像素） ---
    title_size: int = 60
    title_min_size: int = 30
    text_size: int = 34
    text_min_size: int = 18
    subtitle_size: int = 40
    subtitle_max_width: float = 1500
    label_size: int = 38
    plain_label_size: int = 24
    header_size: int = 28
    title_card_size: int = 84

    # --- 顏色 ---
    background_top: RGB = (30, 33, 40)
    background_bottom: RGB = (10, 10, 12)
    vignette_strength: float = 0.55
    gold: RGB = (222, 184, 98)
    red: RGB = (214, 52, 52)
    text_color: RGB = (238, 236, 230)
    dim_text: RGB = (170, 168, 160)
    subtitle_box: RGBA = (16, 16, 18, 225)
    subtitle_border: RGBA = (110, 110, 110, 160)
    progress_empty: RGBA = (90, 90, 96, 200)
    highlight_width: int = 5

    # --- 動畫長度（秒） ---
    pop_seconds: float = 0.4
    fade_seconds: float = 0.3
    hide_seconds: float = 0.3
    flip_seconds: float = 0.5
    move_seconds: float = 0.8
    shuffle_seconds: float = 1.5  # cue 沒寫 duration 時使用
    subtitle_fade_seconds: float = 0.3
    subtitle_rise: float = 14
    transition_seconds: float = 0.4

    @property
    def subtitle_line_height(self) -> float:
        return self.subtitle_size * 1.45

    @property
    def subtitle_top(self) -> float:
        """字幕框最高會到的位置（最多行數時的上緣）。內容區不能低於這裡。"""
        return (
            self.subtitle_bottom
            - self.subtitle_max_lines * self.subtitle_line_height
            - SUBTITLE_PADDING
        )


DEFAULT_STYLE = Style()
