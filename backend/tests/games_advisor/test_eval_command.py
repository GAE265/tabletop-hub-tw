"""評估題組指令這一層的行為（spec §7.2 規則 3、§15.1、§15.6）。

- 經過 main()：連測試用的 PostgreSQL。run_command 一律設 LLM_PROVIDER=fake，所以 eval 一定在
  開始前就拒絕：真的跑一次評估題組要連 Azure，只在本機手動執行（spec §15.1）。
- 報告開頭要印的模型名稱：從設定決定，不連資料庫。報告怎麼印這兩個名稱在 test_eval_judge.py。
"""

from collections.abc import Callable
from pathlib import Path

from app.core.config import Settings
from tests.games_advisor.conftest import RunCommand
from tests.games_advisor.eval_support import case, cases_data, turn
from tests.games_advisor.support import write_json

MakeSettings = Callable[..., Settings]


def write_cases(tmp_path: Path) -> Path:
    data = cases_data(case("case-01", turn("想找桌遊", action="follow_up")))
    return write_json(tmp_path / "eval_cases.json", data)


def test_eval_refuses_fake_llm(run_command: RunCommand, tmp_path: Path) -> None:
    out_path = tmp_path / "report.md"

    result = run_command("eval", str(write_cases(tmp_path)), "--out", str(out_path))

    assert result.code == 1
    assert "需要真的模型，請設定 LLM_*" in result.err
    assert not out_path.exists()


def test_repeat_must_be_at_least_one(run_command: RunCommand, tmp_path: Path) -> None:
    out_path = tmp_path / "report.md"

    result = run_command(
        "eval", str(write_cases(tmp_path)), "--out", str(out_path), "--repeat", "0"
    )

    assert result.code == 1
    assert "usage" in result.err
    assert "--repeat" in result.err
    assert not out_path.exists()


# --- 報告開頭的模型名稱（spec §15.6） ---


def test_report_models_come_from_settings(make_settings: MakeSettings) -> None:
    from app.domains.games_advisor.commands import eval_model_names

    settings = make_settings(llm_model="model-a", llm_batch_model="model-b")

    assert eval_model_names(settings, judge=True) == ("model-a", "model-b")


def test_judge_model_falls_back_to_llm_model(make_settings: MakeSettings) -> None:
    from app.domains.games_advisor.commands import eval_model_names

    # LLM_BATCH_MODEL 留空：評審和批次指令一樣退回 LLM_MODEL（spec §7.2 規則 4）
    settings = make_settings(llm_model="model-a")

    assert eval_model_names(settings, judge=True) == ("model-a", "model-a")


def test_no_judge_has_no_judge_model(make_settings: MakeSettings) -> None:
    from app.domains.games_advisor.commands import eval_model_names

    settings = make_settings(llm_model="model-a", llm_batch_model="model-b")

    assert eval_model_names(settings, judge=False) == ("model-a", None)
