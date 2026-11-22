"""整個遊戲一支影片：把整本規則書分成三格（add-rules-video-mobile 整本範圍，2026-11-22 永傑決定）。

只講「開局、走完一輪、獲勝方式」三格；其餘（變體、細則、Q&A 等）放進排除清單，附原因，
只存資料庫，店員看不到（漏講的由店員看完影片後提出修改補救）。
每一筆分類都要引用原文片段；程式檢查片段確實出現在那一頁，引用不到的不採用。
某一格是空的就讓草稿工作失敗並寫明原因。
"""

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.domains.rules_qa.video_script import RulebookPage
from app.integrations.llm import LLMProvider
from app.integrations.llm.types import JsonSchema

# 三格的 key 與給店員看的名稱，依影片的順序（段資料的三個 chapter）
SLOTS: tuple[tuple[str, str], ...] = (
    ("setup", "開局"),
    ("round", "走完一輪"),
    ("win", "獲勝方式"),
)
SLOT_TITLES = dict(SLOTS)

# 片段太短（例如只有一個詞）無法判斷出處，不採用
MIN_QUOTE_CHARS = 4

INSTRUCTIONS = """你要把一款桌遊的整本規則書分成三格，作為一支規則教學影片的範圍。
觀看者是第一次玩的玩家，目標是看完能自己開一局、玩完一輪、知道怎麼贏。

三格：
- setup（開局）：配件準備、起始配置、分配角色或手牌、誰先開始等，開一局之前要做的事。
- round（走完一輪）：一輪裡每位玩家的回合流程、可以做的行動、回合中的階段，玩一輪需要知道的事。
- win（獲勝方式）：遊戲什麼時候結束、怎麼判定勝負或計分。
- excluded（不講）：不屬於三格的內容，例如變體或進階規則、設計者的話、配件清單、圖例、問答、
  罕見情況的細則。每一筆寫 reason（為什麼不講）。

規則：
1. 每一筆都要引用規則書的原文片段（quote），一字不改地照抄，可以是一句或一整段；page 寫它在第幾頁。
2. 不可改寫、摘要或補充原文沒有的內容；不可把不同頁的文字合成一筆。
3. 同一段文字只放進一格。三格都要有內容；真的找不到某一格的內容時，那一格給空陣列。
4. 依原文的順序列出。
5. 每一頁都要有去處：至少有一筆放進某一格或 excluded（圖例、配件清單也一樣，放進 excluded）。"""

_QUOTE = {
    "type": "object",
    "properties": {"page": {"type": "integer"}, "quote": {"type": "string"}},
    "required": ["page", "quote"],
    "additionalProperties": False,
}
_EXCLUDED = {
    "type": "object",
    "properties": {
        "page": {"type": "integer"},
        "quote": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["page", "quote", "reason"],
    "additionalProperties": False,
}
SCHEMA = JsonSchema(
    name="rules_video_scope",
    schema={
        "type": "object",
        "properties": {
            "setup": {"type": "array", "items": _QUOTE},
            "round": {"type": "array", "items": _QUOTE},
            "win": {"type": "array", "items": _QUOTE},
            "excluded": {"type": "array", "items": _EXCLUDED},
        },
        "required": ["setup", "round", "win", "excluded"],
        "additionalProperties": False,
    },
)


@dataclass(frozen=True)
class Excerpt:
    page: int
    text: str


@dataclass(frozen=True)
class ExcludedExcerpt:
    page: int
    text: str
    reason: str


@dataclass(frozen=True)
class ScopeSlot:
    key: str  # setup | round | win
    title: str  # 開局 | 走完一輪 | 獲勝方式
    excerpts: list[Excerpt]


@dataclass(frozen=True)
class ScopeResult:
    slots: list[ScopeSlot]
    excluded: list[ExcludedExcerpt]
    # 引用不到原文而沒採用的（{slot, page, quote, problem}），給開發者看
    dropped: list[dict[str, Any]] = field(default_factory=list)

    @property
    def pages(self) -> list[int]:
        """三格用到的頁（段資料的 source_pages 只能用這些頁）。"""
        return sorted({e.page for slot in self.slots for e in slot.excerpts})

    def to_dict(self) -> dict[str, Any]:
        return {
            "slots": [asdict(slot) for slot in self.slots],
            "excluded": [asdict(e) for e in self.excluded],
            "dropped": self.dropped,
        }


class ScopeIncomplete(Exception):
    """改寫一次後，仍有頁沒有去處（不在三格、也不在排除清單）。"""

    def __init__(self, pages: list[int], dropped: list[dict[str, Any]]) -> None:
        listed = "、".join(str(page) for page in pages)
        super().__init__(f"規則書第 {listed} 頁沒有分到三格，也不在排除清單")
        self.pages = pages
        self.dropped = dropped

    @property
    def detail(self) -> str:
        return f"{self}；沒採用的片段：{json.dumps(self.dropped, ensure_ascii=False)}"


class ScopeEmpty(Exception):
    """某一格找不到內容（或引用的片段都對不上原文）。"""

    def __init__(self, slot_title: str, dropped: list[dict[str, Any]]) -> None:
        super().__init__(f"規則書裡找不到「{slot_title}」的內容")
        self.slot_title = slot_title
        self.dropped = dropped

    @property
    def detail(self) -> str:
        return f"{self}；沒採用的片段：{json.dumps(self.dropped, ensure_ascii=False)}"


def _squash(text: str) -> str:
    """比對時忽略空白與換行的差異（OCR 的換行位置常和 LLM 照抄的不同）。"""
    return re.sub(r"\s+", "", text)


def build_input(pages: list[RulebookPage]) -> str:
    parts = []
    for page in pages:
        parts += [f"=== 規則書第 {page.page} 頁 ===", page.text, ""]
    return "\n".join(parts).rstrip()


REWRITE_REQUEST = """上一次的輸出漏了這幾頁：{pages}。
每一頁都要有去處：放進 setup、round、win 其中一格，或放進 excluded 並寫 reason。
請重新輸出完整的結果（不是只輸出補上的部分）。

上一次的輸出：
{previous}"""


def classify_scope(llm: LLMProvider, pages: list[RulebookPage]) -> ScopeResult:
    """把整本分成三格；檢查引用；每一頁都要有去處（在某一格的片段裡，或在排除清單裡）。

    有頁沒去處就改寫一次（2026-11-22 永傑決定），仍沒有拋 ScopeIncomplete；
    某一格空了拋 ScopeEmpty。
    """
    llm_input = build_input(pages)
    raw = llm.generate_json(instructions=INSTRUCTIONS, input=llm_input, schema=SCHEMA)
    result = _parse(raw, pages)
    missing = _pages_without_place(result, pages)
    if missing:
        listed = "、".join(f"第 {page} 頁" for page in missing)
        rewrite = REWRITE_REQUEST.format(
            pages=listed, previous=json.dumps(raw, ensure_ascii=False, indent=2)
        )
        raw = llm.generate_json(
            instructions=INSTRUCTIONS, input=f"{llm_input}\n\n{rewrite}", schema=SCHEMA
        )
        result = _parse(raw, pages)
        missing = _pages_without_place(result, pages)
        if missing:
            raise ScopeIncomplete(missing, result.dropped)
    for slot in result.slots:
        if not slot.excerpts:
            raise ScopeEmpty(slot.title, result.dropped)
    return result


def _parse(raw: dict[str, Any], pages: list[RulebookPage]) -> ScopeResult:
    texts = {page.page: _squash(page.text) for page in pages}
    dropped: list[dict[str, Any]] = []

    def accept(slot: str, item: dict[str, Any]) -> bool:
        page, quote = item.get("page"), (item.get("quote") or "").strip()
        problem = None
        if page not in texts:
            problem = "頁碼不在規則書裡"
        elif len(_squash(quote)) < MIN_QUOTE_CHARS:
            problem = "片段太短"
        elif _squash(quote) not in texts[page]:
            problem = "片段不在那一頁"
        if problem:
            dropped.append({"slot": slot, "page": page, "quote": quote, "problem": problem})
            return False
        return True

    slots = []
    for key, title in SLOTS:
        excerpts = [
            Excerpt(item["page"], item["quote"].strip())
            for item in raw.get(key, [])
            if accept(key, item)
        ]
        slots.append(ScopeSlot(key, title, excerpts))
    excluded = [
        ExcludedExcerpt(item["page"], item["quote"].strip(), item.get("reason", ""))
        for item in raw.get("excluded", [])
        if accept("excluded", item)
    ]
    return ScopeResult(slots, excluded, dropped)


def _pages_without_place(result: ScopeResult, pages: list[RulebookPage]) -> list[int]:
    """沒有任何採用的片段（三格或排除清單）的頁；引用對不上原文的不算。"""
    placed = {e.page for slot in result.slots for e in slot.excerpts}
    placed |= {e.page for e in result.excluded}
    return sorted(page.page for page in pages if page.page not in placed)


def scope_from_dict(data: dict[str, Any]) -> ScopeResult:
    """從資料庫存的 classification 重建。"""
    return ScopeResult(
        slots=[
            ScopeSlot(s["key"], s["title"], [Excerpt(**e) for e in s["excerpts"]])
            for s in data.get("slots", [])
        ],
        excluded=[ExcludedExcerpt(**e) for e in data.get("excluded", [])],
        dropped=list(data.get("dropped", [])),
    )


def slot_pages(slot: ScopeSlot, lang: str) -> list[RulebookPage]:
    """這一格的片段，依頁合併成「頁面」（給涵蓋檢查用：只拿這一格的內容來比對）。"""
    by_page: dict[int, list[str]] = {}
    for excerpt in slot.excerpts:
        by_page.setdefault(excerpt.page, []).append(excerpt.text)
    return [RulebookPage(lang, page, "\n".join(texts)) for page, texts in sorted(by_page.items())]
