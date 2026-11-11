---
status: proposed
---

# 桌遊基本資料改成所有 domain 共用的 `games` 表

規則書入庫（`rules_ingest`，8 大類各一款）、規則問答、戰績等功能都會提到同一批桌遊，需要統一的桌遊編號與名稱。因此桌遊的基本資料（`games`）、8 個類型（`game_types`）與每款桌遊的類型（`game_game_types`）改成所有 domain 共用的表：表名不用 domain 名稱開頭，所有 domain 都可以直接查詢，`games.id` 用 "1"、"2"、"3"…… 由立倫指定的字串編號。這三點都和 AGENTS.md §4.2、§4.4 有出入；立倫在 2026-11-11 決定以例外處理，不改 AGENTS.md，理由寫在建立資料表的 MR 說明，由組員在 MR 審核時確認，確認後本檔改成 accepted。這也推翻了 games_advisor 原本「桌遊資料只供推薦，不給其他 domain 參照」的決定。

## Considered Options

- **歸 games_advisor 管（`games_advisor_games`），其他 domain 呼叫它的 service**：符合 AGENTS.md，但每個 domain 要對齊桌遊編號都得多一層 service 呼叫，而且類型查不到。
- **主鍵維持 UUID，另加一個數字編號欄位**：符合 §4.4，但組員溝通、寫測試資料時用的是 "1"、"2" 這種編號，兩套 ID 容易混用。

## Consequences

- 共用表由立倫負責，程式放在 `backend/app/core/games/`（資料表定義與唯讀查詢）；只有 games_advisor 的匯入指令寫入。其他 domain 改這三張表要 @ 立倫。
- 編號給出去就不改、不重複使用；`games.json` 不帶編號，匯入時另給編號對應檔。字串排序 "10" 會排在 "2" 前面，照編號排序時要轉成數字。
- 只有推薦用到的資料（心得摘要、標籤、心得片段）留在 games_advisor 自己的表，`game_id` 參照 `games.id`；心得摘要因此從桌遊表搬到 `games_advisor_review_summaries`。
- 瑋鋐審 migration 時會看到不是 UUID 的主鍵、沒有 domain 開頭的表名，MR 說明要指向本檔。
- 其他 domain 直接依賴這三張表的欄位，之後改欄位名稱或刪欄位，要先確認沒有 domain 在用。
