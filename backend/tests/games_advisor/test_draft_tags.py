"""draft-tags：上標籤（spec §8.7）。

service 的測試：假的 repository、FakeLLMProvider，不連資料庫。標籤草稿與原始檔寫在 tmp_path。
模型輸出被拒絕時「重試 1 次、仍失敗就跳過」的共用規則（spec §7.2 規則 6）也在這裡測。
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.domains.games_advisor import service
from app.integrations.llm.errors import LLMOutputRejected, LLMUnavailable
from app.integrations.llm.fake import FakeLLMProvider
from tests.games_advisor.fakes import FakeGameRepository, FakeTagRepository
from tests.games_advisor.support import exported, make_game, make_review, make_tag, reviews_data

CODES = ["laughter", "luck", "scheming", "tense"]
MAYBE_WRONG = "詞彙表可能有問題"


def url(number: int, index: int = 1) -> str:
    return make_review(number, index)["source_url"]


def tag(code: str, confidence: float, *source_urls: str) -> dict[str, Any]:
    return {"code": code, "confidence": confidence, "source_urls": list(source_urls)}


def good(number: int) -> dict[str, Any]:
    """LLM 替第 number 款給的合格輸出：0.8 分的引用 2 篇，0.5 分的引用 1 篇。"""
    return {
        "tags": [
            tag("laughter", 0.8, url(number, 1), url(number, 2)),
            tag("scheming", 0.5, url(number, 1)),
        ]
    }


def entry(number: int, output: dict[str, Any]) -> dict[str, Any]:
    """標籤草稿裡第 number 款的那一項。"""
    game = make_game(number)
    return {"bgg_id": game["bgg_id"], "name": game["name"], "tags": output["tags"]}


def vocabulary(*codes: str) -> FakeTagRepository:
    store = FakeTagRepository()
    for code in codes:
        definition = make_tag(code)
        store.tags[code] = {"name": definition["name"], "definition": definition["definition"]}
    return store


def two_reviews_each(*numbers: int) -> dict[str, Any]:
    return reviews_data([make_review(number, index) for number in numbers for index in (1, 2)])


def draft(
    tmp_path: Path,
    llm: FakeLLMProvider,
    *,
    numbers: tuple[int, ...] = (1, 2),
    data: dict[str, Any] | None = None,
    tags: FakeTagRepository | None = None,
    only_bgg_ids: list[int] | None = None,
) -> Any:
    return service.draft_tags(
        FakeGameRepository([exported(number, game_id=number) for number in numbers]),
        tags if tags is not None else vocabulary(*CODES),
        data or two_reviews_each(*numbers),
        llm=llm,
        out_path=tmp_path / "tags-draft.json",
        only_bgg_ids=only_bgg_ids,
    )


def read_draft(tmp_path: Path, name: str = "tags-draft.json") -> dict[str, Any]:
    return json.loads((tmp_path / name).read_text(encoding="utf-8"))


def printed(result: Any) -> str:
    return "\n".join(result.lines)


# --- 正常情況 ---


def test_writes_draft_and_original_with_codes_from_the_vocabulary(tmp_path: Path) -> None:
    tags = vocabulary(*CODES)
    llm = FakeLLMProvider(json_outputs=[good(1), good(2)])

    result = draft(tmp_path, llm, tags=tags)

    # 每款 1 次，一次讀完該款全部心得
    assert [call.method for call in llm.calls] == ["generate_json", "generate_json"]
    for call, number in zip(llm.calls, (1, 2), strict=True):
        for index in (1, 2):
            assert make_review(number, index)["text"] in call.kwargs["input"]
        # 代碼只能選詞彙表裡的：schema 的 enum 等於資料表的 4 個代碼
        code_schema = call.kwargs["schema"].schema["properties"]["tags"]["items"]["properties"][
            "code"
        ]
        assert sorted(code_schema["enum"]) == CODES
    assert read_draft(tmp_path) == {"games": [entry(1, good(1)), entry(2, good(2))]}
    # 原始檔和草稿內容相同
    assert read_draft(tmp_path, "tags-draft.original.json") == read_draft(tmp_path)
    # 上標籤只寫檔案，不寫每款桌遊的標籤
    assert tags.game_tags == {}
    assert result.skipped == []
    assert result.exit_code == 0


def test_bgg_id_option_limits_the_draft_to_that_game(tmp_path: Path) -> None:
    llm = FakeLLMProvider(json_outputs=[good(2)])

    draft(tmp_path, llm, only_bgg_ids=[900002])

    assert len(llm.calls) == 1
    assert read_draft(tmp_path) == {"games": [entry(2, good(2))]}


def test_game_without_reviews_is_in_the_draft_with_no_tags(tmp_path: Path) -> None:
    # 第 2 款沒有心得：腳本只有 1 次輸出，多呼叫一次 fake 就會讓測試失敗
    llm = FakeLLMProvider(json_outputs=[good(1)])

    draft(tmp_path, llm, data=two_reviews_each(1))

    assert len(llm.calls) == 1
    assert read_draft(tmp_path) == {"games": [entry(1, good(1)), entry(2, {"tags": []})]}


def test_game_with_empty_output_is_in_the_draft_with_a_reminder(tmp_path: Path) -> None:
    llm = FakeLLMProvider(json_outputs=[good(1), {"tags": []}])

    result = draft(tmp_path, llm)

    assert read_draft(tmp_path) == {"games": [entry(1, good(1)), entry(2, {"tags": []})]}
    reminder = [line for line in result.lines if make_game(2)["name"] in line]
    assert reminder and "沒有任何標籤" in reminder[0]
    assert result.exit_code == 0


# --- 自動檢查不通過或模型出錯：重試 1 次，仍失敗就跳過那一款 ---


def test_retries_once_when_the_output_has_a_code_outside_the_vocabulary(tmp_path: Path) -> None:
    bad = {"tags": [tag("party", 0.5, url(1, 1))]}
    llm = FakeLLMProvider(json_outputs=[bad, good(1), good(2)])

    result = draft(tmp_path, llm)

    assert len(llm.calls) == 3
    assert read_draft(tmp_path) == {"games": [entry(1, good(1)), entry(2, good(2))]}
    assert result.exit_code == 0


def test_retries_once_when_the_output_is_rejected(tmp_path: Path) -> None:
    llm = FakeLLMProvider(json_outputs=[LLMOutputRejected("輸出被截斷"), good(1), good(2)])

    result = draft(tmp_path, llm)

    assert len(llm.calls) == 3
    assert read_draft(tmp_path) == {"games": [entry(1, good(1)), entry(2, good(2))]}
    assert result.exit_code == 0


def test_skips_the_game_when_the_output_is_rejected_twice(tmp_path: Path) -> None:
    llm = FakeLLMProvider(
        json_outputs=[LLMOutputRejected("輸出被截斷"), LLMOutputRejected("輸出被截斷"), good(2)]
    )

    result = draft(tmp_path, llm)

    assert read_draft(tmp_path) == {"games": [entry(2, good(2))]}
    assert [skipped.bgg_id for skipped in result.skipped] == [900001]
    assert "輸出被截斷" in result.skipped[0].reason
    assert result.exit_code == 2


@pytest.mark.parametrize(
    "bad_tags",
    [
        pytest.param([tag("laughter", 1.2, url(1, 1), url(1, 2))], id="分數 1.2"),
        pytest.param(
            [tag("scheming", 0.5, url(1, 1)), tag("scheming", 0.3, url(1, 2))], id="同一款重複標籤"
        ),
        pytest.param([tag("scheming", 0.5)], id="標籤沒有引用心得"),
        pytest.param([tag("scheming", 0.5, url(2, 1))], id="引用別款的心得網址"),
        pytest.param([tag("laughter", 0.8, url(1, 1))], id="0.8 只引用 1 篇"),
    ],
)
def test_skips_the_game_when_both_outputs_fail_the_checks(
    tmp_path: Path, bad_tags: list[dict[str, Any]]
) -> None:
    llm = FakeLLMProvider(json_outputs=[{"tags": bad_tags}, {"tags": bad_tags}, good(2)])

    result = draft(tmp_path, llm)

    # 第 1 款兩次都不合格：跳過、不在草稿；第 2 款照寫
    assert len(llm.calls) == 3
    assert read_draft(tmp_path) == {"games": [entry(2, good(2))]}
    assert [skipped.bgg_id for skipped in result.skipped] == [900001]
    assert result.skipped[0].reason
    assert result.exit_code == 2


def test_skips_the_game_when_the_model_is_unavailable(tmp_path: Path) -> None:
    llm = FakeLLMProvider(json_outputs=[LLMUnavailable("模型逾時"), good(2)])

    result = draft(tmp_path, llm)

    # 連不上不重試（SDK 已經重試過）
    assert len(llm.calls) == 2
    assert read_draft(tmp_path) == {"games": [entry(2, good(2))]}
    assert [skipped.bgg_id for skipped in result.skipped] == [900001]
    assert result.exit_code == 2


# --- 提醒，不算失敗 ---


def usage_outputs() -> list[dict[str, Any]]:
    """5 款：laughter 有 4 款（80%），scheming 有 3 款（60%），luck、tense 沒有任何一款。"""
    return [
        {
            "tags": [
                *([tag("laughter", 0.5, url(number, 1))] if number <= 4 else []),
                *([tag("scheming", 0.5, url(number, 1))] if number <= 3 else []),
            ]
        }
        for number in range(1, 6)
    ]


def usage_line(result: Any, code: str) -> str:
    lines = [line for line in result.lines if code in line]
    assert len(lines) == 1, result.lines
    return lines[0]


def test_warns_about_a_tag_that_no_game_uses(tmp_path: Path) -> None:
    result = draft(tmp_path, FakeLLMProvider(json_outputs=usage_outputs()), numbers=(1, 2, 3, 4, 5))

    assert MAYBE_WRONG in usage_line(result, "luck")
    assert MAYBE_WRONG in usage_line(result, "tense")
    assert result.exit_code == 0


def test_warns_about_a_tag_that_80_percent_of_the_games_use(tmp_path: Path) -> None:
    result = draft(tmp_path, FakeLLMProvider(json_outputs=usage_outputs()), numbers=(1, 2, 3, 4, 5))

    # 每個標籤被幾款使用都印出來；4 款（80%）要提醒，3 款（60%）不用
    assert "4 款" in usage_line(result, "laughter")
    assert MAYBE_WRONG in usage_line(result, "laughter")
    assert "3 款" in usage_line(result, "scheming")
    assert MAYBE_WRONG not in usage_line(result, "scheming")


# --- 拒絕執行：不呼叫模型，什麼都不寫 ---


def test_refuses_when_the_draft_already_exists(tmp_path: Path) -> None:
    (tmp_path / "tags-draft.json").write_text("立倫刪過標籤的草稿", encoding="utf-8")
    llm = FakeLLMProvider(json_outputs=[])

    with pytest.raises(service.Refused):
        draft(tmp_path, llm)

    assert llm.calls == []
    assert (tmp_path / "tags-draft.json").read_text(encoding="utf-8") == "立倫刪過標籤的草稿"
    assert not (tmp_path / "tags-draft.original.json").exists()


def test_refuses_when_the_original_already_exists(tmp_path: Path) -> None:
    (tmp_path / "tags-draft.original.json").write_text("上一次的原始檔", encoding="utf-8")
    llm = FakeLLMProvider(json_outputs=[])

    with pytest.raises(service.Refused):
        draft(tmp_path, llm)

    assert llm.calls == []
    assert (tmp_path / "tags-draft.original.json").read_text(encoding="utf-8") == "上一次的原始檔"
    assert not (tmp_path / "tags-draft.json").exists()


def test_refuses_when_the_vocabulary_is_empty(tmp_path: Path) -> None:
    llm = FakeLLMProvider(json_outputs=[])

    with pytest.raises(service.Refused) as refused:
        draft(tmp_path, llm, tags=vocabulary())

    # 提示先同步詞彙表
    assert "sync-vocabulary" in str(refused.value)
    assert llm.calls == []
    assert not (tmp_path / "tags-draft.json").exists()
