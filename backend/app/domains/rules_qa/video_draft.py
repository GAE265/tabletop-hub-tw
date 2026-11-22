"""草稿工作的處理函式（kind = draft；add-rules-video-mobile design.md D11）。

1. 讀專案：店員編輯後的頁面文字（不讀 games_manual）、用語對照表；記下 video_version。
2. generate_script：照 1c 的規則（自動清理、檢查、改寫一次）。
3. 涵蓋檢查：只用編輯後的本章頁文字；失敗或回空清單時，草稿照樣存，coverage 記 not_done。
4. 沿用舊草稿同一個 asset_key 的照片、方向、區域座標（MR 7；涵蓋檢查不需要照片，所以在檢查之後）。
5. 一個交易寫入草稿；條件是 video_version 沒變，變了就失敗、不覆寫。
任何一步失敗，原本的草稿都不變。LLM 的逾時用 LLM_TIMEOUT_SECONDS（每次呼叫）加 SDK 的重試。

整個遊戲一支影片（沒有章節的專案，2026-11-22 永傑決定）：第 1 步之後先分類三格
（video_scope：開局、走完一輪、獲勝方式），第 2 步只用三格的原文片段產生三個 chapter，
第 3 步對每一格分別做涵蓋檢查；分類結果（含排除清單）一起寫入。
店員看到的錯誤不含段代號等內部代號；細節放 error_detail（JobFailed.detail）。
"""

import dataclasses
import hashlib
import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.domains.rules_qa.repository import (
    RulesQaRepository,
    VideoDraftRepository,
    VideoTermsRepository,
)
from app.domains.rules_qa.video_assets import carry_over_assets
from app.domains.rules_qa.video_coverage import check_coverage
from app.domains.rules_qa.video_jobs import JobContext, JobFailed
from app.domains.rules_qa.video_scope import (
    ScopeEmpty,
    ScopeIncomplete,
    ScopeResult,
    classify_scope,
    slot_pages,
)
from app.domains.rules_qa.video_script import (
    CleanupRecord,
    RulebookPage,
    ScriptRejected,
    ScriptRequest,
    Term,
    TermIn,
    generate_script,
    generate_whole_game,
)
from app.integrations.llm import LLMProvider
from app.integrations.llm.errors import LLMError, LLMUnavailable
from app.integrations.video import Video, VideoDataError, parse_video

PAGE_LANG = "zh"  # games_manual 沒有語言欄位（design.md D3）

DRAFT_LLM_UNAVAILABLE_MESSAGE = "AI 服務暫時無法使用（連線逾時或忙碌），請稍後再產生一次"
DRAFT_LLM_REJECTED_MESSAGE = "AI 沒有完成草稿，請再產生一次；若持續發生請通知管理員"
DRAFT_CONFLICT_MESSAGE = "產生草稿期間專案被修改，請重新產生"
DRAFT_PAGES_NOT_SET_MESSAGE = "還沒有選本章頁，請先選頁並確認文字"
DRAFT_SCRIPT_REJECTED_MESSAGE = "AI 產生的草稿沒有通過檢查，請再產生一次；若一直失敗，請通知管理員"
DRAFT_NO_RULEBOOK_MESSAGE = "這款遊戲的規則書還沒有匯入，請管理員先匯入"
COVERAGE_LLM_MESSAGE = "涵蓋檢查沒有完成：AI 服務暫時無法使用"
COVERAGE_FORMAT_MESSAGE = "涵蓋檢查沒有完成：AI 的回答格式不對"
COVERAGE_EMPTY_MESSAGE = "涵蓋檢查無效：LLM 沒有拆出任何規則"


def scope_incomplete_message(pages: list[int]) -> str:
    listed = "、".join(str(page) for page in pages)
    return (
        f"規則書第 {listed} 頁沒有分到開局、走完一輪、獲勝方式，也不在不講的清單裡，無法產生影片；"
        "請再產生一次，若一直發生請通知管理員"
    )


def scope_empty_message(slot_title: str) -> str:
    return f"規則書裡找不到「{slot_title}」的內容，無法產生影片；請管理員確認規則書是否完整匯入"


TERMS_MISSING_HINT = "這款遊戲還沒有用語對照表，草稿的用詞品質可能下降"
PAGES_STALE_HINT = "這份草稿依舊的頁面文字產生，建議重新產生"


def narration_text_hash(video: dict[str, Any]) -> str:
    """旁白與字幕的雜湊：涵蓋檢查只看這兩樣，所以只有它們變了才算過期。

    上傳照片、改區域會讓 video_version 加 1，但不影響涵蓋檢查（2026-11-21 永傑決定）。
    """
    texts = [
        [beat.get("narration", ""), beat.get("subtitle", "")]
        for segment in video.get("segments", [])
        for beat in segment.get("beats", [])
    ]
    return hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode("utf-8")).hexdigest()


def terms_status(stored: list[dict[str, Any]] | None) -> str:
    """used＝有對照表；empty＝上傳了空表（確認不使用）；missing＝從未上傳。"""
    if stored is None:
        return "missing"
    return "used" if stored else "empty"


class DraftJobHandler:
    """草稿工作；後端啟動時註冊在 app.state.rules_video_job_handlers["draft"]。"""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def __call__(self, ctx: JobContext) -> dict[str, Any]:
        ctx.report(0.05, "讀取規則書文字")
        with ctx.session_factory() as session:
            state = VideoDraftRepository(session).get_state(ctx.project_id)
            game_name = RulesQaRepository(session).game_name(state.game_id) if state else None
            stored_terms = VideoTermsRepository(session).get(state.game_id) if state else None
        whole_game = state is not None and state.chapter_number is None
        if state is None or not state.chapter_pages:
            raise JobFailed(
                DRAFT_NO_RULEBOOK_MESSAGE if whole_game else DRAFT_PAGES_NOT_SET_MESSAGE
            )

        chapter = _pages(state.chapter_pages, state.page_texts)
        terms_raw = None if stored_terms is None else stored_terms.terms
        scope: ScopeResult | None = None
        if whole_game:
            ctx.report(0.1, "AI 分類規則（開局、走完一輪、獲勝方式）")
            scope = self._classify(chapter)
        request = ScriptRequest(
            chapter_number=state.chapter_number or 1,
            chapter_title=state.chapter_title or "",
            pages=[p for p in chapter if p.page in scope.pages] if scope else chapter,
            reference_pages=[] if scope else _pages(state.reference_pages, state.page_texts),
            terms=_terms(terms_raw),
            game_key=f"game-{state.game_id}",
            title=f"{game_name or '規則'} 規則教學",
            scope=scope.slots if scope else None,
        )

        with tempfile.TemporaryDirectory(prefix="rules-video-draft-") as work:
            base_dir = Path(work)
            ctx.report(0.3 if scope else 0.15, "AI 產生草稿")
            cleanup: list[CleanupRecord] = []
            data = self._generate(request, base_dir, cleanup)
            ctx.report(0.7, "規則涵蓋檢查")
            coverage = (
                self._coverage_by_slot(data, base_dir, scope)
                if scope
                else self._coverage(data, base_dir, chapter)
            )
            coverage["text_hash"] = narration_text_hash(data)
        kept_photos = carry_over_assets(state.video, data)

        ctx.report(0.95, "儲存草稿")
        with ctx.session_factory() as session:
            repo = VideoDraftRepository(session)
            with repo.transaction():
                saved = repo.save_draft(
                    ctx.project_id,
                    expected_version=state.video_version,
                    video=data,
                    coverage=coverage,
                    pages_version=state.pages_version,
                    classification=scope.to_dict() if scope else None,
                )
        if not saved:
            raise JobFailed(DRAFT_CONFLICT_MESSAGE)

        assets = data.get("assets", [])
        result: dict[str, Any] = {
            "segments": len(data.get("segments", [])),
            "beats": sum(len(s.get("beats", [])) for s in data.get("segments", [])),
            "assets": len(assets),
            "pending_photos": sum(1 for a in assets if not a.get("file")),
            "kept_photos": kept_photos,
            "cleanup": [asdict(record) for record in cleanup],
            "coverage": coverage["status"],
            "terms": terms_status(terms_raw),
        }
        if scope is not None:
            result["scope"] = {
                **{
                    slot.key: sum(1 for s in data["segments"] if s["chapter_key"] == slot.key)
                    for slot in scope.slots
                },
                "excluded": len(scope.excluded),
            }
            result["dropped_quotes"] = len(scope.dropped)
        return result

    def _classify(self, pages: list[RulebookPage]) -> ScopeResult:
        try:
            return classify_scope(self._llm, pages)
        except LLMUnavailable as exc:
            raise JobFailed(DRAFT_LLM_UNAVAILABLE_MESSAGE, detail=str(exc)) from exc
        except LLMError as exc:
            raise JobFailed(DRAFT_LLM_REJECTED_MESSAGE, detail=str(exc)) from exc
        except ScopeIncomplete as exc:
            raise JobFailed(scope_incomplete_message(exc.pages), detail=exc.detail) from exc
        except ScopeEmpty as exc:
            raise JobFailed(scope_empty_message(exc.slot_title), detail=exc.detail) from exc

    def _generate(
        self, request: ScriptRequest, base_dir: Path, cleanup: list[CleanupRecord]
    ) -> dict[str, Any]:
        try:
            if request.scope is not None:
                # 整個遊戲：每格各一次呼叫（2026-11-22 永傑決定）
                return generate_whole_game(self._llm, request, base_dir, cleanup_log=cleanup)
            return generate_script(self._llm, request, base_dir, cleanup_log=cleanup)
        except LLMUnavailable as exc:
            raise JobFailed(DRAFT_LLM_UNAVAILABLE_MESSAGE, detail=str(exc)) from exc
        except LLMError as exc:
            raise JobFailed(DRAFT_LLM_REJECTED_MESSAGE, detail=str(exc)) from exc
        except ScriptRejected as exc:
            # 檢查沒過的每一條含段代號等內部代號：只放 error_detail（2026-11-22 永傑決定）
            raise JobFailed(DRAFT_SCRIPT_REJECTED_MESSAGE, detail="\n".join(exc.errors)) from exc

    def _coverage(
        self, data: dict[str, Any], base_dir: Path, chapter: list[RulebookPage]
    ) -> dict[str, Any]:
        """涵蓋檢查沒做成時只記原因，不讓草稿失敗。"""
        return self._check(parse_video(data, base_dir, draft=True), chapter)

    def _check(self, video: Video, pages: list[RulebookPage]) -> dict[str, Any]:
        try:
            report = check_coverage(self._llm, video, pages)
        except LLMError as exc:
            return {"status": "not_done", "reason": COVERAGE_LLM_MESSAGE, "detail": str(exc)}
        except (VideoDataError, KeyError, TypeError) as exc:
            return {"status": "not_done", "reason": COVERAGE_FORMAT_MESSAGE, "detail": repr(exc)}
        if not report.is_valid:
            return {"status": "not_done", "reason": COVERAGE_EMPTY_MESSAGE}
        return {"status": "done", "report": json.loads(report.to_json())}

    def _coverage_by_slot(
        self, data: dict[str, Any], base_dir: Path, scope: ScopeResult
    ) -> dict[str, Any]:
        """每一格只拿這一格的原文片段，比對這一格的段（排除的內容不檢查）。提示，不擋下。"""
        video = parse_video(data, base_dir, draft=True)
        slots = []
        for slot in scope.slots:
            part = dataclasses.replace(
                video, segments=tuple(s for s in video.segments if s.chapter_key == slot.key)
            )
            checked = self._check(part, slot_pages(slot, PAGE_LANG))
            slots.append({"key": slot.key, "title": slot.title, **checked})
        done = all(s["status"] == "done" for s in slots)
        return {"status": "done" if done else "not_done", "slots": slots}


def _pages(numbers: list[int], page_texts: dict[str, Any]) -> list[RulebookPage]:
    """店員編輯後的文字；整頁空白的不送（例如只用來對照、內容全刪的頁）。"""
    pages = []
    for number in numbers:
        text = (page_texts.get(str(number)) or {}).get("text", "")
        if text.strip():
            pages.append(RulebookPage(PAGE_LANG, number, text.strip()))
    return pages


def _terms(stored: list[dict[str, Any]] | None) -> list[Term]:
    return [TermIn(**entry).to_term() for entry in stored or []]
