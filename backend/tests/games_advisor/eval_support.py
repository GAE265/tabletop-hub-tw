"""評估題組測試（spec §15）共用的題目、腳本與執行方式。

桌遊、心得片段與腳本項目沿用 conversation_support：甲乙丙丁 4 款，bgg_id 是 800000 + id。
要測的程式都在函式裡才 import：程式還沒寫的時候，每個情境各自失敗（同 conftest.py 的說明）。
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from app.integrations.embedding import FakeEmbeddingProvider
from app.integrations.llm import FakeCall, FakeLLMProvider, FakeResponse
from tests.games_advisor.conversation_support import DIM, GAMES, MODEL, make_repo
from tests.games_advisor.fakes import FakeSearchRepository

if TYPE_CHECKING:
    from app.domains.games_advisor.evaluation import EvalResult, TurnResult

Script = list[FakeResponse | Exception]
JudgeScript = list[dict[str, Any] | Exception]

# 評審的輸出：沒有找不到依據的說法，也就是「有依據」
SUPPORTED: dict[str, Any] = {"unsupported": []}


def bgg(game_id: int) -> int:
    """conversation_support 第 game_id 款假桌遊的 BGG ID。"""
    return 800000 + game_id


def turn(player: str = "我們 4 個人", **expect: Any) -> dict[str, Any]:
    """題組檔的一輪：玩家訊息，以及這一輪要檢查的欄位。"""
    return {"player": player, "expect": expect}


def case(case_id: str, *turns: dict[str, Any], demo: bool = False) -> dict[str, Any]:
    return {"id": case_id, "demo": demo, "turns": list(turns)}


def cases_data(*cases: dict[str, Any]) -> dict[str, Any]:
    """eval_cases.json 的內容（spec §15.2）。"""
    return {"cases": list(cases)}


def with_tokens(response: FakeResponse, input_tokens: int, output_tokens: int) -> FakeResponse:
    return replace(response, input_tokens=input_tokens, output_tokens=output_tokens)


def make_eval_repo() -> FakeSearchRepository:
    """conversation_support 的假桌遊；每款都有目前模型（MODEL）產生的心得摘要向量與心得片段。"""
    repo = make_repo()
    repo.summary_models = {values["id"]: MODEL for values in GAMES}
    repo.excerpt_models = {values["id"]: [MODEL] for values in GAMES}
    return repo


@dataclass(frozen=True)
class EvalRun:
    """評估跑完一次：結果、對話與評審的 fake（--no-judge 時沒有評審），以及報告的內容。"""

    result: "EvalResult"
    llm: FakeLLMProvider
    judge: FakeLLMProvider | None
    report: str


def _run_eval(
    out_path: Path,
    data: dict[str, Any],
    llm: FakeLLMProvider,
    judge: FakeLLMProvider | None,
    *,
    repo: FakeSearchRepository | None,
    repeat: int,
    llm_model: str,
    judge_model: str,
) -> "EvalResult":
    from app.domains.games_advisor.evaluation import Judge, run_eval

    repo = make_eval_repo() if repo is None else repo
    return run_eval(
        data,
        games=repo,
        tags=repo,
        reviews=repo,
        embedding=FakeEmbeddingProvider(DIM),
        embedding_model=MODEL,
        llm=llm,
        llm_model=llm_model,
        judge=None if judge is None else Judge(llm=judge, model=judge_model),
        out_path=out_path,
        repeat=repeat,
    )


def evaluate(
    out_path: Path,
    data: dict[str, Any],
    responses: Script,
    *,
    judge_outputs: JudgeScript | None = None,
    repo: FakeSearchRepository | None = None,
    repeat: int = 1,
    llm_model: str = "model-a",
    judge_model: str = "model-b",
) -> EvalRun:
    """跑評估題組，報告寫到 out_path。

    對話照 responses 的腳本回應。judge_outputs 是評審的腳本；給 None 等於加了 --no-judge，
    不建評審的 provider。
    """
    llm = FakeLLMProvider(responses=responses)
    judge = None if judge_outputs is None else FakeLLMProvider(json_outputs=judge_outputs)
    result = _run_eval(
        out_path,
        data,
        llm,
        judge,
        repo=repo,
        repeat=repeat,
        llm_model=llm_model,
        judge_model=judge_model,
    )
    return EvalRun(result, llm, judge, out_path.read_text(encoding="utf-8"))


def refuse(
    out_path: Path, data: dict[str, Any], *, repo: FakeSearchRepository | None = None
) -> tuple[list[str], list[FakeCall]]:
    """跑評估題組，確認開始前就拒絕執行；指令收到 Refused 會印出原因、結束碼 1。

    回傳拒絕的原因，以及對話與評審的 fake 收到的所有呼叫（應該是空的）。
    """
    from app.domains.games_advisor.service import Refused

    llm = FakeLLMProvider(responses=[])
    judge = FakeLLMProvider(json_outputs=[])
    with pytest.raises(Refused) as caught:
        _run_eval(
            out_path,
            data,
            llm,
            judge,
            repo=repo,
            repeat=1,
            llm_model="model-a",
            judge_model="model-b",
        )
    return caught.value.reasons, llm.calls + judge.calls


def only_turn(run: EvalRun) -> "TurnResult":
    """只有 1 題、跑 1 次、1 輪時，那一輪的結果。"""
    [case_run] = run.result.runs
    [turn_result] = case_run.turns
    return turn_result
