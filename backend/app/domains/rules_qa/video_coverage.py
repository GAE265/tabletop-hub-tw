"""規則涵蓋檢查（spec rules-video-script「規則涵蓋檢查」）。

用 LLM 把本章規則書頁面的每一條規則，分別與旁白、字幕對照。LLM 的輸入只有本章頁面原文、
編號的旁白與編號的字幕，不給參考頁與草稿的其他內容。「旁白比字幕少條件」由程式依兩邊的狀態判斷。
這是 AI 檢查 AI，可能漏報或誤報，報告只供參考。
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.domains.rules_qa.video_script import RulebookPage
from app.integrations.llm import LLMProvider
from app.integrations.llm.types import JsonSchema
from app.integrations.video.model import Video

STATUS_LABELS = {"complete": "完整", "incomplete": "不完整", "missing": "未涵蓋"}
CATEGORY_LABELS = {"condition": "條件", "action": "動作", "purpose": "目的說明"}
TRACK_LABELS = {"narration": "旁白", "subtitle": "字幕"}
KIND_LABELS = {"contradiction": "與原文相反", "not_in_rulebook": "規則書沒有的規則"}

INSTRUCTIONS = """你是桌遊規則教學影片的審稿者，負責檢查旁白與字幕有沒有完整、正確地講出規則。
輸入有三部分：本章規則書原文、編號的旁白、編號的字幕。

1. 把原文拆成一條一條的規則：每一個「條件＋結果」、每一個步驟、
   每一個限制（例如「直到…或…」）各算一條。source 寫出原文中這條規則的句子。
2. 每條規則分別判斷旁白與字幕：
   - complete：所有條件與結果都講到了（可以換句話說、可以口語）。
   - incomplete：講到了，但少了某個條件、結果或限制；missing 寫出少了什麼。
   - missing：完全沒有講到。
   beat_keys 列出講到這條規則的句子編號（沒有就給空陣列）。
3. 旁白可以比字幕短，但條件不能少；只要少了條件就是 incomplete。
4. problems 列出與原文相反的句子（contradiction），或寫了原文沒有的規則的句子（not_in_rulebook），
   track 標出是旁白（narration）還是字幕（subtitle）。只是換句話說、口語化，不算問題。
5. 只根據輸入的原文判斷，不憑記憶補充規則。
6. 每條規則標出 category：
   - condition（條件）：決定什麼情況下做什麼，例如「如果沒有血刃牌」「直到一方獲勝或所有輪結束」。
   - action（動作）：要做的事或結果，例如「移除所有幽魂牌」「翻開所有牌」。
   - purpose（目的說明）：解釋為什麼這樣做，不影響怎麼玩，例如「讓人無法判斷誰打出哪張牌」。"""

_TRACK = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["complete", "incomplete", "missing"]},
        "beat_keys": {"type": "array", "items": {"type": "string"}},
        "missing": {"type": ["string", "null"]},
    },
    "required": ["status", "beat_keys", "missing"],
    "additionalProperties": False,
}

SCHEMA = JsonSchema(
    name="rules_video_coverage",
    schema={
        "type": "object",
        "properties": {
            "rules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_id": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": ["condition", "action", "purpose"],
                        },
                        "source": {"type": "string"},
                        "narration": _TRACK,
                        "subtitle": _TRACK,
                    },
                    "required": ["rule_id", "category", "source", "narration", "subtitle"],
                    "additionalProperties": False,
                },
            },
            "problems": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "beat_key": {"type": "string"},
                        "track": {"type": "string", "enum": ["narration", "subtitle"]},
                        "kind": {"type": "string", "enum": ["contradiction", "not_in_rulebook"]},
                        "text": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["beat_key", "track", "kind", "text", "reason"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["rules", "problems"],
        "additionalProperties": False,
    },
)


@dataclass(frozen=True)
class TrackCheck:
    status: str  # complete | incomplete | missing
    beat_keys: list[str]
    missing: str | None


@dataclass(frozen=True)
class RuleCheck:
    rule_id: str
    source: str
    narration: TrackCheck
    subtitle: TrackCheck
    unmatched_beats: list[str] = field(default_factory=list)
    category: str = "condition"  # condition | action | purpose

    @property
    def is_hint(self) -> bool:
        """目的說明：另列為提示，不算漏講（2026-11-21 永傑決定）。"""
        return self.category == "purpose"

    @property
    def narration_shorter(self) -> bool:
        """字幕完整、旁白卻不完整或沒講到：旁白比字幕少條件（目的說明除外）。"""
        return (
            not self.is_hint
            and self.subtitle.status == "complete"
            and self.narration.status != "complete"
        )

    @property
    def has_issue(self) -> bool:
        if self.is_hint:
            return bool(self.unmatched_beats)
        return (
            self.narration.status != "complete"
            or self.subtitle.status != "complete"
            or bool(self.unmatched_beats)
        )


@dataclass(frozen=True)
class Problem:
    beat_key: str
    track: str
    kind: str
    text: str
    reason: str
    unmatched: bool = False


@dataclass
class CoverageReport:
    rules: list[RuleCheck]
    problems: list[Problem]

    @property
    def has_issues(self) -> bool:
        return bool(self.problems) or any(r.has_issue for r in self.rules)

    def to_json(self) -> str:
        data = {
            "rules": [asdict(r) | {"narration_shorter": r.narration_shorter} for r in self.rules],
            "problems": [asdict(p) for p in self.problems],
        }
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    def markdown(self) -> str:
        return _markdown(self)


def build_input(video: Video, pages: list[RulebookPage]) -> str:
    """只放本章原文、編號的旁白與字幕；不放參考頁與草稿的其他內容。"""
    lines: list[str] = []
    for page in pages:
        lines += [f"=== 本章規則書原文：第 {page.page} 頁（{page.lang}）===", page.text, ""]
    beats = [beat for segment in video.segments for beat in segment.beats]
    lines.append("=== 旁白（句子編號：內容）===")
    lines += [f"{beat.beat_key}：{beat.narration}" for beat in beats]
    lines += ["", "=== 字幕（句子編號：內容）==="]
    lines += [f"{beat.beat_key}：{beat.subtitle}" for beat in beats]
    return "\n".join(lines)


def check_coverage(llm: LLMProvider, video: Video, pages: list[RulebookPage]) -> CoverageReport:
    raw = llm.generate_json(
        instructions=INSTRUCTIONS, input=build_input(video, pages), schema=SCHEMA
    )
    known = {beat.beat_key for segment in video.segments for beat in segment.beats}
    return _to_report(raw, known)


def _track(raw: dict[str, Any]) -> TrackCheck:
    return TrackCheck(
        status=raw["status"], beat_keys=list(raw.get("beat_keys", [])), missing=raw.get("missing")
    )


def _to_report(raw: dict[str, Any], known: set[str]) -> CoverageReport:
    rules = []
    for entry in raw["rules"]:
        narration, subtitle = _track(entry["narration"]), _track(entry["subtitle"])
        unmatched = sorted({k for k in narration.beat_keys + subtitle.beat_keys if k not in known})
        rules.append(
            RuleCheck(
                entry["rule_id"],
                entry["source"],
                narration,
                subtitle,
                unmatched,
                entry.get("category", "condition"),
            )
        )
    problems = [
        Problem(
            beat_key=p["beat_key"],
            track=p["track"],
            kind=p["kind"],
            text=p["text"],
            reason=p["reason"],
            unmatched=p["beat_key"] not in known,
        )
        for p in raw["problems"]
    ]
    return CoverageReport(rules, problems)


def _cell(text: str | None) -> str:
    return "—" if not text else text.replace("|", "\\|").replace("\n", " ")


def _track_text(track: TrackCheck) -> str:
    text = STATUS_LABELS.get(track.status, track.status)
    if track.missing:
        text += f"（缺：{track.missing}）"
    if track.beat_keys:
        text += f"〔{'、'.join(track.beat_keys)}〕"
    return text


def _markdown(report: CoverageReport) -> str:
    lines = [
        "## 規則陳述檢查（AI 檢查，僅供參考）",
        "",
        "由 LLM 把本章原文的每一條規則分別與旁白、字幕對照；可能漏報或誤報，判斷以人為準。",
        "",
    ]
    hints = [rule for rule in report.rules if rule.is_hint]
    if not report.has_issues:
        return "\n".join([*lines, "沒有發現問題。", "", *_hint_lines(hints)])

    lines += ["| 規則 | 分類 | 原文 | 旁白 | 字幕 | 標記 |", "|---|---|---|---|---|---|"]
    for rule in report.rules:
        if rule.is_hint:
            continue
        marks = []
        if rule.narration_shorter:
            marks.append("**旁白比字幕少條件**")
        if rule.unmatched_beats:
            marks.append(f"無法對應的句子：{'、'.join(rule.unmatched_beats)}")
        lines.append(
            f"| {rule.rule_id} | {CATEGORY_LABELS.get(rule.category, rule.category)} "
            f"| {_cell(rule.source)} | {_cell(_track_text(rule.narration))} "
            f"| {_cell(_track_text(rule.subtitle))} | {'；'.join(marks) or ''} |"
        )
    if report.problems:
        lines += [
            "",
            "### 說反或規則書沒有的規則",
            "",
            "| 句子 | 旁白／字幕 | 類型 | 內容 | 原因 |",
        ]
        lines.append("|---|---|---|---|---|")
        for p in report.problems:
            key = p.beat_key + ("（無法對應）" if p.unmatched else "")
            lines.append(
                f"| {key} | {TRACK_LABELS.get(p.track, p.track)} | "
                f"{KIND_LABELS.get(p.kind, p.kind)} | {_cell(p.text)} | {_cell(p.reason)} |"
            )
    lines += ["", *_hint_lines(hints)]
    return "\n".join(lines) + "\n"


def _hint_lines(hints: list[RuleCheck]) -> list[str]:
    """目的說明另列為提示：不算漏講，但不隱藏。"""
    if not hints:
        return []
    lines = [
        "### 提示（目的說明，不算漏講）",
        "",
        "原文中解釋「為什麼這樣做」的句子。不影響怎麼玩，所以不算漏講；列出來供判斷要不要講。",
        "",
        "| 規則 | 原文 | 旁白 | 字幕 |",
        "|---|---|---|---|",
    ]
    for rule in hints:
        lines.append(
            f"| {rule.rule_id} | {_cell(rule.source)} | {_cell(_track_text(rule.narration))} "
            f"| {_cell(_track_text(rule.subtitle))} |"
        )
    return [*lines, ""]


def markdown_from_json(text: str) -> str:
    """從 coverage.json 重建報告段落（compare 用）。"""
    raw = json.loads(text)
    rules = [
        RuleCheck(
            r["rule_id"],
            r["source"],
            TrackCheck(**r["narration"]),
            TrackCheck(**r["subtitle"]),
            r.get("unmatched_beats", []),
            r.get("category", "condition"),
        )
        for r in raw["rules"]
    ]
    problems = [Problem(**p) for p in raw["problems"]]
    return CoverageReport(rules, problems).markdown()
