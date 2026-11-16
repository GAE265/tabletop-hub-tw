"""評審建議（spec §15.6）：每張卡片多呼叫 1 次模型，檢查推薦理由有沒有寫出依據裡沒有的內容。

對話用 FakeLLMProvider(responses=...)，評審用另一個 FakeLLMProvider(json_outputs=...)；
桌遊用假的 repository，不連資料庫也不連 Azure。評審只給建議，不算分（spec §15.3）。
「結束碼 0」：評估題組跑完就是 0（spec §15.3），這裡檢查 run_eval 正常回傳、報告照寫。
"""

from pathlib import Path

from app.integrations.llm import LLMError, LLMOutputRejected, LLMUnavailable
from tests.games_advisor.conversation_support import final, rec, search
from tests.games_advisor.eval_support import (
    SUPPORTED,
    EvalRun,
    case,
    cases_data,
    evaluate,
    make_eval_repo,
    only_turn,
    turn,
)
from tests.games_advisor.support import make_tag

ONE_TURN = cases_data(case("judge-01", turn("我們 2 個人", action="recommend")))
# 查 2 人（甲、乙），推薦 1 款或 2 款，每張卡片引用 1 段心得片段
ONE_CARD = [search(players=2), final("推薦你這款", rec(1, "e1a"))]
TWO_CARDS = [search(players=2), final("推薦你這兩款", rec(1, "e1a"), rec(2, "e2a"))]


def judge_inputs(run: EvalRun) -> list[str]:
    assert run.judge is not None
    return [call.kwargs["input"] for call in run.judge.calls]


def test_judge_supported(tmp_path: Path) -> None:
    run = evaluate(tmp_path / "report.md", ONE_TURN, ONE_CARD, judge_outputs=[SUPPORTED])

    [card] = only_turn(run).cards
    assert card.judge.status == "supported"
    assert "評審建議：有依據" in run.report


def test_judge_unsupported_lists_items(tmp_path: Path) -> None:
    doubt = "理由說「適合新手」，片段和命中的偏好都沒有提到"

    run = evaluate(
        tmp_path / "report.md", ONE_TURN, ONE_CARD, judge_outputs=[{"unsupported": [doubt]}]
    )

    [card] = only_turn(run).cards
    assert (card.judge.status, card.judge.unsupported) == ("unsupported", [doubt])
    assert "評審建議：有疑慮" in run.report
    assert doubt in run.report


def test_judge_input_has_card_evidence_only(tmp_path: Path) -> None:
    repo = make_eval_repo()
    repo.tags = [make_tag("laughter"), make_tag("luck")]
    repo.game_tags = {1: {"laughter": 0.9, "luck": 0.8}}
    responses = [
        search(players=2, prefer_tags=["laughter"], avoid_tags=["luck"]),
        final("推薦你這款", rec(1, "e1a", reason="大家一起大笑，但很看運氣")),
    ]

    run = evaluate(
        tmp_path / "report.md", ONE_TURN, responses, judge_outputs=[SUPPORTED], repo=repo
    )

    [judge_input] = judge_inputs(run)
    assert "大家一起大笑，但很看運氣" in judge_input  # 推薦理由
    assert "第 1 款的片段 a" in judge_input  # 卡片上的心得片段原文
    assert "歡樂爆笑" in judge_input  # 甲命中的偏好（matched_preferences）
    assert "運氣影響大" in judge_input  # 甲命中的負面偏好（matched_avoids）
    # 工具有回傳、卡片沒引用的片段不給；同一次查詢的其他桌遊也不給
    assert "第 1 款的片段 b" not in judge_input
    assert "第 2 款" not in judge_input


def test_judge_input_has_matches_from_both_searches(tmp_path: Path) -> None:
    repo = make_eval_repo()
    repo.tags = [make_tag("laughter"), make_tag("scheming")]
    repo.game_tags = {1: {"laughter": 0.9, "scheming": 0.7}}
    # 兩次查詢都回傳甲：第 1 次命中歡樂爆笑，第 2 次命中勾心鬥角
    responses = [
        search(players=2, prefer_tags=["laughter"]),
        search("call_2", players=2, prefer_tags=["scheming"]),
        final("推薦你這款", rec(1, "e1a")),
    ]

    run = evaluate(
        tmp_path / "report.md", ONE_TURN, responses, judge_outputs=[SUPPORTED], repo=repo
    )

    [judge_input] = judge_inputs(run)
    assert "歡樂爆笑" in judge_input
    assert "勾心鬥角" in judge_input


def test_judge_called_once_per_card(tmp_path: Path) -> None:
    data = cases_data(case("judge-02", turn("我們 4 個人", action="recommend")))
    cards = [(1, "理由甲"), (2, "理由乙"), (3, "理由丙")]
    responses = [
        search(players=4),
        final("推薦你這三款", *(rec(game_id, f"e{game_id}a", reason=r) for game_id, r in cards)),
    ]

    run = evaluate(tmp_path / "report.md", data, responses, judge_outputs=[SUPPORTED] * 3)

    inputs = judge_inputs(run)
    assert len(inputs) == 3
    # 照卡片的順序，每次只有那一張卡片的推薦理由與片段
    for judge_input, (game_id, reason) in zip(inputs, cards, strict=True):
        assert reason in judge_input
        assert f"第 {game_id} 款的片段 a" in judge_input
        others = [other for other_id, other in cards if other_id != game_id]
        assert not any(other in judge_input for other in others)


def test_judge_does_not_affect_scores(tmp_path: Path) -> None:
    data = cases_data(
        case(
            "demo-01",
            turn("我們 2 個人", action="recommend", manual=["推薦理由有引用心得"]),
            demo=True,
        )
    )
    doubt = {"unsupported": ["理由說「適合新手」，片段沒有提到"]}

    doubtful = evaluate(tmp_path / "doubt.md", data, ONE_CARD * 3, judge_outputs=[doubt] * 3)
    supported = evaluate(tmp_path / "fine.md", data, ONE_CARD * 3, judge_outputs=[SUPPORTED] * 3)

    def scores(run: EvalRun) -> tuple[object, ...]:
        result = run.result
        return (result.constraint, result.preference, result.manual_items, result.demo)

    assert scores(doubtful) == scores(supported)
    assert doubtful.result.demo == {"demo-01": True}


def test_card_without_excerpts_is_not_judged(tmp_path: Path) -> None:
    responses = [search(players=2), final("推薦你這款", rec(1))]

    run = evaluate(tmp_path / "report.md", ONE_TURN, responses, judge_outputs=[])

    assert judge_inputs(run) == []
    [card] = only_turn(run).cards
    assert card.judge.status == "not_judged"
    assert "未評審：沒有引用心得片段" in run.report


def test_empty_reason_is_not_judged(tmp_path: Path) -> None:
    responses = [search(players=2), final("推薦你這款", rec(1, "e1a", reason=""))]

    run = evaluate(tmp_path / "report.md", ONE_TURN, responses, judge_outputs=[])

    assert judge_inputs(run) == []
    [card] = only_turn(run).cards
    assert card.judge.status == "not_judged"
    assert "未評審：推薦理由是空的" in run.report


def test_turns_without_cards_are_not_judged(tmp_path: Path) -> None:
    data = cases_data(
        case(
            "judge-03",
            turn("想找桌遊", action="follow_up"),
            turn("今天天氣如何？", action="off_topic"),
            turn("我們 4 個人", action="recommend"),  # 拿到固定文字，停下
            turn("換一批", action="recommend"),  # 未執行
        )
    )
    responses = [final("請問幾個人？"), final("我只能幫你找桌遊喔"), LLMOutputRejected("內容過濾")]

    run = evaluate(tmp_path / "report.md", data, responses, judge_outputs=[])

    assert judge_inputs(run) == []
    statuses = [result.status for result in run.result.runs[0].turns]
    assert statuses == ["matched", "matched", "mismatched", "not_run"]


def test_no_judge_skips_all_judging(tmp_path: Path) -> None:
    # judge_outputs 沒給：等於加了 --no-judge，沒有評審的 provider
    run = evaluate(tmp_path / "report.md", ONE_TURN, ONE_CARD)

    assert run.judge is None
    assert {call.method for call in run.llm.calls} == {"respond"}
    assert "這次沒有跑評審" in run.report
    assert "評審建議：" not in run.report


def test_judge_retries_once_on_rejected_output(tmp_path: Path) -> None:
    run = evaluate(
        tmp_path / "report.md",
        ONE_TURN,
        ONE_CARD,
        judge_outputs=[LLMOutputRejected("輸出被截斷"), SUPPORTED],
    )

    assert len(judge_inputs(run)) == 2
    [card] = only_turn(run).cards
    assert card.judge.status == "supported"


def test_judge_gives_up_after_two_rejections(tmp_path: Path) -> None:
    run = evaluate(
        tmp_path / "report.md",
        ONE_TURN,
        TWO_CARDS,
        judge_outputs=[
            LLMOutputRejected("第 1 次被擋"),
            LLMOutputRejected("第 2 次被擋"),
            SUPPORTED,
        ],
    )

    # 第 1 張放棄，第 2 張照常評審；run_eval 正常回傳，報告照寫
    first, second = only_turn(run).cards
    assert first.judge.status == "failed"
    assert "第 2 次被擋" in first.judge.note
    assert second.judge.status == "supported"
    assert "評審失敗" in run.report
    assert "第 2 次被擋" in run.report


def test_judge_unavailable_is_not_retried(tmp_path: Path) -> None:
    run = evaluate(
        tmp_path / "report.md",
        ONE_TURN,
        TWO_CARDS,
        judge_outputs=[LLMUnavailable("逾時"), SUPPORTED],
    )

    # 沒有重試：腳本的第 2 項給了第 2 張卡片
    first, second = only_turn(run).cards
    assert first.judge.status == "failed"
    assert "逾時" in first.judge.note
    assert second.judge.status == "supported"
    assert "評審失敗" in run.report


def test_judge_other_llm_error_is_not_retried(tmp_path: Path) -> None:
    run = evaluate(
        tmp_path / "report.md", ONE_TURN, TWO_CARDS, judge_outputs=[LLMError("金鑰錯誤"), SUPPORTED]
    )

    first, second = only_turn(run).cards
    assert first.judge.status == "failed"
    assert "金鑰錯誤" in first.judge.note
    assert second.judge.status == "supported"
    assert "評審失敗" in run.report


def test_conversation_and_judge_use_separate_providers(tmp_path: Path) -> None:
    run = evaluate(tmp_path / "report.md", ONE_TURN, ONE_CARD, judge_outputs=[SUPPORTED])

    assert run.judge is not None
    assert {call.method for call in run.llm.calls} == {"respond"}
    assert {call.method for call in run.judge.calls} == {"generate_json"}
    assert run.judge.calls[0].kwargs["schema"].name == "advisor_reason_check"


def test_report_header_shows_both_models(tmp_path: Path) -> None:
    run = evaluate(
        tmp_path / "report.md",
        ONE_TURN,
        ONE_CARD,
        judge_outputs=[SUPPORTED],
        llm_model="model-a",
        judge_model="model-b",
    )

    assert "對話模型：model-a" in run.report
    assert "評審模型：model-b" in run.report
    assert "評審和對話是同一個模型" not in run.report


def test_report_header_when_judge_uses_same_model(tmp_path: Path) -> None:
    # LLM_BATCH_MODEL 留空時，指令照 batch_llm_settings 退回 LLM_MODEL（test_review_commands.py
    # 已測），兩個模型名稱相同；這裡測報告怎麼寫
    run = evaluate(
        tmp_path / "report.md",
        ONE_TURN,
        ONE_CARD,
        judge_outputs=[SUPPORTED],
        llm_model="model-a",
        judge_model="model-a",
    )

    assert "評審模型：model-a" in run.report
    assert "評審和對話是同一個模型" in run.report


def test_report_footer_counts_judge_results(tmp_path: Path) -> None:
    data = cases_data(
        case(
            "judge-04",
            turn("我們 4 個人", action="recommend"),
            turn("那 6 個人呢？", action="recommend"),
        )
    )
    responses = [
        # 第 1 輪 3 張卡片：有依據、有依據、有疑慮
        search(players=4),
        final("推薦你這三款", rec(1, "e1a"), rec(2, "e2a"), rec(3, "e3a")),
        # 第 2 輪 2 張卡片：丙沒有引用片段（未評審），丁評審失敗
        search(players=6),
        final("推薦你這兩款", rec(3), rec(4, "e4a")),
    ]
    judge_outputs = [
        SUPPORTED,
        SUPPORTED,
        {"unsupported": ["沒有依據的說法"]},
        LLMError("金鑰錯誤"),
    ]

    run = evaluate(tmp_path / "report.md", data, responses, judge_outputs=judge_outputs)

    assert "評審統計：有依據 2 張／有疑慮 1 張／未評審 1 張／評審失敗 1 張" in run.report
    assert "評審建議不算分，以人工勾選為準" in run.report
