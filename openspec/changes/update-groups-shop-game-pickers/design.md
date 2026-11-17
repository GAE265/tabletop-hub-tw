# Design

## Context

- `groups.game_id`（單一、可為空，參照 `games.id`，遊戲刪除時設為空值）是 `add-groups-calendar` 的設計；揪團 API 的請求用 `game_id`、回應用 `game`。
- `games` 是共用表（擁有者立倫），model 與 `GameRepository` 在 `backend/app/core/games/`；目前沒有任何對外的遊戲清單 API。`games.id` 是 bigint（ADR 0003）。
- 店家：`booking_shops` 是共用表（擁有者瑋鋐）。#39 新增了 `GET /api/v1/shops`，回應 `{"items": [{"id", "name"}], "total"}`，尚未合併。
- 前端開團表單目前的店家下拉選單只列當月揪團出現過的店家，另有「或輸入店家 ID」與「遊戲 ID（選填）」兩個文字欄位。
- 使用者決定：店家用 #39 的 API；遊戲清單 API 由永傑新增並 @ 立倫；一個揪團的遊戲數量不限制。

## Goals / Non-Goals

**Goals:**
- 玩家開團時不必知道任何 ID。
- 一個揪團可以有多款遊戲，順序依選擇的順序。

**Non-Goals:**
- 在 groups 另做店家 API。
- 依遊戲篩選月曆、遊戲圖片、遊戲詳細資訊。

## Decisions

**D1 對應表 `group_games`，移除 `groups.game_id`。**
欄位：`group_id`（uuid，參照 `groups.id`，ON DELETE CASCADE）、`game_id`（bigint，參照 `games.id`，ON DELETE CASCADE）、`position`（integer，從 1 開始，選擇的順序），主鍵 (`group_id`, `game_id`)。每個欄位依 AGENTS.md 1.10 寫中文 `comment`。
- 遊戲被刪除時只刪掉「對應」，揪團保留，這與原本 `game_id` 設為空值的意義相同；ADR 0003 禁止的是「資料本身跟著桌遊被刪掉」，對應列不屬於此限。
- 替代方案：`groups.game_ids bigint[]`。被否決：陣列無法設外鍵，遊戲刪除時不會自動處理，也不能用 JOIN 取得名稱。
- 只有一個 migration：建立 `group_games` → 搬移 `game_id` 不為空的資料（position=1）→ 移除 `groups.game_id`。降級反向，取 position 最小的遊戲放回。

**D2 API 契約：`game_ids`／`games`，不相容變更。**
- 請求：`game_ids: list[int]`，預設空陣列；有重複回 422；有不存在的遊戲回 404 `GROUP_GAME_NOT_FOUND`（沿用既有的錯誤代碼），`details.game_ids` 列出不存在的編號，整筆不寫入。
- 回應：`games: [{id, name}]`，依 `position` 排序。
- `PATCH`：帶 `game_ids` 時整份取代（先刪後加，同一個交易）；不帶時不動。
- 列表查詢：先查出一頁揪團，再用一次查詢取得這些揪團的遊戲（`WHERE group_id IN (...)`），避免 JOIN 造成分頁筆數錯誤或 N+1。
- 前端只有本專案自己用，所以不保留舊欄位做相容；前端在同一個 change 一起更新。

**D3 遊戲清單 API 放在 `backend/app/core/games/`。**
`games` 的 model 與 repository 已在 `core/games/`（ADR 0003），新增 `service.py`（分頁參數、組回應）與 `router.py`，在 `main.py` 掛載；`GameRepository` 新增 `search_games(q, offset, limit) -> (rows, total)`。這是立倫的共用區，MR 要 @ 立倫。
- 替代方案：放在 `games_advisor` domain。被否決：遊戲清單是所有功能共用的，不屬於推薦 Agent。
- 搜尋用 `ILIKE '%q%'` 比對 `name` 與 `english_name`；`q` 中的 `%`、`_` 要跳脫。目前 16 款遊戲，不需要全文檢索或索引。

**D4 前端：店家下拉選單。**
- `groups/data/` 新增 `ShopOption`（`id`、`name`）與 `GroupsRepository.listShops()`（呼叫 `GET /api/v1/shops`）；`groups/state/` 新增 `shopOptionsProvider`（失敗不自動重試，交給「重試」按鈕）。
- 刪除 `knownShopsProvider`（從當月揪團推出店家的暫時做法）與「或輸入店家 ID」欄位。
- 前端不 import `booking` domain 的程式；groups 只需要 `id`、`name`，自己定義 DTO。

**D5 前端：可搜尋的遊戲複選。**
- 用 Flutter 內建的 `Autocomplete` 做搜尋輸入與結果清單，已選的遊戲用 `InputChip`（可以刪除）顯示在下方；不新增套件。
- `groups/data/` 新增 `GameOption`（`id`、`name`）與 `GroupsRepository.searchGames(q)`；`groups/state/` 的表單資料 `GroupFormData` 改成 `games: List<GameOption>`，送出時轉成 `game_ids`。
- 搜尋在輸入停止 300 毫秒後才呼叫 API（debounce），避免每打一個字就查一次；結果排除已選的遊戲。
- 驗證：`validateGroupForm` 移除「遊戲 ID 要是整數」；店家改為檢查有沒有選。

**D6 前端：顯示多款遊戲。**
`Group` DTO 的 `game` 改成 `games`；揪團卡片、詳細頁每款遊戲一個 `PillBadge`。

## Risks / Trade-offs

- **[依賴 #39]** `GET /api/v1/shops` 還沒合併。→ 前端照 #39 的格式先做，測試用 fake；#39 合併前，瀏覽器裡的店家下拉選單會載入失敗（顯示錯誤與重試）。
- **[不相容的契約變更]** `game_id`／`game` 改名後，舊版前端無法開團。→ 後端與前端分兩個 MR 時，後端 MR 合併到前端 MR 合併之間，`dev` 的開團表單會壞掉。為了避免，**後端與前端的揪團變更放在同一個 MR**（遊戲清單 API 可以先獨立合併）。
- **[migration 編號]** 與 #39 都可能用 `0005`。→ 後合併的一方改號。
- **[不限遊戲數量]** 極端情況下一個揪團可以選很多遊戲。→ 依使用者決定不限制；卡片上的標籤會換行，不影響版面。

## Open Questions

1. 新表名 `group_games` 要在群組告知（4.4）。
