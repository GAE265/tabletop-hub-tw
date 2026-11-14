"""評估題組的執行、計分與報告（spec §15.1、§15.3、§15.4，§15.5 的「執行」「計分」）。

對話用 FakeLLMProvider 的腳本，桌遊與向量用假的 repository，不連資料庫也不連 Azure。
這裡都不跑評審（等於加了 --no-judge），評審的測試在 test_eval_judge.py。
指令收到 Refused 就印出原因、結束碼 1，所以「結束碼 1」的情境在這裡檢查拋出 Refused。
"""

from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from app.integrations.llm import (
    FakeLLMProvider,
    FakeResponse,
    LLMConversationNotFound,
    LLMError,
    LLMOutputRejected,
    LLMUnavailable,
)
from tests.games_advisor.conversation_support import (
    DROPPED_REPLY,
    MODEL,
    REJECTED_REPLY,
    final,
    rec,
    responds,
    search,
)
from tests.games_advisor.eval_support import (
    bgg,
    case,
    cases_data,
    evaluate,
    make_eval_repo,
    refuse,
    turn,
    with_tokens,
)

# 推薦 1 款的一輪：查 4 人，推薦甲並引用 1 段心得片段
RECOMMEND = [search(players=4), final("推薦你這款", rec(1, "e1a"))]


# --- 停在不符合的輪次（spec §15.3、MR 說明的解讀 1） ---


def test_mismatch_stops_the_case(tmp_path: Path) -> None:
    data = cases_data(
        case(
            "stop-01",
            turn("我們 4 個人", action="recommend"),
            turn("想要歡樂一點", action="recommend", manual=["推薦的是歡樂的桌遊"]),
            turn("換一批", action="recommend"),
        )
    )

    # 第 1 輪預期推薦，模型卻追問
    run = evaluate(tmp_path / "report.md", data, [final("請問想玩多久？")])

    [case_run] = run.result.runs
    assert [result.status for result in case_run.turns] == ["mismatched", "not_run", "not_run"]
    # 只送出第 1 輪的玩家訊息
    assert [call["input"] for call in responds(run.llm)] == ["我們 4 個人"]
    # 未執行輪次的項目算沒通過，分母固定
    assert run.result.constraint == (0, 3)
    assert run.result.manual_items == 1
    assert "未執行" in run.report


@pytest.mark.parametrize(
    ("responses", "reason"),
    [
        pytest.param([LLMUnavailable("逾時")], "503", id="503"),
        pytest.param([LLMOutputRejected("內容過濾")], REJECTED_REPLY, id="固定文字 A"),
        pytest.param([search(players=4), final("推薦你", rec(99))], DROPPED_REPLY, id="固定文字 B"),
    ],
)
def test_unavailable_or_fixed_reply_stops_the_case(
    tmp_path: Path, responses: list[FakeResponse | Exception], reason: str
) -> None:
    # 第 1 輪預期追問：固定文字沒有卡片，但仍然算不符合
    data = cases_data(
        case("stop-02", turn("想找桌遊", action="follow_up"), turn("4 個人", action="recommend"))
    )

    run = evaluate(tmp_path / "report.md", data, responses)

    first, second = run.result.runs[0].turns
    assert (first.status, second.status) == ("mismatched", "not_run")
    assert reason in first.error
    assert reason in run.report
    # 拿到錯誤或固定文字的那一輪，項目全部算沒通過（MR 說明的解讀 4）
    assert run.result.constraint == (0, 2)


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        pytest.param(LLMError("金鑰錯誤"), "500", id="500"),
        pytest.param(LLMConversationNotFound("對話過期"), "404", id="404"),
    ],
)
def test_other_errors_stop_the_case(tmp_path: Path, error: Exception, reason: str) -> None:
    data = cases_data(
        case(
            "stop-03",
            turn("想找桌遊", action="follow_up"),
            turn("4 個人", action="recommend"),
            turn("換一批", action="recommend"),
        )
    )

    run = evaluate(tmp_path / "report.md", data, [final("請問幾個人？"), error])

    turns = run.result.runs[0].turns
    assert [result.status for result in turns] == ["matched", "mismatched", "not_run"]
    assert reason in turns[1].error
    assert reason in run.report


def test_turns_continue_the_same_conversation(tmp_path: Path) -> None:
    data = cases_data(
        case(
            "flow-01",
            turn("我們 4 個人", action="recommend"),
            turn("第一款適合小孩嗎？", action="follow_up"),
            turn("謝謝", action="follow_up"),
        )
    )
    one_run = [*RECOMMEND, final("適合 8 歲以上"), final("不客氣")]

    run = evaluate(tmp_path / "report.md", data, one_run * 2, repeat=2)

    messages = [call for call in responds(run.llm) if isinstance(call["input"], str)]
    assert [call["input"] for call in messages] == ["我們 4 個人", "第一款適合小孩嗎？", "謝謝"] * 2
    # 第 1 輪不帶 id，之後接上一輪回覆的 id（第 1 輪查了一次，回覆的是第 2 個 id）；
    # 第 2 次重跑重新開始
    assert [call["previous_response_id"] for call in messages] == [
        None,
        "fake_resp_2",
        "fake_resp_3",
        None,
        "fake_resp_6",
        "fake_resp_7",
    ]


# --- 計分與次數（spec §15.3） ---


def test_scores_by_category(tmp_path: Path) -> None:
    data = cases_data(
        case(
            "score-01",
            turn(
                "我們 4 個人，30 分鐘內，不要太難，想要歡樂一點，上次玩過丁",
                action="recommend",  # 條件
                tool_args={
                    "players": 4,  # 條件
                    "max_minutes": 30,  # 條件
                    "exclude_bgg_ids": [bgg(4)],  # 條件
                    "weight_max": 2.5,  # 偏好
                    "prefer_tags": ["laughter"],  # 偏好
                },
                relaxed_constraint=None,  # 條件
                expect_any=[bgg(1)],  # 偏好
                forbid=[bgg(4)],  # 條件
                manual=["推薦理由提到歡樂", "回覆沒有列出桌遊名單"],
            ),
        ),
        case(
            "score-02",
            turn(
                "我們 4 個人，不要太靠運氣的",
                action="recommend",  # 條件
                tool_args={"players": 4, "avoid_tags": ["luck"]},  # 條件、偏好
                expect_any=[bgg(2)],  # 偏好
                manual=["有說明避開運氣"],
            ),
            turn(
                "最小的 8 歲",
                action="recommend",  # 條件
                tool_args={"youngest_age": 8, "prefer_mechanics": ["Voting"]},  # 條件、偏好
                manual=["有考慮年齡", "推薦理由最多 2 句"],
            ),
        ),
    )
    responses = [
        search(
            players=4,
            max_minutes=30,
            weight_max=2.5,
            prefer_tags=["laughter"],
            exclude_game_ids=[4],
        ),
        final("推薦你這款", rec(1, "e1a")),
        # score-02 第 1 輪：漏了 avoid_tags、推薦的不是乙，不符合；第 2 輪未執行
        *RECOMMEND,
    ]

    run = evaluate(tmp_path / "report.md", data, responses)

    # 條件：score-01 6/6；score-02 第 1 輪 2/2、第 2 輪未執行 0/2
    assert run.result.constraint == (8, 10)
    # 偏好：score-01 3/3；score-02 第 1 輪 0/2、第 2 輪未執行 0/1
    assert run.result.preference == (3, 6)
    # 人工項目只算有幾項，由立倫在報告勾選後自己統計：2 + 1 + 2
    assert run.result.manual_items == 5


def test_demo_fails_when_any_run_fails(tmp_path: Path) -> None:
    data = cases_data(case("demo-01", turn("我們 4 個人", action="recommend"), demo=True))
    # 第 2 次只追問，沒有推薦
    responses = [*RECOMMEND, final("請問想玩多久？"), *RECOMMEND]

    run = evaluate(tmp_path / "report.md", data, responses)

    statuses = [case_run.turns[0].status for case_run in run.result.runs]
    assert statuses == ["matched", "mismatched", "matched"]
    assert run.result.demo == {"demo-01": False}
    assert "程式比對 3 次全過" not in run.report


def test_demo_passing_runs_wait_for_manual_check(tmp_path: Path) -> None:
    data = cases_data(
        case(
            "demo-01",
            turn("我們 4 個人", action="recommend", manual=["推薦理由有引用心得"]),
            demo=True,
        )
    )

    run = evaluate(tmp_path / "report.md", data, RECOMMEND * 3)

    # 程式比對全過還不算過：要等立倫勾完人工項目（MR 說明的解讀 2）
    assert run.result.demo == {"demo-01": True}
    assert "程式比對 3 次全過，人工項目請勾選後確認" in run.report


def test_repeat_applies_to_non_demo_cases(tmp_path: Path) -> None:
    data = cases_data(
        case("case-01", turn("想找桌遊", action="follow_up")),
        case("demo-01", turn("想找桌遊", action="follow_up"), demo=True),
    )

    run = evaluate(tmp_path / "report.md", data, [final("請問幾個人？")] * 5, repeat=2)

    assert Counter(case_run.case_id for case_run in run.result.runs) == {
        "case-01": 2,
        "demo-01": 3,
    }
    # 每一次的項目都算分：5 次各 1 個項目
    assert run.result.constraint == (5, 5)


# --- 報告（spec §15.4） ---


def test_report_has_tokens_and_checkboxes(tmp_path: Path) -> None:
    out_path = tmp_path / "eval-report.md"
    data = cases_data(
        case(
            "case-01",
            turn("我們 4 個人，30 分鐘內", action="recommend", manual=["回覆有說明放寬了時長"]),
        )
    )
    responses = [
        with_tokens(search(players=4, max_minutes=30), 120, 30),
        with_tokens(final("推薦你這款", rec(1, "e1a", reason="大家一起笑得很開心")), 200, 45),
    ]

    run = evaluate(out_path, data, responses)

    report = out_path.read_text(encoding="utf-8")
    # token 用量：每次 respond 的用量加總
    assert (run.result.input_tokens, run.result.output_tokens) == (320, 75)
    assert "輸入 320" in report
    assert "輸出 75" in report
    assert "- [ ] 回覆有說明放寬了時長" in report
    # 每一輪的玩家訊息、回覆、工具參數、卡片的名稱、推薦理由與片段原文
    for text in ("我們 4 個人，30 分鐘內", "推薦你這款", "max_minutes", "甲", "大家一起笑得很開心"):
        assert text in report
    assert "第 1 款的片段 a" in report


# --- 開始前檢查（spec §15.1）：不通過就拒絕執行，不呼叫模型 ---

FOLLOW_UP_CASE = cases_data(case("case-01", turn("想找桌遊", action="follow_up")))


def test_existing_report_path_is_refused(tmp_path: Path) -> None:
    out_path = tmp_path / "report.md"
    out_path.write_text("上一次的報告", encoding="utf-8")

    reasons, calls = refuse(out_path, FOLLOW_UP_CASE)

    assert any(str(out_path) in reason for reason in reasons)
    assert calls == []
    assert out_path.read_text(encoding="utf-8") == "上一次的報告"


@pytest.mark.parametrize(
    ("vectors", "command"),
    [
        pytest.param({"summary_models": {3: "old-model"}}, "summarize-reviews", id="心得摘要"),
        pytest.param(
            {"excerpt_models": {3: [MODEL, "old-model"]}}, "build-excerpts", id="心得片段"
        ),
    ],
)
def test_other_embedding_model_is_refused(
    tmp_path: Path, vectors: dict[str, dict[int, Any]], command: str
) -> None:
    repo = make_eval_repo()
    for name, models in vectors.items():
        getattr(repo, name).update(models)
    out_path = tmp_path / "report.md"

    reasons, calls = refuse(out_path, FOLLOW_UP_CASE, repo=repo)

    text = "\n".join(reasons)
    # 印出是哪幾款、用了哪個模型，提醒重跑哪個指令
    assert "丙" in text
    assert "old-model" in text
    assert command in text
    assert "甲" not in text
    assert calls == []
    assert not out_path.exists()


def test_games_without_vectors_only_warn(tmp_path: Path) -> None:
    repo = make_eval_repo()
    del repo.summary_models[4]  # 丁沒有心得摘要向量
    del repo.excerpt_models[3]  # 丙沒有心得片段

    run = evaluate(tmp_path / "report.md", FOLLOW_UP_CASE, [final("請問幾個人？")], repo=repo)

    warnings = run.result.warnings
    assert any("丁" in warning and "心得摘要" in warning for warning in warnings)
    assert any("丙" in warning and "心得片段" in warning for warning in warnings)
    assert not any("甲" in warning for warning in warnings)
    # 照常執行
    assert run.result.runs[0].turns[0].status == "matched"


def test_vector_warnings_come_before_any_model_call(tmp_path: Path) -> None:
    repo = make_eval_repo()
    del repo.summary_models[4]  # 丁沒有心得摘要向量
    llm = FakeLLMProvider(responses=[final("請問幾個人？")])
    warned: list[tuple[str, int]] = []

    evaluate(
        tmp_path / "report.md",
        FOLLOW_UP_CASE,
        [],
        repo=repo,
        llm=llm,
        warn=lambda message: warned.append((message, len(llm.calls))),
    )

    # 提醒在呼叫模型之前就送出：指令收到就印，執行的人可以先停下、不花額度（spec §15.1）
    assert any("丁" in message for message, _ in warned)
    assert all(calls == 0 for _, calls in warned)
    # 提醒之後照常執行
    assert len(llm.calls) == 1


@pytest.mark.parametrize(
    ("data", "words"),
    [
        pytest.param(
            cases_data(
                case("dup-01", turn(action="follow_up")), case("dup-01", turn(action="follow_up"))
            ),
            ["dup-01", "重複"],
            id="id 重複",
        ),
        pytest.param(
            cases_data(case("bad-01", turn(action="suggest"))), ["action"], id="action 不對"
        ),
        pytest.param(
            cases_data(case("bad-02", turn(action="follow_up", expected_game=1))),
            ["expected_game"],
            id="不認得的欄位",
        ),
        pytest.param(
            cases_data(case("bad-03", turn(action="recommend", expect_any=[999999]))),
            ["999999"],
            id="資料庫沒有的 BGG ID",
        ),
    ],
)
def test_invalid_eval_cases_are_refused(
    tmp_path: Path, data: dict[str, Any], words: list[str]
) -> None:
    out_path = tmp_path / "report.md"

    reasons, calls = refuse(out_path, data)

    text = "\n".join(reasons)
    for word in words:
        assert word in text
    assert calls == []
    assert not out_path.exists()
