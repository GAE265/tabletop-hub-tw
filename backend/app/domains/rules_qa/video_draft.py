"""草稿工作的處理函式（kind = draft；add-rules-video-mobile design.md D11）。

1. 讀專案：店員編輯後的頁面文字（不讀 games_manual）、用語對照表；記下 video_version。
2. generate_script：照 1c 的規則（自動清理、檢查、改寫一次）。
3. 涵蓋檢查：只用編輯後的本章頁文字；失敗或回空清單時，草稿照樣存，coverage 記 not_done。
4. 一個交易寫入草稿；條件是 video_version 沒變，變了就失敗、不覆寫。
任何一步失敗，原本的草稿都不變。LLM 的逾時用 LLM_TIMEOUT_SECONDS（每次呼叫）加 SDK 的重試。
"""

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
from app.domains.rules_qa.video_coverage import check_coverage
from app.domains.rules_qa.video_jobs import JobContext, JobFailed
from app.domains.rules_qa.video_script import (
    CleanupRecord,
    RulebookPage,
    ScriptRejected,
    ScriptRequest,
    Term,
    TermIn,
    generate_script,
)
from app.integrations.llm import LLMProvider
from app.integrations.llm.errors import LLMError, LLMUnavailable
from app.integrations.video import VideoDataError, parse_video

PAGE_LANG = "zh"  # games_manual 沒有語言欄位（design.md D3）

DRAFT_LLM_UNAVAILABLE_MESSAGE = "AI 服務暫時無法使用（連線逾時或忙碌），請稍後再產生一次"
DRAFT_LLM_REJECTED_MESSAGE = "AI 沒有完成草稿，請再產生一次；若持續發生請通知管理員"
DRAFT_CONFLICT_MESSAGE = "產生草稿期間專案被修改，請重新產生"
DRAFT_PAGES_NOT_SET_MESSAGE = "還沒有選本章頁，請先選頁並確認文字"
TERMS_MISSING_HINT = "這款遊戲還沒有用語對照表，草稿的用詞品質可能下降"
PAGES_STALE_HINT = "這份草稿依舊的頁面文字產生，建議重新產生"


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
        if state is None or not state.chapter_pages:
            raise JobFailed(DRAFT_PAGES_NOT_SET_MESSAGE)

        chapter = _pages(state.chapter_pages, state.page_texts)
        terms_raw = None if stored_terms is None else stored_terms.terms
        request = ScriptRequest(
            chapter_number=state.chapter_number,
            chapter_title=state.chapter_title,
            pages=chapter,
            reference_pages=_pages(state.reference_pages, state.page_texts),
            terms=_terms(terms_raw),
            game_key=f"game-{state.game_id}",
            title=f"{game_name or '規則'} 規則教學",
        )

        with tempfile.TemporaryDirectory(prefix="rules-video-draft-") as work:
            base_dir = Path(work)
            ctx.report(0.15, "AI 產生草稿")
            cleanup: list[CleanupRecord] = []
            data = self._generate(request, base_dir, cleanup)
            ctx.report(0.7, "規則涵蓋檢查")
            coverage = self._coverage(data, base_dir, chapter)

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
                )
        if not saved:
            raise JobFailed(DRAFT_CONFLICT_MESSAGE)

        assets = data.get("assets", [])
        return {
            "segments": len(data.get("segments", [])),
            "beats": sum(len(s.get("beats", [])) for s in data.get("segments", [])),
            "assets": len(assets),
            "pending_photos": sum(1 for a in assets if not a.get("file")),
            "cleanup": [asdict(record) for record in cleanup],
            "coverage": coverage["status"],
            "terms": terms_status(terms_raw),
        }

    def _generate(
        self, request: ScriptRequest, base_dir: Path, cleanup: list[CleanupRecord]
    ) -> dict[str, Any]:
        try:
            return generate_script(self._llm, request, base_dir, cleanup_log=cleanup)
        except LLMUnavailable as exc:
            raise JobFailed(DRAFT_LLM_UNAVAILABLE_MESSAGE) from exc
        except LLMError as exc:
            raise JobFailed(DRAFT_LLM_REJECTED_MESSAGE) from exc
        except ScriptRejected as exc:
            reasons = "；".join(exc.errors[:3])
            raise JobFailed(
                f"AI 產生的草稿沒有通過檢查：{reasons}。"
                "可以再產生一次；若一直失敗，請檢查規則書頁面的文字"
            ) from exc

    def _coverage(
        self, data: dict[str, Any], base_dir: Path, chapter: list[RulebookPage]
    ) -> dict[str, Any]:
        """涵蓋檢查沒做成時只記原因，不讓草稿失敗。"""
        try:
            report = check_coverage(self._llm, parse_video(data, base_dir, draft=True), chapter)
        except LLMError as exc:
            return {"status": "not_done", "reason": f"涵蓋檢查沒有完成：{exc}"}
        except (VideoDataError, KeyError, TypeError) as exc:
            return {"status": "not_done", "reason": f"涵蓋檢查的輸出格式不符：{exc!r}"}
        if not report.is_valid:
            return {"status": "not_done", "reason": "涵蓋檢查無效：LLM 沒有拆出任何規則"}
        return {"status": "done", "report": json.loads(report.to_json())}


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
