"""用自然語言修改規則影片（spec rules-video-revision，design.md D2–D5、D8）。

店員用一句話描述要改什麼 → LLM 回傳受影響的段的完整新內容 → 程式只取代那幾段，
檢查不通過就改寫一次。LLM 判斷做不到、或用了五種以外的動作時，改為提供替代做法並記錄需求；
多段都符合時列出候選段。每次寫入前備份，每段記下修改紀錄。
"""

import copy
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domains.rules_qa import video_prompts
from app.domains.rules_qa.video_coverage import CoverageReport, video_hash
from app.domains.rules_qa.video_script import FORBIDDEN_WORD, Term, _texts
from app.integrations.llm import LLMProvider
from app.integrations.llm.types import JsonSchema
from app.integrations.video import VideoDataError, parse_video
from app.integrations.video.model import (
    ACTIONS,
    ANIMS,
    HIGHLIGHT_STYLES,
    LABEL_POSITIONS,
    LABEL_STYLES,
    SHAPES,
    TRANSITIONS,
)
from app.integrations.video.templates import DEFAULT_TEMPLATE, SLOT_KINDS, TEMPLATES

# 欄位差異的分類（修改紀錄的 changed、LLM 的 requested 用同一組）
CATEGORIES = (
    "narration",
    "subtitle",
    "keywords",
    "cues",
    "beats",
    "slots",
    "highlights",
    "labels",
    "timing",
    "template",
    "transition_in",
    "source_pages",
)
BEAT_FIELDS = ("narration", "subtitle", "keywords", "cues")
SEGMENT_FIELDS = (
    "slots",
    "highlights",
    "labels",
    "timing",
    "template",
    "transition_in",
    "source_pages",
)
_DEFAULTS: dict[str, Any] = {"template": DEFAULT_TEMPLATE, "transition_in": "cut"}
NOT_VISUAL = ("state", "revisions")  # 狀態與修改紀錄由程式維護，不交給 LLM
MAX_ALTERNATIVES = 3
MANY_SEGMENTS = 2  # 超過這個段數時提醒店員確認

REVISIONS_DIR = "revisions"
PENDING_FILE = "pending.json"
REQUESTS_FILE = "requests.json"


INSTRUCTIONS = f"""你是桌遊規則教學影片的編輯，依店員的修改要求修改影片的段資料（video.json 的段）。
輸入有：修改要求、版型能做的事、目前每一段的內容（JSON）、用語對照。

1. 只改修改要求點名的段與欄位。**沒被點名的欄位原文不動**：旁白、字幕、槽位、動作、highlight、
   label 都一字不改，除非修改要求明確提到。
2. 可以做時 kind 填 revise：segments 列出受影響的每一段，segment_json 是這段修改後的**完整**內容
   （video.json 的段格式，JSON 字串，不含 state、revisions）。segment_key 不可改，不可新增或刪除段。
   requested 列出修改要求點名的欄位分類（{"、".join(CATEGORIES)}）；summary 用一句話說明改了什麼。
3. 版型做不到時（例如要用不存在的動作或版型）kind 填 unsupported：reason 說明做不到的原因，
   alternatives 提出 1 到 {MAX_ALTERNATIVES} 個只用現有能力、最接近要求的替代做法，
   每個附上受影響的段的完整內容。不要硬改。
4. 多段都符合修改要求、無法判斷要改哪一段時，kind 填 ambiguous，candidates 列出候選段與理由。
   輸入有「指定段」時，只能改那一段。
5. 動作（cue 的 do）只能用：{"、".join(ACTIONS)}。
6. 遊戲教學內容不使用「{FORBIDDEN_WORD}」，改用局、輪、回合、階段、天；照用語對照表用詞。"""

ALTERNATIVES_REQUEST = """上一次的輸出用了本版不支援的動作：{actions}。
不要改寫成用這些動作。請把 kind 填 unsupported，reason 說明做不到的原因，
並提出 1 到 {limit} 個只用 {supported} 的替代做法，每個附上受影響的段的完整內容。"""

_ENTRY = {
    "type": "object",
    "properties": {
        "segment_key": {"type": "string"},
        "requested": {"type": "array", "items": {"type": "string", "enum": list(CATEGORIES)}},
        "summary": {"type": "string"},
        # 段資料以 JSON 字串表示：槽位名稱不固定，strict schema 無法描述；
        # 也不把 do 限制成五種，程式才看得到 AI 想用什麼動作（design.md D2 第 4 步）
        "segment_json": {"type": "string"},
    },
    "required": ["segment_key", "requested", "summary", "segment_json"],
    "additionalProperties": False,
}

SCHEMA = JsonSchema(
    name="rules_video_revision",
    schema={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["revise", "unsupported", "ambiguous"]},
            "reason": {"type": ["string", "null"]},
            "segments": {"type": "array", "items": _ENTRY},
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "segments": {"type": "array", "items": _ENTRY},
                    },
                    "required": ["title", "description", "segments"],
                    "additionalProperties": False,
                },
            },
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "segment_key": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["segment_key", "reason"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["kind", "reason", "segments", "alternatives", "candidates"],
        "additionalProperties": False,
    },
)


class RevisionError(Exception):
    """輸入或待選檔有問題；這時不寫入 video.json。"""


class RevisionRejected(Exception):
    """改寫一次後仍不通過檢查。errors 是最後一次的錯誤，outputs 是 LLM 的原始輸出。"""

    def __init__(self, errors: list[str], outputs: list[dict[str, Any]]) -> None:
        self.errors = errors
        self.outputs = outputs
        super().__init__("\n".join(errors))


@dataclass
class Entry:
    segment_key: str
    segment: dict[str, Any]
    requested: list[str]
    summary: str
    changed: list[str] = field(default_factory=list)

    @property
    def unrequested(self) -> list[str]:
        return [c for c in self.changed if c not in self.requested]

    def to_json(self) -> dict[str, Any]:
        return {
            "segment_key": self.segment_key,
            "segment": self.segment,
            "requested": self.requested,
            "summary": self.summary,
        }


@dataclass
class Proposal:
    """通過檢查、可以套用的修改。"""

    request: str
    entries: list[Entry]


@dataclass
class Alternative:
    title: str
    description: str
    entries: list[Entry]


@dataclass
class Unsupported:
    request: str
    reason: str
    alternatives: list[Alternative]
    unsupported_actions: list[str] = field(default_factory=list)


@dataclass
class Ambiguous:
    reason: str
    candidates: list[tuple[str, str]]


# --------------------------------------------------------------------------- 產生修改


def propose(
    llm: LLMProvider,
    folder: Path,
    request: str,
    *,
    terms: list[Term],
    only_segment: str | None = None,
) -> Proposal | Unsupported | Ambiguous:
    """請 LLM 修改；回傳通過檢查的提案、替代做法或候選段。改寫一次仍不通過時拋 RevisionRejected。"""
    data = read_video(folder)
    keys = [s["segment_key"] for s in data["segments"]]
    if only_segment is not None and only_segment not in keys:
        raise RevisionError(f"找不到指定的段：{only_segment}（有 {'、'.join(keys)}）")
    llm_input = build_input(data, request, terms, only_segment)
    outputs: list[dict[str, Any]] = []
    errors: list[str] = []
    for attempt in range(2):
        prompt = llm_input
        if attempt:
            prompt += "\n\n" + video_prompts.rewrite_request(errors, outputs[-1])
        raw = llm.generate_json(instructions=INSTRUCTIONS, input=prompt, schema=SCHEMA)
        outputs.append(raw)
        kind = raw.get("kind")
        if kind == "ambiguous" and only_segment is None:
            candidates = [(c["segment_key"], c["reason"]) for c in raw.get("candidates", [])]
            return Ambiguous(raw.get("reason") or "", candidates)
        if kind == "unsupported" and raw.get("alternatives"):
            # 替代做法在產生時就檢查，存進 pending.json 的一定能套用（本機驗收發現）
            errors = _check_alternatives(folder, data, raw, terms)
            if errors:
                continue
            return _unsupported(raw, request, [])
        if kind != "revise":
            errors = [_unexpected_kind(kind, only_segment)]
            continue
        entries, errors = _entries(raw.get("segments", []))
        if errors:
            continue
        actions = _unknown_actions(entries)
        if actions:
            # 用了五種以外的動作：走替代做法，不走改寫（design.md D2 第 4 步）
            return _ask_alternatives(
                llm, llm_input, raw, request, actions, outputs, (folder, data, terms)
            )
        errors = check_entries(folder, data, entries, terms, only_segment)
        if not errors:
            return Proposal(request, entries)
    raise RevisionRejected(errors, outputs)


def _unexpected_kind(kind: Any, only_segment: str | None) -> str:
    if kind == "ambiguous":
        return f"已指定段 {only_segment}，請只修改這一段，kind 填 revise"
    if kind == "unsupported":
        return "kind 是 unsupported 時，alternatives 至少要有一個替代做法"
    return f"kind 必須是 revise、unsupported 或 ambiguous：{kind!r}"


def _ask_alternatives(
    llm: LLMProvider,
    llm_input: str,
    previous: dict[str, Any],
    request: str,
    actions: list[str],
    outputs: list[dict[str, Any]],
    context: tuple[Path, dict[str, Any], list[Term]],
) -> Unsupported:
    prompt = (
        llm_input
        + "\n\n=== 上一次的輸出 ===\n"
        + json.dumps(previous, ensure_ascii=False)
        + "\n\n"
        + ALTERNATIVES_REQUEST.format(
            actions="、".join(actions), limit=MAX_ALTERNATIVES, supported="、".join(ACTIONS)
        )
    )
    raw = llm.generate_json(instructions=INSTRUCTIONS, input=prompt, schema=SCHEMA)
    outputs.append(raw)
    if raw.get("kind") != "unsupported" or not raw.get("alternatives"):
        raise RevisionRejected(
            [f"用了不支援的動作（{'、'.join(actions)}），且沒有取得替代做法"], outputs
        )
    folder, data, terms = context
    errors = _check_alternatives(folder, data, raw, terms)
    if errors:
        raise RevisionRejected(errors, outputs)
    return _unsupported(raw, request, actions)


def _check_alternatives(
    folder: Path, data: dict[str, Any], raw: dict[str, Any], terms: list[Term]
) -> list[str]:
    errors = []
    for alt in raw["alternatives"][:MAX_ALTERNATIVES]:
        entries, problems = _entries(alt.get("segments", []))
        if not problems:
            problems = check_entries(folder, data, entries, terms)
        errors += [f"替代做法「{alt.get('title')}」：{p}" for p in problems]
    return errors


def _unsupported(raw: dict[str, Any], request: str, actions: list[str]) -> Unsupported:
    alternatives = []
    for alt in raw["alternatives"][:MAX_ALTERNATIVES]:
        entries, _ = _entries(alt.get("segments", []))
        alternatives.append(Alternative(alt["title"], alt["description"], entries))
    reason = raw.get("reason") or f"本版不支援的動作：{'、'.join(actions)}"
    return Unsupported(request, reason, alternatives, actions)


def _entries(raw_entries: list[dict[str, Any]]) -> tuple[list[Entry], list[str]]:
    entries, errors = [], []
    for raw in raw_entries:
        key = raw.get("segment_key")
        try:
            segment = json.loads(raw.get("segment_json") or "")
        except json.JSONDecodeError as exc:
            errors.append(f"段 {key} 的 segment_json 不是合法的 JSON：{exc}")
            continue
        if not isinstance(segment, dict):
            errors.append(f"段 {key} 的 segment_json 必須是物件")
            continue
        for name in NOT_VISUAL:
            segment.pop(name, None)
        # LLM 有時在 segment_json 裡省略 segment_key（本機驗收發現）：用外層的補上；
        # 兩邊都有但不一樣時，由 check_entries 報錯
        segment.setdefault("segment_key", key)
        requested = [c for c in raw.get("requested", []) if c in CATEGORIES]
        entries.append(Entry(key, segment, requested, raw.get("summary", "")))
    return entries, errors


def _unknown_actions(entries: list[Entry]) -> list[str]:
    found = set()
    for entry in entries:
        for beat in entry.segment.get("beats", []) or []:
            for cue in (beat.get("cues", []) if isinstance(beat, dict) else []) or []:
                do = cue.get("do") if isinstance(cue, dict) else None
                if isinstance(do, str) and do not in ACTIONS:
                    found.add(do)
    return sorted(found)


def build_input(
    data: dict[str, Any], request: str, terms: list[Term], only_segment: str | None
) -> str:
    segments = [{k: v for k, v in s.items() if k not in NOT_VISUAL} for s in data["segments"]]
    lines = [f"=== 修改要求 ===\n{request}", ""]
    if only_segment:
        lines += [f"=== 指定段 ===\n只能修改段 {only_segment}，其他段不可列出。", ""]
    lines += ["=== 版型能做的事 ===", capabilities(), ""]
    if terms:
        lines.append("=== 用語對照（英文 → 中文；avoid 是不要用的詞）===")
        for term in terms:
            avoid = f"（不要用：{'、'.join(term.avoid)}）" if term.avoid else ""
            lines.append(f"{term.en} → {term.zh}{avoid}")
        lines.append("")
    lines += ["=== 目前每一段的內容（JSON）===", json.dumps(segments, ensure_ascii=False, indent=1)]
    return "\n".join(lines)


def capabilities() -> str:
    return "\n".join(
        [
            f"版型：{'、'.join(TEMPLATES)}",
            f"槽位種類：{'、'.join(SLOT_KINDS)}",
            f"動作（cue 的 do）：{'、'.join(ACTIONS)}",
            f"動作的動畫（anim）：{'、'.join(ANIMS)}",
            f"highlight 形狀：{'、'.join(SHAPES)}；顏色：{'、'.join(HIGHLIGHT_STYLES)}",
            f"label 位置：{'、'.join(LABEL_POSITIONS)}；樣式：{'、'.join(LABEL_STYLES)}",
            f"段的轉場：{'、'.join(TRANSITIONS)}",
        ]
    )


# --------------------------------------------------------------------------- 檢查


def check_entries(
    folder: Path,
    data: dict[str, Any],
    entries: list[Entry],
    terms: list[Term],
    only_segment: str | None = None,
) -> list[str]:
    """段的 key、段資料驗證、用語。通過時順便算出每段的欄位差異（entry.changed）。"""
    errors: list[str] = []
    originals = {s["segment_key"]: s for s in data["segments"]}
    seen: set[str] = set()
    for entry in entries:
        key = entry.segment_key
        if key not in originals:
            errors.append(
                f"段 {key} 不存在：不可新增段，segment_key 不可改（有 {'、'.join(originals)}）"
            )
        elif key in seen:
            errors.append(f"段 {key} 出現了兩次：每段只能列一次")
        elif only_segment is not None and key != only_segment:
            errors.append(f"已指定段 {only_segment}，不可修改段 {key}")
        if entry.segment.get("segment_key") != key:
            errors.append(f"段 {key} 的 segment_json 裡的 segment_key 不一致：不可改 segment_key")
        seen.add(key)
    if not entries:
        errors.append("kind 是 revise 時，segments 至少要有一段")
    if errors:
        return errors

    merged = replace_segments(data, entries)
    try:
        parse_video(merged, folder, draft=not _is_formal(data, folder))
    except VideoDataError as exc:
        errors += exc.errors
    changed = {"segments": [e.segment for e in entries]}
    for where, text in _texts(changed):
        if FORBIDDEN_WORD in text:
            errors.append(
                f"{where}使用了「{FORBIDDEN_WORD}」，請改用局、輪、回合、階段、天等用詞：{text}"
            )
        for term in terms:
            for word in term.avoid:
                if word in text:
                    errors.append(f"{where}用了「{word}」，請改用「{term.zh}」：{text}")
    for entry in entries:
        entry.changed = diff_categories(originals[entry.segment_key], entry.segment)
    return errors


def _is_formal(data: dict[str, Any], folder: Path) -> bool:
    """原本的段資料能用正式模式載入時，修改後也要通過正式模式；草稿就用草稿模式檢查。"""
    try:
        parse_video(data, folder, draft=False)
    except VideoDataError:
        return False
    return True


def diff_categories(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """新舊段的欄位差異，依 CATEGORIES 的順序列出。"""
    changed: set[str] = set()
    for name in SEGMENT_FIELDS:
        if _value(old, name) != _value(new, name):
            changed.add(name)
    old_beats = {b.get("beat_key"): b for b in old.get("beats", []) or []}
    new_beats = {b.get("beat_key"): b for b in new.get("beats", []) or []}
    if list(old_beats) != list(new_beats):
        changed.add("beats")
    for key in old_beats.keys() & new_beats.keys():
        for name in BEAT_FIELDS:
            if _value(old_beats[key], name) != _value(new_beats[key], name):
                changed.add(name)
    return [c for c in CATEGORIES if c in changed]


def _value(data: dict[str, Any], name: str) -> Any:
    value = data.get(name)
    if value in (None, [], {}):
        return _DEFAULTS.get(name)
    return value


def replace_segments(data: dict[str, Any], entries: list[Entry]) -> dict[str, Any]:
    by_key = {e.segment_key: e.segment for e in entries}
    merged = copy.deepcopy(data)
    merged["segments"] = [
        copy.deepcopy(by_key.get(s["segment_key"], s)) for s in merged["segments"]
    ]
    return merged


# --------------------------------------------------------------------------- 套用與紀錄


def read_video(folder: Path) -> dict[str, Any]:
    path = folder / "video.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RevisionError(f"找不到 {path}") from exc
    except json.JSONDecodeError as exc:
        raise RevisionError(f"{path} 不是合法的 JSON：{exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
        raise RevisionError(f"{path} 沒有 segments")
    return data


def current_hash(folder: Path) -> str:
    return video_hash((folder / "video.json").read_bytes())


def apply_entries(
    folder: Path,
    entries: list[Entry],
    request: str,
    *,
    kind: str = "revision",
    by: str = "staff",
    now: datetime | None = None,
) -> int:
    """備份後取代各段、寫修改紀錄；回傳這次的修改編號。沒有任何變動的段不記錄。"""
    data = read_video(folder)
    originals = {s["segment_key"]: s for s in data["segments"]}
    revisions = folder / REVISIONS_DIR
    revisions.mkdir(parents=True, exist_ok=True)
    number = _next_number(revisions)
    (revisions / f"{number}-before.json").write_bytes((folder / "video.json").read_bytes())

    at = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    replaced: dict[str, dict[str, Any]] = {}
    for entry in entries:
        old = originals[entry.segment_key]
        entry.changed = diff_categories(old, entry.segment)
        new = copy.deepcopy(entry.segment)
        new["state"] = {
            k: v for k, v in (old.get("state") or {}).items() if k != "content_hash"
        } | {"status": "stale"}
        record = {
            "number": number,
            "at": at,
            "by": by,
            "kind": kind,
            "request": request,
            "changed": entry.changed,
            "unrequested": entry.unrequested,
            "summary": entry.summary,
        }
        new["revisions"] = [*(old.get("revisions") or []), record]
        replaced[entry.segment_key] = new
    data["segments"] = [replaced.get(s["segment_key"], s) for s in data["segments"]]
    write_json(folder / "video.json", data)
    return number


def _next_number(revisions: Path) -> int:
    numbers = []
    for path in revisions.glob("*-before.json"):
        prefix = path.name.split("-", 1)[0]
        if prefix.isdigit():
            numbers.append(int(prefix))
    return max(numbers, default=0) + 1


def mark_rendered(folder: Path, content_hashes: dict[str, str]) -> list[str]:
    """render 成功後：被修改過（stale）的段改為 rendered 並記下 content_hash；回傳更新的段。

    沒有 stale 的段時不動 video.json（不重寫手寫檔的格式）。
    """
    data = read_video(folder)
    updated = []
    for segment in data["segments"]:
        state = segment.get("state") or {}
        key = segment["segment_key"]
        if state.get("status") == "stale" and key in content_hashes:
            segment["state"] = state | {"status": "rendered", "content_hash": content_hashes[key]}
            updated.append(key)
    if updated:
        write_json(folder / "video.json", data)
    return updated


def save_proposal(folder: Path, proposal: Proposal) -> Path:
    return _save_pending(
        folder,
        {
            "kind": "proposal",
            "request": proposal.request,
            "video_hash": current_hash(folder),
            "segments": [e.to_json() for e in proposal.entries],
        },
    )


def save_alternatives(folder: Path, result: Unsupported) -> Path:
    path = _save_pending(
        folder,
        {
            "kind": "alternatives",
            "request": result.request,
            "reason": result.reason,
            "video_hash": current_hash(folder),
            "alternatives": [
                {
                    "title": a.title,
                    "description": a.description,
                    "segments": [e.to_json() for e in a.entries],
                }
                for a in result.alternatives
            ],
        },
    )
    record_request(folder, result)
    return path


def _save_pending(folder: Path, data: dict[str, Any]) -> Path:
    path = folder / REVISIONS_DIR / PENDING_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, data)
    return path


def clear_pending(folder: Path) -> None:
    (folder / REVISIONS_DIR / PENDING_FILE).unlink(missing_ok=True)


def load_pending(folder: Path, kind: str) -> dict[str, Any]:
    """讀取待選檔；種類不對或 video.json 在那之後被改過時拋 RevisionError。"""
    path = folder / REVISIONS_DIR / PENDING_FILE
    if not path.is_file():
        what = "dry-run 的提案" if kind == "proposal" else "替代做法"
        raise RevisionError(f"沒有待套用的{what}（{REVISIONS_DIR}/{PENDING_FILE} 不存在）")
    pending = json.loads(path.read_text(encoding="utf-8"))
    if pending.get("kind") != kind:
        if kind == "proposal":
            raise RevisionError("pending.json 是替代做法，請用 --choose <編號> 選擇")
        raise RevisionError("pending.json 是 dry-run 的提案，請用 --apply 套用")
    if pending.get("video_hash") != current_hash(folder):
        raise RevisionError(
            "video.json 在產生提案（dry-run）之後被改過，pending.json 已過期，請重跑 revise"
        )
    return pending


def entries_from_pending(raw_entries: list[dict[str, Any]]) -> list[Entry]:
    return [
        Entry(e["segment_key"], e["segment"], list(e.get("requested", [])), e.get("summary", ""))
        for e in raw_entries
    ]


def record_request(folder: Path, result: Unsupported, now: datetime | None = None) -> None:
    """超出版型能力的需求記到 requests.json（第 3 階段的輸入）。"""
    path = folder / REVISIONS_DIR / REQUESTS_FILE
    records = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    records.append(
        {
            "at": (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "request": result.request,
            "reason": result.reason,
            "unsupported_actions": result.unsupported_actions,
            "alternatives": [a.title for a in result.alternatives],
        }
    )
    write_json(path, records)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- 寫入後的涵蓋檢查


def coverage_warnings(report: CoverageReport, beat_keys: set[str]) -> list[str]:
    """只留下和被改的段有關的結果（design.md D8）。"""
    warnings = []
    unlinked = []
    for rule in report.rules:
        if rule.is_hint or not rule.has_issue:
            continue
        keys = set(rule.narration.beat_keys + rule.subtitle.beat_keys)
        if keys & beat_keys:
            parts = []
            for label, track in (("旁白", rule.narration), ("字幕", rule.subtitle)):
                if track.status != "complete":
                    missing = f"（缺：{track.missing}）" if track.missing else ""
                    parts.append(f"{label}{_STATUS.get(track.status, track.status)}{missing}")
            warnings.append(f"規則 {rule.rule_id}「{rule.source}」：{'；'.join(parts)}")
        elif not keys:
            unlinked.append(rule.rule_id)
    for problem in report.problems:
        if problem.beat_key in beat_keys:
            warnings.append(f"句子 {problem.beat_key}：{problem.reason}（{problem.text}）")
    if unlinked:
        warnings.append(
            f"另有 {len(unlinked)} 條規則沒有對應的句子（{'、'.join(unlinked)}），"
            "可能和這次修改無關"
        )
    return warnings


_STATUS = {"incomplete": "不完整", "missing": "未涵蓋"}
