"""AI 從規則書頁面產生規則影片的段資料草稿（spec rules-video-script）。

流程：讀規則書頁面文字與用語對照表 → 交給 LLM（generate_json）→ 轉成段資料（草稿模式：
照片待拍、區域待量測）→ 檢查。不通過就帶著錯誤清單要求 LLM 改寫一次；仍不通過就失敗，
並把兩次原始輸出交給呼叫端保存（與規則問答「改寫一次」的做法一致）。
"""

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, ValidationError

from app.domains.rules_qa import video_prompts
from app.integrations.llm import LLMProvider
from app.integrations.video import VideoDataError, load_video, parse_video

FORBIDDEN_WORD = "次"  # AGENTS.md 10.2：遊戲教學內容不使用「次」
PAGE_FILE = re.compile(r"^([a-z]{2})-(\d+)\.txt$")
TERM_CATEGORIES = ("generic", "single")
CATEGORY_LABELS = {"generic": "泛稱", "single": "單一種牌"}
REPRESENTATIVE = "代表牌"


class ScriptInputError(Exception):
    """輸入檔案不存在或格式不對；這時還沒有呼叫 LLM。"""


class ScriptRejected(Exception):
    """改寫一次後仍不通過檢查。errors 是最後一次的錯誤，outputs 是兩次 LLM 原始輸出。"""

    def __init__(self, errors: list[str], outputs: list[dict[str, Any]]) -> None:
        self.errors = errors
        self.outputs = outputs
        super().__init__("\n".join(errors))


@dataclass(frozen=True)
class RulebookPage:
    lang: str
    page: int
    text: str


@dataclass(frozen=True)
class Term:
    en: str
    zh: str
    key: str | None = None
    avoid: tuple[str, ...] = ()
    # generic：泛稱（一整類的牌，素材必須寫代表牌說明）；single：單一種牌（素材不可標代表牌）
    category: str | None = None


@dataclass(frozen=True)
class ScriptRequest:
    chapter_number: int
    chapter_title: str
    pages: list[RulebookPage]
    terms: list[Term]
    game_key: str
    title: str
    voice: str | None = None
    # 參考頁：只供查牌名與分類（例如判斷代表牌），不可寫成旁白，也不可列在 source_pages
    reference_pages: list[RulebookPage] = field(default_factory=list)
    # 整個遊戲一支影片的三格（video_scope.ScopeSlot）；None＝單章模式（命令列與舊的單章專案）。
    # 整本模式時 pages 是三格用到的頁（source_pages 只能用這些頁）
    scope: list[Any] | None = None


# --------------------------------------------------------------------------- 輸入


def load_pages(folder: Path, names: list[str]) -> list[RulebookPage]:
    """讀取規則書頁面文字；檔名必須是 <語言>-<頁碼>.txt，例如 en-005.txt。"""
    pages = []
    for name in names:
        path = folder / name
        match = PAGE_FILE.match(path.name)
        if match is None:
            raise ScriptInputError(
                f"規則書頁面的檔名必須是 <語言>-<頁碼>.txt，例如 en-005.txt：{name}"
            )
        if not path.is_file():
            raise ScriptInputError(f"找不到規則書頁面：{name}")
        pages.append(
            RulebookPage(
                lang=match.group(1),
                page=int(match.group(2)),
                text=path.read_text(encoding="utf-8").strip(),
            )
        )
    if not pages:
        raise ScriptInputError("至少要指定一頁規則書（--pages）")
    return pages


def load_terms(path: Path) -> list[Term]:
    """讀取本機的用語對照表 terms.json；規則與 API 共用（parse_terms、term_conflicts）。"""
    if not path.is_file():
        raise ScriptInputError(f"找不到用語對照表：{path.name}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScriptInputError(f"{path.name} 不是合法的 JSON：{exc}") from exc
    if not isinstance(raw, list):
        raise ScriptInputError(f"{path.name} 必須是陣列")
    if len(raw) > TERMS_MAX:
        raise ScriptInputError(f"{path.name} 最多 {TERMS_MAX} 筆，目前 {len(raw)} 筆")
    try:
        entries = _TERM_LIST.validate_python(raw)
    except ValidationError as exc:
        problems = []
        for error in exc.errors():
            index, *where = error["loc"]
            field_name = ".".join(str(part) for part in where) or "整筆"
            problems.append(f"第 {int(index) + 1} 筆的 {field_name}：{error['msg']}")
        raise ScriptInputError(
            f"{path.name} 格式錯誤（category 只能是 generic＝泛稱、single＝單一種牌）："
            + "；".join(problems)
        ) from exc
    terms = [entry.to_term() for entry in entries]
    conflicts = term_conflicts(terms)
    if conflicts:
        raise ScriptInputError(f"{path.name}：" + "；".join(c.message for c in conflicts))
    return terms


# --------------------------------------------------------------------------- 用語對照表的共用規則
# 命令列（load_terms）與 API（PUT /games/{id}/video-terms）用同一份規則
# （add-rules-video-mobile design.md D4）。

TERMS_MAX = 500
TERM_TEXT_MAX = 100
TermText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TERM_TEXT_MAX)
]


class TermIn(BaseModel):
    """對照表的一筆。avoid 不允許空字串：空字串會比對到所有文字。"""

    en: TermText
    zh: TermText
    key: TermText | None = None
    avoid: list[TermText] = Field(default_factory=list)
    category: Literal["generic", "single"] | None = None

    def to_term(self) -> Term:
        return Term(self.en, self.zh, self.key, tuple(self.avoid), self.category)


_TERM_LIST = TypeAdapter(list[TermIn])


@dataclass(frozen=True)
class TermConflict:
    kind: str  # duplicate_en | category_conflict
    message: str


def term_conflicts(terms: list[Term]) -> list[TermConflict]:
    """en 不能重複；同一個 key 的 category 必須一致。都是去掉前後空白、不分大小寫後比對。

    key 可以重複：規則書常用兩個英文名稱指同一個區域，例如 White Rose placement area 與
    Sanctuary 都對到 white_rose_zone。只有兩筆都填了 category 才比較。
    """
    conflicts: list[TermConflict] = []
    by_en: dict[str, list[int]] = {}
    for number, term in enumerate(terms, start=1):
        by_en.setdefault(term.en.strip().casefold(), []).append(number)
    for numbers in by_en.values():
        if len(numbers) > 1:
            listed = "、".join(str(n) for n in numbers)
            conflicts.append(
                TermConflict(
                    "duplicate_en",
                    f"en 重複：「{terms[numbers[0] - 1].en}」（第 {listed} 筆）",
                )
            )
    by_key: dict[str, list[tuple[int, Term]]] = {}
    for number, term in enumerate(terms, start=1):
        if term.key:
            by_key.setdefault(term.key.strip().casefold(), []).append((number, term))
    for entries in by_key.values():
        categories = {t.category for _, t in entries if t.category is not None}
        if len(categories) > 1:
            listed = "、".join(
                f"第 {n} 筆 {t.category}" for n, t in entries if t.category is not None
            )
            conflicts.append(
                TermConflict(
                    "category_conflict",
                    f"key {entries[0][1].key} 的 category 不一致：{listed}",
                )
            )
    return conflicts


def build_input(request: ScriptRequest) -> str:
    header = (
        ["範圍：整個遊戲（開局、走完一輪、獲勝方式三個章節）"]
        if request.scope is not None
        else [f"章節：第 {request.chapter_number} 章「{request.chapter_title}」"]
    )
    lines = [
        *header,
        "",
        "用語對照表（英文 → 中文；key 是段資料中使用的名稱；泛稱或單一種牌；不要用的譯法）：",
    ]
    for term in request.terms:
        line = f"- {term.en} → {term.zh}"
        if term.key:
            line += f"（key：{term.key}）"
        if term.category:
            line += f"（{CATEGORY_LABELS[term.category]}）"
        if term.avoid:
            line += f"（不要用：{'、'.join(term.avoid)}）"
        lines.append(line)
    if request.scope is not None:
        for slot in request.scope:
            lines += ["", f"##### {slot.key}（{slot.title}）的原文片段 #####"]
            for excerpt in slot.excerpts:
                lines += [f"--- 規則書第 {excerpt.page} 頁 ---", excerpt.text]
        return "\n".join(lines)
    for page in request.pages:
        lines += ["", f"=== 本章內容：規則書第 {page.page} 頁（{page.lang}）===", page.text]
    for page in request.reference_pages:
        lines += [
            "",
            f"=== 參考資料：規則書第 {page.page} 頁（{page.lang}）"
            "——只供查牌名與牌的分類，不可寫成旁白、字幕或畫面文字，也不可列在 source_pages ===",
            page.text,
        ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- 產生


def generate_script(
    llm: LLMProvider,
    request: ScriptRequest,
    base_dir: Path,
    cleanup_log: list["CleanupRecord"] | None = None,
) -> dict[str, Any]:
    """回傳通過檢查的段資料（video.json 的內容）；改寫一次仍不通過時拋 ScriptRejected。

    每次 LLM 輸出都先做格式小錯的自動清理（C1–C4），清了什麼記進 cleanup_log；清理後照樣檢查。
    """
    llm_input = build_input(request)
    whole_game = request.scope is not None
    instructions = (
        video_prompts.WHOLE_GAME_INSTRUCTIONS if whole_game else video_prompts.INSTRUCTIONS
    )
    schema = video_prompts.WHOLE_GAME_SCHEMA if whole_game else video_prompts.SCRIPT_SCHEMA
    outputs: list[dict[str, Any]] = []
    errors: list[str] = []
    for attempt in range(2):
        prompt = llm_input
        if attempt:
            prompt += "\n\n" + video_prompts.rewrite_request(errors, outputs[-1])
        raw = llm.generate_json(instructions=instructions, input=prompt, schema=schema)
        outputs.append(raw)
        cleaned, records = clean_format(raw)
        if cleanup_log is not None:
            cleanup_log += [
                CleanupRecord(r.rule, r.where, r.before, r.after, attempt + 1) for r in records
            ]
        try:
            data = to_video_data(cleaned, request)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            errors = [f"輸出格式不符合 schema：{exc!r}"]
            continue
        errors = check_script(data, request, base_dir)
        if not errors:
            return data
    raise ScriptRejected(errors, outputs)


# --------------------------------------------------------------------------- 格式小錯的自動清理

CLEANUP_RULES = {
    "C1": "「@」「.」前後的空白",
    "C2": "開頭、結尾的空白",
    "C3": "全形分隔符號（＠、．）",
    "C4": "cue target 的 highlight:／label: 前綴",
}
_SEPARATOR_SPACES = re.compile(r"\s*([@.])\s*")
_PREFIX = re.compile(r"^(highlight|label)\s*:\s*(.+)$")


@dataclass(frozen=True)
class CleanupRecord:
    rule: str  # C1–C4
    where: str
    before: str
    after: str
    attempt: int = 1  # 第幾次 LLM 輸出


def clean_format(raw: dict[str, Any]) -> tuple[dict[str, Any], list[CleanupRecord]]:
    """只清 C1–C4 四種格式小錯，回傳清理後的複本與紀錄；其他內容一律不動。"""
    data = json.loads(json.dumps(raw))
    records: list[CleanupRecord] = []

    def strip(obj: dict[str, Any], field_name: str, where: str) -> None:  # C2
        value = obj.get(field_name)
        if isinstance(value, str) and value != value.strip():
            obj[field_name] = value.strip()
            records.append(CleanupRecord("C2", f"{where} 的 {field_name}", value, value.strip()))

    def target(obj: dict[str, Any], field_name: str, where: str) -> None:  # C2、C3、C1
        strip(obj, field_name, where)
        value = obj.get(field_name)
        if not isinstance(value, str):
            return
        full = value.replace("＠", "@").replace("．", ".")
        if full != value:
            records.append(CleanupRecord("C3", f"{where} 的 {field_name}", value, full))
        spaced = _SEPARATOR_SPACES.sub(lambda m: m.group(1), full)
        if spaced != full:
            records.append(CleanupRecord("C1", f"{where} 的 {field_name}", full, spaced))
        obj[field_name] = spaced

    for i, asset in enumerate(data.get("assets", [])):
        where = f"素材 {asset.get('asset_key', i)}"
        strip(asset, "asset_key", where)
        names = asset.get("regions")
        if isinstance(names, list):
            stripped = [n.strip() if isinstance(n, str) else n for n in names]
            for before, after in zip(names, stripped, strict=True):
                if before != after:
                    records.append(CleanupRecord("C2", f"{where} 的區域名稱", before, after))
            asset["regions"] = stripped

    for segment in data.get("segments", []):
        seg = f"段 {segment.get('segment_key')}"
        strip(segment, "segment_key", seg)
        for slot_name in ("main", "sidebar"):
            slot = segment.get(slot_name) or {}
            strip(slot, "asset_key", f"{seg} {slot_name}")
            for item in slot.get("items", []) if slot_name == "main" else []:
                for field_name in ("item_key", "asset_key", "back_asset_key"):
                    strip(item, field_name, f"{seg} 項 {item.get('item_key')}")
        for kind in ("highlights", "labels"):
            for overlay in segment.get(kind, []):
                where = f"{seg} {kind[:-1]} {overlay.get('key')}"
                strip(overlay, "key", where)
                target(overlay, "target", where)
        overlay_keys = {
            "highlight": {h.get("key") for h in segment.get("highlights", [])},
            "label": {lab.get("key") for lab in segment.get("labels", [])},
        }
        for b, beat in enumerate(segment.get("beats", []), start=1):
            for c, cue in enumerate(beat.get("cues", []), start=1):
                where = f"{seg} 第 {b} 句 cue {c}"
                target(cue, "target", where)
                target(cue, "to", where)
                value = cue.get("target")
                match = _PREFIX.match(value) if isinstance(value, str) else None
                if match and match.group(2) in overlay_keys[match.group(1)]:  # C4
                    cue["target"] = match.group(2)
                    records.append(CleanupRecord("C4", f"{where} 的 target", value, match.group(2)))
    return data, records


def to_video_data(raw: dict[str, Any], request: ScriptRequest) -> dict[str, Any]:
    """LLM 輸出 → video.json 的格式（草稿：照片待拍、區域待量測）。"""
    page_lang = {p.page: p.lang for p in request.pages}
    chapter_key = f"c{request.chapter_number}"
    if request.scope is not None:
        # 整本：三個 chapter，依開局、走完一輪、獲勝方式的順序
        chapters = [
            {"chapter_key": slot.key, "number": number, "title": slot.title}
            for number, slot in enumerate(request.scope, start=1)
        ]
    else:
        chapters = [
            {
                "chapter_key": chapter_key,
                "number": request.chapter_number,
                "title": request.chapter_title,
            }
        ]
    order = {c["chapter_key"]: i for i, c in enumerate(chapters)}
    data: dict[str, Any] = {
        "format_version": 1,
        "game_key": request.game_key,
        "title": request.title,
        "chapters": chapters,
        "assets": [],
        "segments": [],
    }
    if request.voice:
        data["voice"] = request.voice
    for asset in raw["assets"]:
        entry: dict[str, Any] = {
            "asset_key": asset["asset_key"],
            "kind": asset["kind"],
            "priority": asset["priority"],
            "reason": asset["reason"],
            "file": None,  # 待拍
            "regions": {name: None for name in asset["regions"]},  # 待量測
        }
        if asset.get("shot"):
            entry["shot"] = asset["shot"]
        if asset.get("label"):
            entry["label"] = asset["label"]
        data["assets"].append(entry)

    raw_segments = raw["segments"]
    if request.scope is not None:
        # 依三格的順序排好（同一格內維持原本的順序）；不認得的 chapter 排最後，交給檢查回報
        raw_segments = sorted(raw_segments, key=lambda s: order.get(s.get("chapter"), len(order)))
    beat_number = 0
    for raw_segment in raw_segments:
        segment: dict[str, Any] = {
            "segment_key": raw_segment["segment_key"],
            "chapter_key": raw_segment.get("chapter", chapter_key)
            if request.scope is not None
            else chapter_key,
            "source_pages": [
                {"lang": page_lang.get(page, "?"), "page": page}
                for page in raw_segment["source_pages"]
            ],
            "slots": _slots(raw_segment),
            "highlights": raw_segment["highlights"],
            "labels": raw_segment["labels"],
            "beats": [],
        }
        for raw_beat in raw_segment["beats"]:
            cues = []
            for cue in raw_beat["cues"]:
                entry = {"at": cue["at"], "do": cue["do"], "target": cue["target"]}
                if cue.get("to"):
                    entry["to"] = cue["to"]
                cues.append(entry)
            segment["beats"].append(
                {
                    "beat_key": f"{request.chapter_number}-{beat_number}",
                    "narration": raw_beat["narration"],
                    "subtitle": raw_beat["subtitle"],
                    "cues": cues,
                }
            )
            beat_number += 1
        _hide_shown_targets(segment)
        data["segments"].append(segment)
    return data


def _slots(raw_segment: dict[str, Any]) -> dict[str, Any]:
    slots: dict[str, Any] = {}
    if raw_segment.get("main_title"):
        slots["main_title"] = {"kind": "text", "text": raw_segment["main_title"]}
    main = raw_segment["main"]
    if main["kind"] == "items":
        items = []
        for item in main["items"]:
            entry = {"item_key": item["item_key"], "asset_key": item["asset_key"]}
            if item.get("back_asset_key"):
                entry["back_asset_key"] = item["back_asset_key"]
            items.append(entry)
        slots["main"] = {"kind": "items", "items": items}
    else:
        slots["main"] = {"kind": "asset", "asset_key": main["asset_key"]}
    sidebar = raw_segment["sidebar"]
    if sidebar["kind"] == "asset":
        slots["sidebar"] = {"kind": "asset", "asset_key": sidebar["asset_key"]}
    elif sidebar["kind"] == "text":
        slots["sidebar"] = {"kind": "text", "text": sidebar["text"]}
        if sidebar.get("title"):
            slots["sidebar"]["title"] = sidebar["title"]
    elif sidebar["kind"] == "bullets":
        slots["sidebar"] = {"kind": "bullets", "items": sidebar["items"]}
        if sidebar.get("title"):
            slots["sidebar"]["title"] = sidebar["title"]
    return slots


def _hide_shown_targets(segment: dict[str, Any]) -> None:
    """被 show 的槽位或項目，一開始要隱藏，show 才有意義。"""
    for beat in segment["beats"]:
        for cue in beat["cues"]:
            if cue["do"] != "show":
                continue
            target = cue["target"]
            if target in segment["slots"]:
                segment["slots"][target]["hidden"] = True
            elif "." in target:
                slot_name, _, item_key = target.partition(".")
                slot = segment["slots"].get(slot_name, {})
                for item in slot.get("items", []):
                    if item["item_key"] == item_key:
                        item["hidden"] = True


# --------------------------------------------------------------------------- 檢查


def check_script(data: dict[str, Any], request: ScriptRequest, base_dir: Path) -> list[str]:
    errors: list[str] = []
    try:
        parse_video(data, base_dir, draft=True)
    except VideoDataError as exc:
        errors += exc.errors

    for where, text in _texts(data):
        if FORBIDDEN_WORD in text:
            errors.append(
                f"{where}使用了「{FORBIDDEN_WORD}」，請改用局、輪、回合、階段、天等用詞：{text}"
            )
        for term in request.terms:
            for word in term.avoid:
                if word in text:
                    errors.append(f"{where}用了「{word}」，請改用「{term.zh}」：{text}")

    errors += _check_assets(data, request)
    if request.scope is not None:
        errors += _check_whole_game(data, request)

    chapter_pages = {p.page for p in request.pages}
    reference_pages = {p.page for p in request.reference_pages} - chapter_pages
    allowed = "、".join(str(p) for p in sorted(chapter_pages))
    for segment in data.get("segments", []):
        key = segment.get("segment_key")
        pages = [p["page"] for p in segment.get("source_pages", [])]
        from_reference = [p for p in pages if p in reference_pages]
        outside = [p for p in pages if p not in chapter_pages and p not in reference_pages]
        if from_reference:
            listed = "、".join(str(p) for p in from_reference)
            errors.append(
                f"段 {key} 的 source_pages 用了參考頁：{listed}。參考頁只供查牌名與分類，"
                f"不可當成旁白的依據；source_pages 只能用本章的頁（{allowed}）"
            )
        if outside:
            listed = "、".join(str(p) for p in outside)
            errors.append(
                f"段 {key} 的 source_pages 有輸入以外的頁碼：{listed}（只能用 {allowed}）"
            )
    return errors


def _check_whole_game(data: dict[str, Any], request: ScriptRequest) -> list[str]:
    """整本模式：素材只能實拍（繪製素材到了素材步驟會卡住店員，要在草稿就改掉）；三格都要有段。"""
    errors = []
    for asset in data.get("assets", []):
        if asset.get("kind") != "flat_photo":
            errors.append(
                f"素材 {asset.get('asset_key')} 的 kind 是 {asset.get('kind')}："
                "本版不支援繪製素材，kind 一律用 flat_photo（實拍），立體配件也是拍照"
            )
    used = {segment.get("chapter_key") for segment in data.get("segments", [])}
    for slot in request.scope or []:
        if slot.key not in used:
            errors.append(
                f"「{slot.title}」（chapter={slot.key}）沒有任何一段：三個章節都至少要有一段"
            )
    return errors


def _check_assets(data: dict[str, Any], request: ScriptRequest) -> list[str]:
    """每個素材都要有拍攝說明；泛稱要寫代表牌說明，單一種牌不可標代表牌。"""
    categories = {t.key: t.category for t in request.terms if t.key and t.category}
    errors = []
    for asset in data.get("assets", []):
        key = asset.get("asset_key")
        shot = asset.get("shot")
        if not isinstance(shot, str) or not shot.strip():
            errors.append(f"素材 {key} 沒有拍攝說明（shot）：每個素材都要寫要拍什麼、怎麼拍")
        reason = asset.get("reason") or ""
        category = categories.get(key)
        if category == "generic" and REPRESENTATIVE not in reason:
            errors.append(
                f"素材 {key} 是泛稱，reason 必須寫明"
                "「代表牌：<泛稱>，店員可以替換成同類的任一張牌」"
            )
        if category == "single" and REPRESENTATIVE in reason:
            errors.append(f"素材 {key} 是單一種牌，reason 不可標「代表牌」")
    return errors


def _texts(data: dict[str, Any]) -> list[tuple[str, str]]:
    """所有觀眾會讀到或聽到的文字：旁白、字幕、槽位文字、label。"""
    texts: list[tuple[str, str]] = []
    for segment in data.get("segments", []):
        key = segment.get("segment_key")
        for beat in segment.get("beats", []):
            texts.append((f"段 {key} 句 {beat.get('beat_key')} 的旁白", beat.get("narration", "")))
            texts.append((f"段 {key} 句 {beat.get('beat_key')} 的字幕", beat.get("subtitle", "")))
        for name, slot in segment.get("slots", {}).items():
            for part in (slot.get("text"), slot.get("title"), *slot.get("items", [])):
                if isinstance(part, str):
                    texts.append((f"段 {key} 槽位 {name} 的文字", part))
        for label in segment.get("labels", []):
            texts.append((f"段 {key} label {label.get('key')}", label.get("text", "")))
    return texts


# --------------------------------------------------------------------------- 借用手寫版


def copy_assets_from(data: dict[str, Any], hand_folder: Path, draft_folder: Path) -> list[str]:
    """從手寫版借用同一個 asset_key 的照片檔與區域座標；回傳借用到的 asset_key。"""
    hand = load_video(hand_folder)
    borrowed = []
    for asset in data["assets"]:
        source = hand.assets.get(asset["asset_key"])
        if source is None or source.file is None:
            continue
        target = draft_folder / "assets" / source.file
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(hand.asset_path(source.asset_key), target)
        asset["file"] = source.file
        asset["orientation"] = source.orientation
        for name in asset["regions"]:
            region = source.regions.get(name)
            if region is not None:
                asset["regions"][name] = [region.x, region.y, region.w, region.h]
        borrowed.append(asset["asset_key"])
    return borrowed
