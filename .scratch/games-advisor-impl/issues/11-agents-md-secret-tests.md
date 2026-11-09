# 11：AGENTS.md 加上需要金鑰的測試規則

Status: ready-for-human
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §2、§18
MR: （還沒開）分支 `docs/secret-tests-rule`，從 `dev` 開

## 要做什麼

需要 API 金鑰才能跑的測試（spec §2 的「需要金鑰的測試」）不進 CI，只在本機通過。AGENTS.md §7.2 目前不准用 skip，用標記排除測試會被當成同一件事，所以要先把規則寫進 AGENTS.md。AI 不改 AGENTS.md，由立倫親手修改；同一個 MR 裡的 3 份流程文件由 AI 起草。

組員的想法是「單元測試可以，但功能測試就不用在 CI 上跑，只在本地的功能測試通過」。條文改用「需不需要金鑰」來分：

- 「功能測試」範圍不明確，每個測試都在測某個功能。照寬鬆的讀法，router、repository、seed、migration 測試都會移出 CI。
- 「需不需要金鑰」看一眼測試就能判斷。

能用 fake 或 `MockTransport` 寫的測試照樣進 CI。評估題組是指令，不算這類測試（spec §15）。

## 建議條文（AGENTS.md §7 新增 7.6）

```markdown
### 7.6 需要金鑰的測試

- 需要 API 金鑰或其他秘密才能執行的後端測試，加上 `@pytest.mark.real`。這些測試不在 CI 執行，發 MR 前要在本機執行 `uv run pytest -m real` 並全部通過。
- 能用 fake 或假造回應（例如 httpx `MockTransport`）寫的測試，一律寫成不需要金鑰的測試，照常在 CI 執行。
- MR 說明的情境表格中，需要金鑰的測試標上「（本機）」，並在表格外附上執行指令、通過數量與執行日期。
- 用 `real` 標記排除在 CI 外，不算 7.2 禁止的 skip；但不得用 `skip`、`xfail` 掩蓋需要金鑰的測試失敗。
```

配合修改：

- §2 第 7 點：補上「有需要金鑰的測試時，加跑 `uv run pytest -m real`」。
- §8.3 後端的 `pytest`：補上「不含 `real` 標記的測試」。

## 驗收條件

- [ ] 立倫親手在 AGENTS.md §7 加上 7.6，並配合修改 §2 第 7 點、§8.3
- [ ] `docs/test-first-flow.md`：自我檢查表加上 `uv run pytest -m real`；「可以用 skip 嗎」補上需要金鑰的測試的說明
- [ ] `.github/pull_request_template.md`：自我檢查加一行需要金鑰的測試
- [ ] `docs/review-guide.md`：測試案例的檢查加一條「（本機）的測試有附上本機執行結果」
- [ ] MR 說明的情境表格寫「不適用」，理由是只改文件（AGENTS.md §7.4）
- [ ] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結（本檔在 #15 的分支，#15 合併前就在那個分支改）
