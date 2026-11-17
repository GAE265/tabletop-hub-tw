# Proposal

## Why

手動測試開團時發現兩個問題：

1. **店家要手動輸入 UUID**：開團表單的店家下拉選單只列「當月揪團出現過的店家」，月份沒有揪團時是空的，只能在文字欄輸入店家 ID。一般玩家不可能知道 UUID，填錯後端只回「請求欄位驗證失敗」。
2. **遊戲只能填一個，而且要輸入數字 ID**：一場揪團常常會玩好幾款遊戲，但目前 `groups.game_id` 只能存一款，表單也要手動輸入遊戲編號。

本 change 讓開團表單的店家改成從 `booking_shops` 讀取的下拉選單，遊戲改成可以搜尋、可以複選的下拉選單，並讓一個揪團可以有多款遊戲。

## What Changes

- **新增遊戲清單 API** `GET /api/v1/games`：依中文或英文名稱搜尋（`q`），分頁。讀取共用表 `games`（擁有者立倫），程式放在 `backend/app/core/games/`，MR 要 @ 立倫。
- **揪團可以選多款遊戲（契約變更）**：
  - 新增對應表 `group_games`（揪團 ↔ 遊戲），移除 `groups.game_id`；migration 會把既有的 `game_id` 搬到新表。
  - API：請求的 `game_id` 改成 `game_ids`（整數陣列，可以是空陣列，不限數量）；回應的 `game` 改成 `games`（陣列）。**這是不相容的變更**，前端在同一個 change 一起更新。
- **開團表單**：
  - 店家：下拉選單，選項來自 `GET /api/v1/shops`（`booking` 的 API，在 #39，瑋鋐負責）。移除「或輸入店家 ID」欄位。
  - 遊戲：可以輸入關鍵字搜尋、可以複選的下拉選單，選好的遊戲以標籤顯示、可以移除。移除「遊戲 ID」欄位。
  - 揪團卡片與詳細頁顯示多款遊戲。
- **不做**：在後端新增店家 API（使用 #39 的 `GET /api/v1/shops`）、依遊戲篩選月曆、遊戲的圖片。

## Capabilities

### New Capabilities
- `games-list`：遊戲清單與搜尋 API。

### Modified Capabilities
- `groups`（`add-groups-calendar`）：揪團的遊戲由單選改為複選；資料表新增 `group_games`、移除 `groups.game_id`。
- `groups-calendar-page`（`add-groups-calendar`）：開團表單的店家與遊戲改成下拉選單；卡片與詳細頁顯示多款遊戲。

## Impact

- **受影響 domain**：`groups`（主責永傑）。
- **共用資料表**：
  - `games`（擁有者立倫）：只讀。新增讀取 API 與 repository 的搜尋方法，放在 `backend/app/core/games/`（立倫的共用區），MR 要 @ 立倫。
  - `booking_shops`（擁有者瑋鋐）：前端透過 #39 的 `GET /api/v1/shops` 讀取，不改結構。
- **依賴**：店家下拉選單需要 #39 合併後才能在瀏覽器實際使用；在那之前，前端照 #39 的格式（`items`：`id`、`name`）實作，測試用 fake。
- **契約**：有改動（新增 `GET /api/v1/games`；`groups` 的 `game_id` → `game_ids`、`game` → `games`），要 @ 立倫。
- **migration**：一個（新增 `group_games`、搬資料、移除 `groups.game_id`），要 @ 瑋鋐。新表名 `group_games` 要先在群組告知（4.4）。新表與欄位依 AGENTS.md 1.10 寫中文 `comment=`。
- **migration 編號**：`dev` 目前到 `0004`；#39 修正後也會用 `0005`，後合併的一方要改號。
- **前端**：不新增套件（搜尋複選用 Flutter 內建的 `Autocomplete` 與 `InputChip`）。
- **不修改** `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。
