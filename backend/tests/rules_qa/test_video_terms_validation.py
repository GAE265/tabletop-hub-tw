"""用語對照表的共用驗證：命令列的 load_terms 與 API 用同一份規則（MR 3，design.md D4）。"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.domains.rules_qa.video_script import ScriptInputError, load_terms, term_conflicts
from tests.rules_qa.video_script_support import TERMS


def _write(tmp_path: Path, terms: list[dict[str, Any]]) -> Path:
    path = tmp_path / "terms.json"
    path.write_text(json.dumps(terms, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_file_loads_as_before(tmp_path: Path) -> None:
    terms = load_terms(_write(tmp_path, TERMS))
    assert [t.key for t in terms] == [t["key"] for t in TERMS]
    zone = next(t for t in terms if t.key == "zone_a")
    assert zone.zh == "甲區" and zone.avoid == ("A區",) and zone.category is None


def test_values_are_trimmed(tmp_path: Path) -> None:
    terms = load_terms(_write(tmp_path, [{"en": " Red card ", "zh": " 紅牌 ", "key": " red "}]))
    assert (terms[0].en, terms[0].zh, terms[0].key) == ("Red card", "紅牌", "red")


def test_duplicate_en_ignores_case_and_spaces(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [{"en": "White Rose", "zh": "白薔薇"}, {"en": " white rose ", "zh": "白玫瑰"}],
    )
    with pytest.raises(ScriptInputError) as exc:
        load_terms(path)
    assert "en" in str(exc.value) and "White Rose" in str(exc.value)


def test_duplicate_key_with_same_category_is_allowed(tmp_path: Path) -> None:
    # 規則書用兩個英文名稱指同一個區域（design.md D4）
    terms = load_terms(
        _write(
            tmp_path,
            [
                {"en": "White Rose placement area", "zh": "白薔薇區", "key": "white_rose_zone",
                 "category": "single"},
                {"en": "Sanctuary", "zh": "聖所", "key": " WHITE_ROSE_ZONE ", "category": "single"},
            ],
        )
    )  # fmt: skip
    assert len(terms) == 2


def test_duplicate_key_with_one_category_missing_is_allowed(tmp_path: Path) -> None:
    terms = load_terms(
        _write(
            tmp_path,
            [
                {"en": "White Rose placement area", "zh": "白薔薇區", "key": "white_rose_zone",
                 "category": "single"},
                {"en": "Sanctuary", "zh": "聖所", "key": "white_rose_zone"},
            ],
        )
    )  # fmt: skip
    assert len(terms) == 2


def test_duplicate_key_with_different_category_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {"en": "Knight cards", "zh": "騎士牌", "key": "knight", "category": "generic"},
            {"en": "Red Knight", "zh": "紅騎士", "key": "Knight", "category": "single"},
        ],
    )
    with pytest.raises(ScriptInputError) as exc:
        load_terms(path)
    message = str(exc.value)
    assert "knight" in message.lower() and "category" in message


@pytest.mark.parametrize(
    "bad",
    [
        {"en": "X", "zh": "叉" * 101},
        {"en": "", "zh": "叉"},
        {"en": "X", "zh": "叉", "avoid": [""]},
        {"en": "X", "zh": "叉", "avoid": "叉叉"},
    ],
    ids=["zh_too_long", "en_empty", "avoid_empty_string", "avoid_not_list"],
)
def test_invalid_entry_is_rejected(tmp_path: Path, bad: dict[str, Any]) -> None:
    with pytest.raises(ScriptInputError) as exc:
        load_terms(_write(tmp_path, [bad]))
    assert "第 1 筆" in str(exc.value)


def test_too_many_entries(tmp_path: Path) -> None:
    terms = [{"en": f"Term {i}", "zh": f"詞{i}"} for i in range(501)]
    with pytest.raises(ScriptInputError) as exc:
        load_terms(_write(tmp_path, terms))
    assert "500" in str(exc.value)


def test_term_conflicts_lists_every_problem() -> None:
    from app.domains.rules_qa.video_script import Term

    problems = term_conflicts(
        [
            Term("A", "甲", "k", (), "generic"),
            Term("a", "乙", "K", (), "single"),
        ]
    )
    kinds = sorted(p.kind for p in problems)
    assert kinds == ["category_conflict", "duplicate_en"]
