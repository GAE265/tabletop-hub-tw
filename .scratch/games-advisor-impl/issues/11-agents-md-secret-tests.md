# 11：AGENTS.md 加上需要金鑰的測試規則

Status: resolved
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §2、§18
MR: [#18](https://github.com/GAE265/tabletop-hub-tw/pull/18)（分支 `chore/test-classification`，組員提出；原本的 #17 已關閉）

## 結果

2026-11-10 #18 合併進 dev，寫成 AGENTS.md 7.6「測試分類」。下面的「建議條文」是當初的草稿，留著當紀錄；和定案不同的地方：

- 標記叫 `external`，不是 `real`；名稱是「外部服務測試」。
- 只有 `integrations/` 的測試可以需要金鑰；domain 的測試一律用 `integrations/` 的假實作。
- 觸發條件是「有修改 `integrations/` 的 MR」，要在 MR 說明貼上 `uv run pytest -m external` 的結果（通過幾個、失敗幾個）。
- `backend/pyproject.toml` 的 `markers` 與 `addopts = "-m 'not external'"` 已在 #18 加好，ticket 08 不用再做。
- `.github/pull_request_template.md` 沒有改。

## 要做什麼

需要 API 金鑰才能跑的測試（spec §2 的「需要金鑰的測試」）不進 CI，只在本機通過。AGENTS.md §7.2 目前不准用 skip，用標記排除測試會被當成同一件事，所以要先把規則寫進 AGENTS.md。AI 不改 AGENTS.md，由立倫親手修改；同一個 MR 裡的 3 份流程文件由 AI 起草。

組員的想法是「單元測試可以，但功能測試就不用在 CI 上跑，只在本地的功能測試通過」。條文改用「需不需要金鑰」來分：

- 「功能測試」範圍不明確，每個測試都在測某個功能。照寬鬆的讀法，router、repository、seed、migration 測試都會移出 CI。
- 「需不需要金鑰」看一眼測試就能判斷。

能用 fake 或 `MockTransport` 寫的測試照樣進 CI。評估題組是指令，不算這類測試（spec §15）。

## 建議條文（AGENTS.md §7 新增 7.6）

```markdown
### 7.6 需要金鑰的測試

- 需要 API 金鑰或其他秘密才能執行的後端測試，加上 `@pytest.mark.real`。這些測試不在 CI 執行。MR 新增、修改這類測試，或改到它們測試的程式時，發 MR 前要在本機執行 `uv run pytest -m real` 並全部通過。
- 能用 fake 或假造回應（例如 httpx `MockTransport`）寫的測試，一律寫成不需要金鑰的測試，照常在 CI 執行。
- MR 說明的情境表格中，需要金鑰的測試標上「（本機）」，並在表格外附上執行指令、通過數量與執行日期。
- 用 `real` 標記排除在 CI 外，不算 7.2 禁止的 skip；但不得用 `skip`、`xfail` 掩蓋需要金鑰的測試失敗。
```

配合修改：

- §2 第 7 點：補上「MR 新增、修改需要金鑰的測試，或改到它們測試的程式時，加跑 `uv run pytest -m real`（7.6）」。沒有金鑰的組員（例如只做訂位）不受影響。
- §8.3 後端的 `pytest`：補上「不含 `real` 標記的測試」。

## 驗收條件

- [x] AGENTS.md §7 加上 7.6，並配合修改 §2 第 7 點、§8.3（#18）
- [x] `docs/test-first-flow.md`：自我檢查表加上 `uv run pytest -m external`；「可以用 skip 嗎」補上外部服務測試的說明（#18）
- [ ] `.github/pull_request_template.md`：自我檢查加一行需要金鑰的測試（#18 沒有改，不擋結案）
- [x] `docs/review-guide.md`：加上「動到 `integrations/` 的 MR 要附 external 測試結果」（#18）
- [x] MR 說明的情境表格寫「不適用」，理由是只改文件（AGENTS.md §7.4）（#18）
- [x] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結（本檔在 #15 的分支，#15 合併前就在那個分支改）
