# 05：資料表

Status: ready-for-agent
Blocked by: 04
Spec: [spec](../../games-advisor/spec.md) §3
MR: （還沒開）

## 要做什麼

建立 games_advisor 的 4 張資料表，放在同一個 migration。向量欄位的維度讀 04 新增的 `GAMES_ADVISOR_EMBEDDING_DIM`。repository 函式不在這裡寫，跟著用到它的指令或 service 一起寫。

## 驗收條件

- [ ] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [ ] spec §3.5 的每一列都有測試而且通過
- [ ] AGENTS.md §2 第 7 點的三項檢查通過
- [ ] MR @ 瑋鋐（審核 migration，AGENTS.md §4.4）
- [ ] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結
