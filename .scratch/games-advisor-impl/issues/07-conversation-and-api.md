# 07：推薦對話與 API

Status: ready-for-agent
Blocked by: 01、05
Spec: [spec](../../games-advisor/spec.md) §10–§13
MR: （還沒開）

## 要做什麼

做「查桌遊」工具、對話 service 與 `POST /api/v1/advisor/messages`。玩家送出訊息後，推薦 Agent 追問或推薦最多 3 款桌遊。測試用 `FakeLLMProvider` 的腳本，不連 Azure。

## 驗收條件

- [ ] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [ ] spec §11.8、§12.7、§13.4 的每一列都有測試而且通過
- [ ] 02 改走備案的話，照修改後的 spec 寫
- [ ] AGENTS.md §2 第 7 點的三項檢查通過
- [ ] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結
