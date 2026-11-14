# Proposal

## Why

功能 #7「揪團與候補」目前完全沒有實作。玩家需要一個地方看到「哪一天、哪間店有人揪團、還剩幾個位子」，並且能自己開團、報名、額滿時排候補，有人退出時自動遞補。

畫面參考 globalpickleballmeetup.com 的團主揪團月曆：月曆上每天顯示有幾團，點一天就列出當天的揪團（時段、名稱、場地、團主、費用、剩幾位），並可依團主篩選。參考網頁沒有的報名、候補、退出流程，由本 change 補上。

## What Changes

- 新增 `groups` domain 的後端 API：
  - `POST /api/v1/groups`：開團，開團主自動成為第一位成員。
  - `GET /api/v1/groups`：依開始時間區間、店家、開團主篩選，分頁。預設不列出已取消的揪團。
  - `GET /api/v1/groups/{group_id}`：揪團詳細資料。
  - `PATCH /api/v1/groups/{group_id}`：開團主（或 admin）修改欄位，或以 `{"status": "cancelled"}` 取消揪團。
  - `GET /api/v1/groups/{group_id}/members`：成員與候補名單。
  - `POST /api/v1/groups/{group_id}/members`：報名。有名額時成為成員；額滿時同樣回 201，`status=waitlisted` 並附候補順位。
  - `DELETE /api/v1/groups/{group_id}/members/{user_id}`：退出，或由開團主移除成員；成員離開後，候補第一位自動遞補。
- 新增兩張資料表 `groups`、`group_members`（一個 migration）。
- 新增前端 `frontend/lib/domains/groups/`：`data/`、`state/`、`prototypes/groups/` 參考畫面、`pages/` 正式月曆頁，以及交接說明 `docs/handoff/groups.md`。
- **不做**：地區篩選（`booking_shops` 沒有地區欄位，留待瑋鋐加上後再做）、遞補時的通知、揪團 Agent（AI 協助配對），以及費用的付款或退費。

## Capabilities

### New Capabilities
- `groups`：揪團與候補的後端行為（開團、查詢、修改與取消、報名、候補、退出與遞補、權限）。
- `groups-calendar-page`：前端揪團月曆（月曆團數、當日列表、團主篩選、開團表單、報名／候補／退出操作與各種狀態）。

### Modified Capabilities
無。

## Impact

- **受影響 domain**：`groups`（主責永傑，協助立倫）。
- **共用資料表**（AGENTS.md 第 3 節）：只讀取，不改結構。
  - `booking_shops`（擁有者瑋鋐）：外鍵 `groups.shop_id`；讀取店名。
  - `auth_users`（擁有者立倫）：外鍵 `groups.organizer_id`、`group_members.user_id`；讀取 `display_name`。
  - `games`（擁有者立倫）：選填外鍵 `groups.game_id`（`bigint`）；讀取遊戲名稱。
  - 目前 `booking_shops`、`auth_users` 沒有 repository，`GameRepository` 也沒有依 id 查詢的方法。依 4.2「每張表只對應一個 repository」，需要請擁有者提供讀取方法（見 design.md D7）。這部分會動到共用區，MR 要 @ 瑋鋐、立倫。
- **前端開團表單需要店家清單**：目前沒有 `GET /api/v1/shops`（屬於 `booking`，瑋鋐負責）。見 design.md D8。
- **契約**：有改動，新增上列 API（要 @ 立倫）。
- **migration**：一個，新增 `groups`、`group_members`（要 @ 瑋鋐）。建表前先在群組告知表名（4.4）。
- **前端**：新增路由 `/groups`（正式頁）與 `/proto/groups`（參考畫面）。修改 `frontend/lib/app/router.dart`，該檔屬於永傑的共用區，主責本人修改。
- **不修改** `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。
