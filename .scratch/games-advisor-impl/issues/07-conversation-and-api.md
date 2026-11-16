# 07：推薦對話與 API

Status: resolved
Blocked by: 01、05
Spec: [spec](../../games-advisor/spec.md) §10–§13
MR: [#26](https://github.com/GAE265/tabletop-hub-tw/pull/26)

## 要做什麼

做「查桌遊」工具、對話 service 與 `POST /api/v1/advisor/messages`。玩家送出訊息後，推薦 Agent 追問或推薦最多 3 款桌遊。測試用 `FakeLLMProvider` 的腳本，不連 Azure。

## 驗收條件

- [x] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [x] spec §11.8、§12.7、§13.4 的每一列都有測試而且通過
- [x] 02 改走備案的話，照修改後的 spec 寫（02 沒有改走備案，不適用）
- [x] AGENTS.md §2 第 7 點的三項檢查通過
- [x] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結
