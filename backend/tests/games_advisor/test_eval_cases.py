"""repo 裡的題組檔 eval_cases.json（spec §15.2、§15.5）。

讀真的 eval_cases.json 與 tag_vocabulary.json。兩個檔要等心得管線跑完、立倫定案後才會放進
repo，在那之前這兩個測試是紅燈。
"""

import json

from tests.db_utils import BACKEND_DIR

EVAL_CASES = BACKEND_DIR / "tests" / "games_advisor" / "eval_cases.json"
TAG_VOCABULARY = BACKEND_DIR / "app" / "domains" / "games_advisor" / "tag_vocabulary.json"


def test_eval_cases_format() -> None:
    from app.domains.games_advisor.schemas import EvalCasesFile

    data = json.loads(EVAL_CASES.read_text(encoding="utf-8"))

    # 不通過時拋 ValidationError，列出哪一題的哪個欄位不對：
    # id 沒寫或重複、action 不是三種之一、expect 有不認得的欄位
    cases = EvalCasesFile.model_validate(data).cases

    assert cases, "題組是空的"


def test_eval_cases_use_vocabulary_codes() -> None:
    cases = json.loads(EVAL_CASES.read_text(encoding="utf-8"))["cases"]
    vocabulary = json.loads(TAG_VOCABULARY.read_text(encoding="utf-8"))["tags"]
    codes = {tag["code"] for tag in vocabulary}

    # 標籤只出現在 tool_args 的 prefer_tags、avoid_tags
    used = {
        (case["id"], code)
        for case in cases
        for turn in case["turns"]
        for name in ("prefer_tags", "avoid_tags")
        for code in (turn["expect"].get("tool_args") or {}).get(name) or []
    }

    assert sorted(item for item in used if item[1] not in codes) == [], "題組用到詞彙表沒有的代碼"
