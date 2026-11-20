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
from typing import Any

from app.domains.rules_qa import video_prompts
from app.integrations.llm import LLMProvider
from app.integrations.video import VideoDataError, load_video, parse_video

FORBIDDEN_WORD = "次"  # AGENTS.md 10.2：遊戲教學內容不使用「次」
PAGE_FILE = re.compile(r"^([a-z]{2})-(\d+)\.txt$")


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
    """讀取用語對照表：[{en, zh, key?, avoid?}]。"""
    if not path.is_file():
        raise ScriptInputError(f"找不到用語對照表：{path.name}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScriptInputError(f"{path.name} 不是合法的 JSON：{exc}") from exc
    if not isinstance(raw, list):
        raise ScriptInputError(f"{path.name} 必須是陣列")
    terms = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(k), str) and entry.get(k) for k in ("en", "zh")
        ):
            raise ScriptInputError(f"{path.name} 第 {i + 1} 筆必須有非空的 en 與 zh")
        avoid = entry.get("avoid", [])
        if not isinstance(avoid, list) or not all(isinstance(a, str) for a in avoid):
            raise ScriptInputError(f"{path.name} 第 {i + 1} 筆的 avoid 必須是字串陣列")
        key = entry.get("key")
        terms.append(
            Term(entry["en"], entry["zh"], key if isinstance(key, str) else None, tuple(avoid))
        )
    return terms


def build_input(request: ScriptRequest) -> str:
    lines = [
        f"章節：第 {request.chapter_number} 章「{request.chapter_title}」",
        "",
        "用語對照表（英文 → 中文；key 是段資料中使用的名稱；不要用的譯法）：",
    ]
    for term in request.terms:
        line = f"- {term.en} → {term.zh}"
        if term.key:
            line += f"（key：{term.key}）"
        if term.avoid:
            line += f"（不要用：{'、'.join(term.avoid)}）"
        lines.append(line)
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


def generate_script(llm: LLMProvider, request: ScriptRequest, base_dir: Path) -> dict[str, Any]:
    """回傳通過檢查的段資料（video.json 的內容）；改寫一次仍不通過時拋 ScriptRejected。"""
    llm_input = build_input(request)
    outputs: list[dict[str, Any]] = []
    errors: list[str] = []
    for attempt in range(2):
        prompt = llm_input
        if attempt:
            prompt += "\n\n" + video_prompts.rewrite_request(errors, outputs[-1])
        raw = llm.generate_json(
            instructions=video_prompts.INSTRUCTIONS,
            input=prompt,
            schema=video_prompts.SCRIPT_SCHEMA,
        )
        outputs.append(raw)
        try:
            data = to_video_data(raw, request)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            errors = [f"輸出格式不符合 schema：{exc!r}"]
            continue
        errors = check_script(data, request, base_dir)
        if not errors:
            return data
    raise ScriptRejected(errors, outputs)


def to_video_data(raw: dict[str, Any], request: ScriptRequest) -> dict[str, Any]:
    """LLM 輸出 → video.json 的格式（草稿：照片待拍、區域待量測）。"""
    page_lang = {p.page: p.lang for p in request.pages}
    chapter_key = f"c{request.chapter_number}"
    data: dict[str, Any] = {
        "format_version": 1,
        "game_key": request.game_key,
        "title": request.title,
        "chapters": [
            {
                "chapter_key": chapter_key,
                "number": request.chapter_number,
                "title": request.chapter_title,
            }
        ],
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
        data["assets"].append(entry)

    beat_number = 0
    for raw_segment in raw["segments"]:
        segment: dict[str, Any] = {
            "segment_key": raw_segment["segment_key"],
            "chapter_key": chapter_key,
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
