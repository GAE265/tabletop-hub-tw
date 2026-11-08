# 06：心得管線

Status: ready-for-agent
Blocked by: 05
Spec: [spec](../../games-advisor/spec.md) §6–§9
MR: （還沒開）

## 要做什麼

建立批次指令模組 `app.domains.games_advisor.commands` 與 7 個子指令：匯入桌遊、心得摘要、心得片段、歸納詞彙表、同步詞彙表、上標籤、匯入標籤草稿。測試只用假的 LLM、embedding 與自編的假資料。

## 驗收條件

- [ ] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [ ] spec §7.2、§8.1–§8.8、§9 的每一列都有測試而且通過
- [ ] AGENTS.md §2 第 7 點的三項檢查通過
- [ ] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結
