"""手機上用一句話修改草稿（add-rules-video-mobile MR 11）。

修改的邏輯沿用命令列版（video_revision）：店員的修改要求 → AI 回傳受影響的段的完整新內容 →
檢查不通過改寫一次。手機版分兩步：

1. 修改的工作（kind=revise）只算出提案，**不寫入草稿**。結果存在工作的 result：
   可以做（proposal）、版型做不到（unsupported，附替代做法）、不確定改哪一段（ambiguous）。
2. 店員看過提案按「套用」，才由 API 取代那幾段（service.VideoRevisionService.apply）。

套用後不做規則涵蓋檢查（2026-11-26 永傑決定，之後再加）。
"""

import tempfile
from pathlib import Path
from typing import Any

from app.domains.rules_qa import video_revision as revision
from app.domains.rules_qa.repository import (
    VideoDraftRepository,
    VideoJobRepository,
    VideoTermsRepository,
)
from app.domains.rules_qa.video_draft import _terms
from app.domains.rules_qa.video_jobs import JobContext, JobFailed
from app.integrations.llm import LLMProvider
from app.integrations.llm.errors import LLMError, LLMUnavailable
from app.integrations.llm.usage import collect_usage

REVISE_NO_DRAFT_MESSAGE = "這個專案還沒有草稿，請先產生草稿"
REVISE_NO_REQUEST_MESSAGE = "沒有收到修改要求，請重新送出"
REVISE_LLM_UNAVAILABLE_MESSAGE = "AI 服務暫時無法使用（連線逾時或忙碌），請稍後再送出一次"
REVISE_LLM_FAILED_MESSAGE = "AI 沒有完成修改，請再送出一次；若持續發生請通知管理員"
REVISE_REJECTED_MESSAGE = "AI 改了兩次都沒有通過檢查，請換個說法，或指定要改哪一段再試一次"
REVISE_SEGMENT_MESSAGE = "草稿裡找不到指定的段，請重新整理後再送出"
COVERAGE_NOT_DONE_MESSAGE = "這次沒有做規則涵蓋檢查"


class RevisionJobHandler:
    """修改的工作；後端啟動時註冊在 app.state.rules_video_job_handlers["revise"]。"""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def __call__(self, ctx: JobContext) -> dict[str, Any]:
        # LLM 的實際 token 用量記在結果（和草稿工作一樣，算費用用）
        with collect_usage() as usage:
            result = self._run(ctx)
        result["usage"] = usage.summary()
        return result

    def _run(self, ctx: JobContext) -> dict[str, Any]:
        ctx.report(0.05, "讀取草稿")
        with ctx.session_factory() as session:
            state = VideoDraftRepository(session).get_state(ctx.project_id)
            job = VideoJobRepository(session).get(ctx.job_id)
            stored = VideoTermsRepository(session).get(state.game_id) if state else None
        if state is None or state.video is None:
            raise JobFailed(REVISE_NO_DRAFT_MESSAGE)
        params = (job.input if job else None) or {}
        request = (params.get("request") or "").strip()
        if not request:
            raise JobFailed(REVISE_NO_REQUEST_MESSAGE)
        segment_key = params.get("segment_key")
        terms = _terms(None if stored is None else stored.terms)

        ctx.report(0.15, "AI 修改中")
        with tempfile.TemporaryDirectory(prefix="rules-video-revise-") as work:
            folder = Path(work)
            revision.write_json(folder / "video.json", state.video)
            try:
                outcome = revision.propose(
                    self._llm, folder, request, terms=terms, only_segment=segment_key
                )
            except LLMUnavailable as exc:
                raise JobFailed(REVISE_LLM_UNAVAILABLE_MESSAGE, detail=str(exc)) from exc
            except LLMError as exc:
                raise JobFailed(REVISE_LLM_FAILED_MESSAGE, detail=str(exc)) from exc
            except revision.RevisionRejected as exc:
                # 檢查沒過的每一條含段代號等內部代號：只放 error_detail
                raise JobFailed(REVISE_REJECTED_MESSAGE, detail="\n".join(exc.errors)) from exc
            except revision.RevisionError as exc:
                raise JobFailed(REVISE_SEGMENT_MESSAGE, detail=str(exc)) from exc
            ctx.report(0.9, "整理提案")
            return build_result(
                outcome, folder, state.video, request, segment_key, state.video_version
            )


def build_result(
    outcome: revision.Proposal | revision.Unsupported | revision.Ambiguous,
    folder: Path,
    data: dict[str, Any],
    request: str,
    segment_key: str | None,
    base_version: int,
) -> dict[str, Any]:
    """工作結果：套用時要用的新段內容、改之前的段（給店員對照），以及當時的草稿版本。"""
    result: dict[str, Any] = {
        "request": request,
        "segment_key": segment_key,
        "base_video_version": base_version,
        "reason": None,
        "segments": [],
        "alternatives": [],
        "candidates": [],
        "unsupported_actions": [],
        "applied": None,
    }
    if isinstance(outcome, revision.Proposal):
        result["outcome"] = "proposal"
        result["segments"] = [_entry_json(e, data) for e in outcome.entries]
    elif isinstance(outcome, revision.Unsupported):
        # 做不到的需求留在工作結果（修改要求、原因、不支援的動作），作為第 3 階段的輸入
        result["outcome"] = "unsupported"
        result["reason"] = outcome.reason
        result["unsupported_actions"] = outcome.unsupported_actions
        for alt in outcome.alternatives:
            revision.compute_changes(folder, data, alt.entries)
            result["alternatives"].append(
                {
                    "title": alt.title,
                    "description": alt.description,
                    "segments": [_entry_json(e, data) for e in alt.entries],
                }
            )
    else:
        result["outcome"] = "ambiguous"
        result["reason"] = outcome.reason
        result["candidates"] = [{"segment_key": k, "reason": r} for k, r in outcome.candidates]
    return result


def _entry_json(entry: revision.Entry, data: dict[str, Any]) -> dict[str, Any]:
    before = next(s for s in data["segments"] if s["segment_key"] == entry.segment_key)
    return {
        **entry.to_json(),
        "changed": entry.changed,
        "unrequested": entry.unrequested,
        "before": {k: v for k, v in before.items() if k not in revision.NOT_VISUAL},
    }


def stored_entries(raw: list[dict[str, Any]]) -> list[revision.Entry]:
    """從工作結果還原要套用的段（欄位差異沿用算提案時的結果）。"""
    entries = revision.entries_from_pending(raw)
    for entry, item in zip(entries, raw, strict=True):
        entry.changed = list(item.get("changed", []))
    return entries


def beat_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """旁白或字幕有變的句子（含新增、刪除的句子），給店員對照改之前與改之後。"""
    old, new = before.get("beats") or [], after.get("beats") or []
    keyed = all(b.get("beat_key") for b in [*old, *new])
    if keyed:
        old_by = {b["beat_key"]: b for b in old}
        new_by = {b["beat_key"]: b for b in new}
        keys = [*old_by, *(k for k in new_by if k not in old_by)]
        pairs = [(k, old_by.get(k), new_by.get(k)) for k in keys]
    else:
        count = max(len(old), len(new))
        pairs = [
            (str(i + 1), old[i] if i < len(old) else None, new[i] if i < len(new) else None)
            for i in range(count)
        ]
    changes = []
    for key, a, b in pairs:
        ta, tb = _text(a), _text(b)
        if ta != tb:
            changes.append({"beat_key": key, "before": ta, "after": tb})
    return changes


def _text(beat: dict[str, Any] | None) -> dict[str, str] | None:
    if beat is None:
        return None
    return {"narration": beat.get("narration") or "", "subtitle": beat.get("subtitle") or ""}


def segment_numbers(data: dict[str, Any]) -> dict[str, int]:
    """段代號 → 第幾段（從 1 開始，畫面上用「第 N 段」）。"""
    return {s["segment_key"]: i for i, s in enumerate(data.get("segments", []), start=1)}
