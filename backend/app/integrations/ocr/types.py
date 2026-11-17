"""OCR 整合層的輸入輸出型別。只保留下游需要的欄位，不回傳 Azure 的原始 JSON。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LayoutLine:
    """版面分析的一行文字。"""

    text: str
    # 四個角的座標 x1,y1,x2,y2,x3,y3,x4,y4，單位同 LayoutResult.unit
    polygon: list[float]


@dataclass(frozen=True)
class LayoutResult:
    """第一頁的版面分析結果。"""

    width: float
    height: float
    # 座標單位：像素圖是 "pixel"，PDF 是 "inch"
    unit: str
    # 文字的傾斜角度（度，-180 到 180）
    angle: float
    lines: list[LayoutLine] = field(default_factory=list)
