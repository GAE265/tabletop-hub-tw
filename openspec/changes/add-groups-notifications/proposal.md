# Proposal

## Why

揪團目前只有報名、候補與遞補，但發生變化時玩家不會知道：
- 開團主決定「人夠了、確定要辦」，成員不知道可以排時間了。
- 開團主取消揪團（解散），成員和候補要自己點進去才發現。
- 有人退出後候補自動遞補成成員，被遞補的玩家不知道自己有位子了。

`add-groups-calendar` 當時把「遞補時的通知」列為不做。本 change 補上揪團的站內通知：導覽列有通知鈴鐺與未讀數，點開看通知列表，點一則就跳到那個揪團。

## What Changes

- **確定成團**（新行為）：開團主（或 admin）在開放中、還沒結束的揪團按「確定成團」。
  - `PATCH /api/v1/groups/{group_id}` 新增可帶 `{"confirmed": true}`。
  - `groups` 新增欄位 `confirmed_at`（空值代表還沒確定成團），揪團資料回應新增 `confirmed_at`。
  - 成團後仍可報名、候補、退出，也仍可取消（取消就是解散）。
- **三種通知**，在同一個交易裡寫入，失敗就整筆不成立：
  - `group_confirmed`（成團）：通知所有成員，不含按下確定的人。
  - `group_cancelled`（解散）：通知所有成員與候補，不含按下取消的人。
  - `waitlist_promoted`（候補正取）：通知被遞補成成員的玩家。成員退出、被移除，或開團主調高人數上限時都會發生。
- **通知 API**（只看得到自己的通知）：
  - `GET /api/v1/group-notifications`：自己的通知，新的在前，分頁，附 `unread_count`。
  - `PATCH /api/v1/group-notifications/{notification_id}`：body `{"read": true}` 標成已讀。
- 新增資料表 `groups_notifications`，與 `groups.confirmed_at` 放在同一個 migration。
- **前端**（和後端放在同一個 MR）：
  - 導覽列加通知鈴鐺與未讀數，進入頁面與每 60 秒重新查詢。
  - 通知列表頁 `/groups/notifications`：點一則就標成已讀，並跳到揪團詳細頁。
  - 揪團詳細頁：開團主看到「確定成團」，已成團的揪團顯示「已成團」。
  - 揪團卡片：已成團的揪團顯示「已成團」。
- **不做**：
  - 店家通知（訂位成功、客人超過結束時間還沒離開），屬於 `booking`，留給瑋鋐。
  - Email、瀏覽器推播。
  - 取消成團、刪除通知、全部標成已讀。
  - 揪團內容修改（時間、地點）的通知。

## Capabilities

### New Capabilities
- `groups-notifications`：確定成團，以及成團、解散、候補正取三種通知的產生、查詢、標成已讀與權限（後端）。
- `groups-notifications-page`：通知鈴鐺、通知列表頁、「確定成團」按鈕與「已成團」標示（前端）。

### Modified Capabilities
無。`add-groups-calendar` 還沒封存，主規格中還沒有 `groups`；本 change 只新增行為，不改它已定義的情境。

## Impact

- **受影響 domain**：`groups`（主責永傑，協助立倫）。全部寫在 `groups` 裡，不新增 domain。
- **契約變更**（MR 要 @ 立倫）：
  - `GroupResponse` 新增 `confirmed_at`。
  - `GroupUpdate` 新增 `confirmed`。
  - 新增兩個 `group-notifications` 端點。
- **Migration**（MR 要 @ 瑋鋐）：`0013`，新增 `groups.confirmed_at` 與 `groups_notifications` 表，每個欄位都有中文說明。
- **建表前**：在群組先說表名 `groups_notifications`（AGENTS.md 4.4）。
- **共用資料表**：只用外鍵參照 `auth_users`，不改結構。
- **前端共用區** `frontend/lib/app/`（導覽列）：擁有者是永傑本人，照一般 MR 流程。
- **交接說明**：更新 `docs/handoff/groups.md`。
