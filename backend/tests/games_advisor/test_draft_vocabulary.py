"""draft-vocabulary：歸納詞彙表草稿（spec §8.5）。

service 的測試：假的 repository、FakeLLMProvider，不連資料庫。草稿與歸納報告寫在 tmp_path。
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.domains.games_advisor import service
from app.integrations.llm.errors import LLMOutputRejected, LLMUnavailable
from app.integrations.llm.fake import FakeLLMProvider
from tests.games_advisor.fakes import FakeGameRepository
from tests.games_advisor.support import exported, make_game, make_review, reviews_data

# 立倫 2026-11-11 指定的 35 個優先候選詞（spec §8.5）
PRIORITY_CANDIDATES = (
    "派對、嘴砲、合作、搞笑、滑稽、出糗、幽默、放鬆、懸疑、推理、分析、決策、觀察、掌控、自由、"
    "分配、學習、專注、活用、動手、主觀、客觀、聯誼、交心、探索、融合、模擬、組合、拆開、破壞、"
    "競爭、刺激、緊張、靜止、平靜"
).split("、")

DISCARD_REASON = "和「運氣影響大」是同一個面向的反方向"


def url(number: int, index: int = 1) -> str:
    return make_review(number, index)["source_url"]


def candidate(term: str, source_url: str) -> dict[str, Any]:
    return {"term": term, "description": f"{term}的一句描述", "source_urls": [source_url]}


def candidates_of(number: int) -> dict[str, Any]:
    """LLM 替第 number 款擷取的候選詞。三款依序編成 c1–c2、c3–c4、c5–c7。"""
    terms = {
        1: ["笑聲不斷", "勾心鬥角"],
        2: ["歡樂", "運氣成分低"],
        3: ["互相猜忌", "笑到不行", "靠運氣"],
    }
    return {"candidates": [candidate(term, url(number)) for term in terms[number]]}


def merged() -> dict[str, Any]:
    """LLM 合併同義詞的輸出。標籤的順序刻意不照出現的款數排。"""
    return {
        "tags": [
            {
                "code": "luck",
                "name": "運氣影響大",
                "definition": "勝負常取決於運氣",
                "candidate_ids": ["c7"],
            },
            {
                "code": "scheming",
                "name": "勾心鬥角",
                "definition": "玩家之間互相猜忌、設局",
                "candidate_ids": ["c2", "c5"],
            },
            {
                "code": "laughter",
                "name": "歡樂爆笑",
                "definition": "玩的過程常有大笑、吵鬧的場面",
                "candidate_ids": ["c1", "c3", "c6"],
            },
        ],
        "discarded": [{"candidate_id": "c4", "reason": DISCARD_REASON}],
    }


def three_games() -> FakeGameRepository:
    return FakeGameRepository([exported(number, game_id=number) for number in (1, 2, 3)])


def reviews_for(*numbers: int) -> dict[str, Any]:
    return reviews_data([make_review(number, 1) for number in numbers])


def draft(tmp_path: Path, llm: FakeLLMProvider, data: dict[str, Any] | None = None) -> Any:
    return service.draft_vocabulary(
        three_games(),
        data or reviews_for(1, 2, 3),
        llm=llm,
        out_path=tmp_path / "draft.json",
        report_path=tmp_path / "report.md",
    )


def test_extracts_candidates_per_game_then_merges_once(tmp_path: Path) -> None:
    llm = FakeLLMProvider(
        json_outputs=[candidates_of(1), candidates_of(2), candidates_of(3), merged()]
    )

    result = draft(tmp_path, llm)

    # 每款 1 次擷取候選詞，再 1 次合併
    assert [call.method for call in llm.calls] == ["generate_json"] * 4
    for call, number in zip(llm.calls[:3], (1, 2, 3), strict=True):
        assert make_review(number, 1)["text"] in call.kwargs["input"]
    merge_input = llm.calls[3].kwargs["input"]
    for candidate_id, term in (("c1", "笑聲不斷"), ("c4", "運氣成分低"), ("c7", "靠運氣")):
        assert candidate_id in merge_input
        assert term in merge_input

    # 草稿只有代碼、名稱、定義，依出現的款數由多到少排（3、2、1 款）
    assert json.loads((tmp_path / "draft.json").read_text(encoding="utf-8")) == {
        "tags": [
            {"code": "laughter", "name": "歡樂爆笑", "definition": "玩的過程常有大笑、吵鬧的場面"},
            {"code": "scheming", "name": "勾心鬥角", "definition": "玩家之間互相猜忌、設局"},
            {"code": "luck", "name": "運氣影響大", "definition": "勝負常取決於運氣"},
        ]
    }

    # 歸納報告：合併的候選詞、出現在哪幾款、依據的網址、捨棄的候選詞與原因
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    for term in ("笑聲不斷", "歡樂", "笑到不行", "勾心鬥角", "互相猜忌", "靠運氣"):
        assert term in report
    for number in (1, 2, 3):
        assert make_game(number)["name"] in report
        assert url(number) in report
    assert "運氣成分低" in report
    assert DISCARD_REASON in report

    assert result.skipped == []
    assert result.exit_code == 0


def test_candidate_prompt_lists_the_priority_candidates(tmp_path: Path) -> None:
    llm = FakeLLMProvider(
        json_outputs=[candidates_of(1), candidates_of(2), candidates_of(3), merged()]
    )

    draft(tmp_path, llm)

    assert len(PRIORITY_CANDIDATES) == 35
    for call in llm.calls[:3]:
        for word in PRIORITY_CANDIDATES:
            assert word in call.kwargs["instructions"]


def test_refuses_when_the_draft_already_exists(tmp_path: Path) -> None:
    (tmp_path / "draft.json").write_text("立倫編輯過的草稿", encoding="utf-8")
    llm = FakeLLMProvider(json_outputs=[])

    with pytest.raises(service.Refused):
        draft(tmp_path, llm)

    assert llm.calls == []
    assert (tmp_path / "draft.json").read_text(encoding="utf-8") == "立倫編輯過的草稿"
    assert not (tmp_path / "report.md").exists()


def test_refuses_when_the_report_already_exists(tmp_path: Path) -> None:
    (tmp_path / "report.md").write_text("上一次的歸納報告", encoding="utf-8")
    llm = FakeLLMProvider(json_outputs=[])

    with pytest.raises(service.Refused):
        draft(tmp_path, llm)

    assert llm.calls == []
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == "上一次的歸納報告"
    assert not (tmp_path / "draft.json").exists()


def test_game_that_fails_extraction_is_skipped_and_the_rest_are_merged(tmp_path: Path) -> None:
    llm = FakeLLMProvider(
        json_outputs=[candidates_of(1), LLMUnavailable("模型逾時"), candidates_of(3), merged()]
    )

    result = draft(tmp_path, llm)

    assert len(llm.calls) == 4
    assert [skipped.bgg_id for skipped in result.skipped] == [900002]
    assert result.exit_code == 2
    assert (tmp_path / "draft.json").exists()
    # 被跳過的桌遊列在歸納報告裡
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert make_game(2)["name"] in report
    assert "模型逾時" in report


def test_merge_rejected_twice_writes_nothing(tmp_path: Path) -> None:
    llm = FakeLLMProvider(
        json_outputs=[
            candidates_of(1),
            candidates_of(2),
            candidates_of(3),
            LLMOutputRejected("輸出被截斷"),
            LLMOutputRejected("輸出被截斷"),
        ]
    )

    with pytest.raises(service.Refused):
        draft(tmp_path, llm)

    # 合併那一次重試了 1 次
    assert len(llm.calls) == 5
    assert not (tmp_path / "draft.json").exists()
    assert not (tmp_path / "report.md").exists()


def test_game_without_reviews_gets_no_llm_call(tmp_path: Path) -> None:
    # 第 3 款沒有心得：腳本只有 2 次擷取加 1 次合併，多呼叫一次 fake 就會讓測試失敗
    only_two = merged()
    only_two["tags"] = [
        {**tag, "candidate_ids": [cid for cid in tag["candidate_ids"] if cid in {"c1", "c2", "c3"}]}
        for tag in only_two["tags"]
    ]
    llm = FakeLLMProvider(json_outputs=[candidates_of(1), candidates_of(2), only_two])

    result = draft(tmp_path, llm, reviews_for(1, 2))

    assert len(llm.calls) == 3
    assert result.exit_code == 0
