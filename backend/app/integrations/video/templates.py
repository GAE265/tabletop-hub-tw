"""版型定義：每個版型有哪些槽位、哪些必填、可以放哪些內容。

版型只描述槽位，不寫任何遊戲的內容；位置與尺寸由 layout.py 依風格計算。
"""

from dataclasses import dataclass

SLOT_KINDS = ("asset", "items", "text", "bullets")
# 已保留名稱、本版尚未支援的槽位內容
RESERVED_SLOT_KINDS = ("player_ring",)


@dataclass(frozen=True)
class SlotSpec:
    required: bool
    kinds: tuple[str, ...]


@dataclass(frozen=True)
class TemplateSpec:
    name: str
    slots: dict[str, SlotSpec]
    # 固定長度（秒）；None 代表依旁白與動作計算
    fixed_seconds: float | None
    # 是否有旁白（句）；標題字卡沒有
    has_beats: bool


TEMPLATES: dict[str, TemplateSpec] = {
    "main_with_sidebar": TemplateSpec(
        name="main_with_sidebar",
        slots={
            "main_title": SlotSpec(required=False, kinds=("text",)),
            "main": SlotSpec(required=True, kinds=("asset", "items")),
            "sidebar": SlotSpec(required=False, kinds=("asset", "text", "bullets")),
        },
        fixed_seconds=None,
        has_beats=True,
    ),
    "title_card": TemplateSpec(name="title_card", slots={}, fixed_seconds=3.0, has_beats=False),
}

DEFAULT_TEMPLATE = "main_with_sidebar"
