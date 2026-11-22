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

from app.domains.rules_qa.video_script import RulebookPage, place_key
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
5. 每一頁都要有去處：至少有一筆放進某一格或 excluded（圖例、配件清單也一樣，放進 excluded）。

場地清單（places）：
6. 掃整本規則書（包含圖例頁、會被排除的頁），列出所有出現過的場地或區域名稱，同一個名稱只列一筆。
   不是場地的詞（牌名、配件名、角色名）不要列。
   - name：規則書原文裡的名稱，一字不改（例如「死亡區」）。
   - page、quote：名稱出現的那一頁，以及包含這個名稱的原文片段（一字不改地照抄）。
   - kind：board＝印在遊戲板或圖版上、拍照後可以框出來的格子或區域；
     table＝桌上的位置（例如桌面中央、自己面前），不在任何配件上。
   - hint：給店員的一句白話說明，告訴他在照片上要框哪裡；依原文片段寫，不可以猜。
     原文只有圖例、看不出位置時，寫「對照規則書第 N 頁的圖」（N 是那一頁）。"""

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
_PLACE = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "page": {"type": "integer"},
        "quote": {"type": "string"},
        "kind": {"type": "string", "enum": ["board", "table"]},
        "hint": {"type": "string"},
    },
    "required": ["name", "page", "quote", "kind", "hint"],
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
            "places": {"type": "array", "items": _PLACE},
        },
        "required": ["setup", "round", "win", "excluded", "places"],
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
class Place:
    """規則書出現過的場地或區域名稱（2026-11-22 永傑決定）。

    kind：board＝主板上的格子（可以當區域）；table＝桌上的位置（不能當區域）。
    hint：給店員的白話說明，只出現在標區域畫面，不進影片。
    """

    name: str
    page: int
    quote: str
    kind: str
    hint: str


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
    # 場地清單（掃整本，含被排除的頁）
    places: list[Place] = field(default_factory=list)

    @property
    def pages(self) -> list[int]:
        """三格用到的頁（段資料的 source_pages 只能用這些頁）。"""
        return sorted({e.page for slot in self.slots for e in slot.excerpts})

    def to_dict(self) -> dict[str, Any]:
        return {
            "slots": [asdict(slot) for slot in self.slots],
            "excluded": [asdict(e) for e in self.excluded],
            "dropped": self.dropped,
            "places": [asdict(place) for place in self.places],
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

MISSING_PAGES_NOTE = """

這次只給你前一次分類時漏掉的頁。每一頁都要有去處：放進 setup、round、win 其中一格，
或放進 excluded 並寫 reason。只能引用這幾頁的原文；places 沒有新的場地可以給空陣列。"""


def classify_scope(llm: LLMProvider, pages: list[RulebookPage]) -> ScopeResult:
    """把整本分成三格；檢查引用；每一頁都要有去處（在某一格的片段裡，或在排除清單裡）。

    有頁沒去處就改寫一次；仍漏頁就只拿漏掉的頁另外做一次小分類（2026-11-22 永傑決定），
    還是沒有拋 ScopeIncomplete；某一格空了拋 ScopeEmpty。
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
        # 改寫後仍漏頁：只拿漏掉的頁另外做一次小分類（2026-11-22 永傑決定）
        result = _classify_missing(llm, pages, missing, result)
        missing = _pages_without_place(result, pages)
        if missing:
            raise ScopeIncomplete(missing, result.dropped)
    for slot in result.slots:
        if not slot.excerpts:
            raise ScopeEmpty(slot.title, result.dropped)
    return result


def _classify_missing(
    llm: LLMProvider, pages: list[RulebookPage], missing: list[int], result: ScopeResult
) -> ScopeResult:
    """只送漏掉的頁做一次分類，結果併進原本的分類（三格、排除清單、場地清單都保留）。"""
    subset = [page for page in pages if page.page in missing]
    raw = llm.generate_json(
        instructions=INSTRUCTIONS + MISSING_PAGES_NOTE, input=build_input(subset), schema=SCHEMA
    )
    extra = _parse(raw, subset)
    known = {place_key(place.name) for place in result.places}
    return ScopeResult(
        slots=[
            ScopeSlot(slot.key, slot.title, slot.excerpts + more.excerpts)
            for slot, more in zip(result.slots, extra.slots, strict=True)
        ],
        excluded=result.excluded + extra.excluded,
        dropped=result.dropped + extra.dropped,
        places=result.places + [p for p in extra.places if place_key(p.name) not in known],
    )


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

    places, dropped_places = parse_places(raw.get("places", []), pages)
    dropped += dropped_places
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
    return ScopeResult(slots, excluded, dropped, places)


def parse_places(
    raw: list[dict[str, Any]], pages: list[RulebookPage]
) -> tuple[list[Place], list[dict[str, Any]]]:
    """檢查場地清單：引用的片段在那一頁，名稱在片段裡（「區」與「處」視為相同）。

    名稱與片段改用規則書的寫法（例如 AI 寫「水晶放置區」、規則書是「水晶放置處」）。
    同一個名稱只留第一筆；hint 空白時寫「對照規則書第 N 頁的圖」。
    """
    texts = {page.page: _squash(page.text) for page in pages}
    places: list[Place] = []
    dropped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        page, name = item.get("page"), _squash(item.get("name") or "")
        quote = (item.get("quote") or "").strip()
        problem = None
        if page not in texts:
            problem = "頁碼不在規則書裡"
        elif len(name) < 2:
            problem = "名稱太短"
        else:
            book_quote = _find_in(texts[page], quote)
            book_name = _find_in(_squash(book_quote or ""), name)
            if book_quote is None:
                problem = "片段不在那一頁"
            elif book_name is None:
                problem = "名稱不在片段裡"
        if problem:
            dropped.append(
                {
                    "slot": "places",
                    "page": page,
                    "quote": quote,
                    "problem": problem,
                    "name": item.get("name"),
                }
            )
            continue
        if place_key(book_name) in seen:
            continue
        seen.add(place_key(book_name))
        hint = (item.get("hint") or "").strip() or f"對照規則書第 {page} 頁的圖"
        book_quote = _respell(quote, book_quote)
        places.append(Place(book_name, page, book_quote, item.get("kind", "board"), hint))
    return places, dropped


def _respell(original: str, book: str) -> str:
    """保留原本的空白，字改用規則書的寫法（只會差在「區／處」）。"""
    chars = iter(book)
    return "".join(c if c.isspace() else next(chars, c) for c in original)


def _find_in(haystack: str, needle: str) -> str | None:
    """在 haystack（已去空白）找 needle，「區」與「處」視為相同；回傳 haystack 裡的寫法。"""
    needle = _squash(needle)
    if not needle:
        return None
    key = place_key(needle)
    index = place_key(haystack).find(key)
    return haystack[index : index + len(needle)] if index >= 0 else None


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
        places=[Place(**place) for place in data.get("places", [])],
    )


def slot_pages(slot: ScopeSlot, lang: str) -> list[RulebookPage]:
    """這一格的片段，依頁合併成「頁面」（給涵蓋檢查用：只拿這一格的內容來比對）。"""
    by_page: dict[int, list[str]] = {}
    for excerpt in slot.excerpts:
        by_page.setdefault(excerpt.page, []).append(excerpt.text)
    return [RulebookPage(lang, page, "\n".join(texts)) for page, texts in sorted(by_page.items())]


# 「此處」這類一般用語不是場地
_COMMON_WORDS = (
    "此處",
    "好處",
    "用處",
    "到處",
    "之處",
    "各處",
    "何處",
    "相處",
    "處理",
    "處於",
    "區分",
    "區別",
)


def unlisted_place_words(data: dict[str, Any], places: list[Place], terms: list[Any]) -> list[str]:
    """旁白與字幕裡出現、但不在場地清單（也不在用語對照表）的「X區」「X處」詞。

    只記錄、不擋（2026-11-22 永傑決定），供之後觀察。一般用語（此處、處理…）不算。
    詞取「區／處」前面兩個字加上它；前面接著清單裡的名稱就算有在清單。
    """
    known = {place_key(p.name) for p in places}
    known |= {place_key(getattr(t, "zh", "") or "") for t in terms} - {""}
    found: list[str] = []
    for segment in data.get("segments", []):
        for beat in segment.get("beats", []):
            for text in (beat.get("narration", ""), beat.get("subtitle", "")):
                text = _squash(text)
                for i, char in enumerate(text):
                    if char not in "區處":
                        continue
                    if any(text[max(0, i - 1) : i + 2].find(w) >= 0 for w in _COMMON_WORDS):
                        continue
                    prefix = place_key(text[: i + 1])
                    if any(prefix.endswith(k) for k in known):
                        continue
                    word = text[max(0, i - 2) : i + 1]
                    if word not in found:
                        found.append(word)
    return found
