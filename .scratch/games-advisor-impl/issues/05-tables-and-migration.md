# 05：資料表

Status: resolved
Blocked by: 03、04
Spec: [spec](../../games-advisor/spec.md) §3
MR: [#22](https://github.com/GAE265/tabletop-hub-tw/pull/22)

## 要做什麼

建立 spec §3 的 7 張資料表，放在同一個 migration：共用表 `games`、`game_types`、`game_game_types`（程式在 `backend/app/core/games/`），以及 games_advisor 的 4 張表。向量欄位的維度讀 04 新增的 `GAMES_ADVISOR_EMBEDDING_DIM`。repository 函式不在這裡寫，跟著用到它的指令或 service 一起寫。

2026-11-12 組員在 MR #22 決定 `games.id` 改成整數（bigint）、新增時自動給號；所有 `game_id` 欄位跟著改成 bigint。沒給 `id` 時自動給號，給了就照給的寫入（同步要用，spec §8.11）。測試情境照 spec §3.8 更新。匯入、匯出、同步的改動在 06。

共用表是 AGENTS.md §4.2、§4.4 的例外（[ADR 0003](../../../docs/adr/0003-shared-games-table.md)）。2026-11-11 立倫決定不改 AGENTS.md，理由寫在這張 ticket 的 MR 說明，由組員審核時確認。

## 驗收條件

- [x] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [x] spec §3.8 的每一列都有測試而且通過
- [ ] MR 說明寫出共用表的例外與理由，連到 ADR 0003；組員同意後 ADR 0003 改成 accepted
- [x] AGENTS.md §2 第 7 點的三項檢查通過
- [x] MR @ 瑋鋐（審核 migration，AGENTS.md §4.4）
- [x] 03 的 `games.json` 提示詞在這個分支 commit
- [x] 合併前把本檔與 03 的 `Status` 改成 `resolved`、`MR` 填上連結
