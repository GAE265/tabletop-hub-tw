"""評估題組指令經過 main() 的行為（spec §7.2 規則 3、§15.1）。

連測試用的 PostgreSQL。run_command 一律設 LLM_PROVIDER=fake，所以 eval 一定在開始前就拒絕：
真的跑一次評估題組要連 Azure，只在本機手動執行（spec §15.1）。
"""

from pathlib import Path

from tests.games_advisor.conftest import RunCommand
from tests.games_advisor.eval_support import case, cases_data, turn
from tests.games_advisor.support import write_json


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
