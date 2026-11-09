## 說明

<!-- 這個 MR 做了什麼、為什麼。一個 MR 只做一件事。 -->

## 測試案例表格

<!-- AGENTS.md 7.2：先列給組員看過。至少包含正常、輸入錯誤、沒有權限、狀態衝突（若有）。 -->

| 情境 | 操作 | 預期結果 |
|---|---|---|
| | | |

## 是否動到契約

<!-- API 路徑／資料格式、資料表結構、MQTT 主題與訊息格式、domain 之間的介面 -->

- [ ] 沒有
- [ ] 有，內容：
  - [ ] API 契約（已 @ 立倫）
  - [ ] migration（已 @ 瑋鋐）
  - [ ] 其他：

## 是否需要 UI（needs-ui）

- [ ] 不需要
- [ ] 需要：已加上 `needs-ui` 標籤、已寫 `docs/handoff/<domain>.md`、已 @ 永傑

## 自我檢查

- [ ] 後端（`backend/`）：`uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`
- [ ] 需要金鑰的測試（`uv run pytest -m real`）已在本機通過，指令、通過數量與日期附在上方說明（沒有相關改動就寫不適用）
- [ ] 前端（`frontend/`）：`flutter analyze`、`flutter test`
- [ ] 沒有提交秘密、規則書全文或合作店家資料
- [ ] 只改了被指派的 domain；動到共用區已在上方說明並 @ 主責
- [ ] 新增第三方套件已寫理由：
