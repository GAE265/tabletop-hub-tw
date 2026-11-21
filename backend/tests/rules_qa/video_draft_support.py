"""草稿工作的測試共用資料（add-rules-video-mobile MR 5，design.md D11）。

規則書頁面與對照表都用虛構的短文字（video_script_support 的假遊戲），不需要金鑰。
"""

import json
import uuid
from typing import Any

from sqlalchemy import Engine, text

from app.integrations.llm.fake import FakeLLMProvider
from tests.rules_qa.video_script_support import FAKE_PAGE, FAKE_REFERENCE_PAGE, TERMS

# 店員編輯後的本章頁：比原文多一句標記，用來確認 AI 與涵蓋檢查讀的是編輯後的文字
EDITED_MARK = "（店員補上：同時翻開所有牌。）"
EDITED_PAGE = FAKE_PAGE + "\n" + EDITED_MARK
ORIGINAL_ONLY = "Case 2: any Blade card. Remove every Blue card."
EDITED_WITHOUT_CASE_2 = EDITED_PAGE.replace(ORIGINAL_ONLY, "")


def add_manual(add_pages, game: int) -> None:
    """games_manual：第 3 頁（參考頁）、第 5 頁（本章頁）的原文。"""
    add_pages(game, [(3, FAKE_REFERENCE_PAGE), (5, FAKE_PAGE)])


def set_pages(
    engine: Engine,
    project: uuid.UUID,
    *,
    chapter_text: str = EDITED_WITHOUT_CASE_2,
    version: int = 1,
) -> None:
    """直接寫入頁面文字（MR 4 的欄位）：本章第 5 頁、參考第 3 頁。"""
    page_texts = {
        "5": {"text": chapter_text, "original_hash": "x"},
        "3": {"text": FAKE_REFERENCE_PAGE, "original_hash": "x"},
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE rules_qa_video_projects SET chapter_pages = '{5}', "
                "reference_pages = '{3}', page_texts = CAST(:t AS jsonb), pages_version = :v "
                "WHERE id = :p"
            ),
            {"t": json.dumps(page_texts, ensure_ascii=False), "v": version, "p": project},
        )


def upload_terms(engine: Engine, game: int, terms: list[dict[str, Any]] | None = None) -> None:
    """用語對照表（MR 3 的表）；terms 為 None 時用測試用的對照表。"""
    from tests.conftest import TEST_ADMIN

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO rules_qa_video_terms (game_id, terms, updated_by) "
                "VALUES (:g, CAST(:t AS jsonb), :u)"
            ),
            {
                "g": game,
                "t": json.dumps(TERMS if terms is None else terms, ensure_ascii=False),
                "u": TEST_ADMIN.id,
            },
        )


def project_row(engine: Engine, project: uuid.UUID):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT video, video_version, coverage, coverage_version, draft_pages_version, "
                "pages_version FROM rules_qa_video_projects WHERE id = :p"
            ),
            {"p": project},
        ).one()


class FakeHookLLM(FakeLLMProvider):
    """手寫的 fake：第 hook_at 次呼叫 generate_json 之前先執行 hook（模擬工作進行中專案被改）。"""

    def __init__(self, json_outputs: list[Any], hook_at: int, hook) -> None:
        super().__init__(json_outputs=json_outputs)
        self._hook_at = hook_at
        self._hook = hook

    def generate_json(self, *, instructions: str, input: str, schema) -> dict:
        if len(self.calls) + 1 == self._hook_at:
            self._hook()
        return super().generate_json(instructions=instructions, input=input, schema=schema)
