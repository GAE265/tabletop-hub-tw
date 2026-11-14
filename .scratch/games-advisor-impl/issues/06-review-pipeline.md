# 06：心得管線

Status: resolved
Blocked by: 05
Spec: [spec](../../games-advisor/spec.md) §6–§9
MR: [#24](https://github.com/GAE265/tabletop-hub-tw/pull/24)

## 要做什麼

建立批次指令模組 `app.domains.games_advisor.commands` 與 9 個子指令：匯入桌遊、匯出共用桌遊資料、同步共用桌遊資料、心得摘要、心得片段、歸納詞彙表、同步詞彙表、上標籤、匯入標籤草稿。測試只用假的 LLM、embedding 與自編的假資料。

2026-11-12 `games.id` 改成整數、自動給號（spec〔整數編號〕、[ADR 0003](../../../docs/adr/0003-shared-games-table.md)）：

- 匯入桌遊不再用編號對應檔：只有立倫在空資料庫執行一次，`--first-four` 指定 1–4 號的 4 款 Demo 遊戲，其他照檔案順序自動給號（spec §8.1）。匯入後 `games.json` 不再使用。
- 新增匯出（spec §8.10）與同步（spec §8.11）：立倫匯出、放進團隊共用雲端資料夾 GAE265G5，其他組員同步，讓每個人的共用表和編號完全一樣；同步後新增的桌遊從匯出檔的 `next_id` 接著給號。

## 驗收條件

- [x] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [x] spec §7.2、§8.1–§8.8、§8.10、§8.11、§9 的每一列都有測試而且通過
- [x] MR 說明寫出其他組員怎麼同步（下載 GAE265G5 的匯出檔 → 執行 `sync-games`），合併後通知組員
- [x] AGENTS.md §2 第 7 點的三項檢查通過
- [x] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結
