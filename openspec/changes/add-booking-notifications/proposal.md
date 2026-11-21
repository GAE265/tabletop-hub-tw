# Proposal

## Why

`add-groups-notifications` 做了揪團的站內通知，但訂位發生的事情目前沒有人會被通知：
- 玩家訂位成功後，只有當下畫面的提示，之後在鈴鐺裡找不到紀錄。
- 店家人員不知道有新訂位，要自己打開店家看板才看得到。
- 客人過了結束時間還沒離開（已入座、還沒離店結帳），店家看板上看不出來，店家人員要自己對時間。

這些在 `add-groups-notifications` 列為不做、留給 `booking`；booking 主責瑋鋐已同意由永傑來做。

## What Changes

- **訂位成功通知**：玩家建立訂位成功時（訂位一建立就是已確認），在同一個交易裡寫入通知：
  - `booking_confirmed`：給訂位的玩家。
  - `shop_new_booking`：給該店每一位店家人員（`auth_users.role = 'shop_staff'` 且 `shop_id` 相同）。
  - 訂位失敗（桌位不足、欄位錯誤等）時不寫入任何通知。
- **訂位通知 API**（只看得到自己的通知，格式與揪團通知相同）：
  - `GET /api/v1/booking-notifications`：新的在前，分頁，附 `unread_count`。
  - `PATCH /api/v1/booking-notifications/{notification_id}`：body `{"read": true}` 標成已讀。
- 新增資料表 `booking_notifications`（migration `0014`）。
- **前端**：
  - 鈴鐺的數字改成揪團與訂位的未讀數相加。
  - 通知頁改成 `/notifications`，分「揪團」「訂位」兩個分頁；原本的 `/groups/notifications` 移除。
  - 鈴鐺與通知頁移到 `frontend/lib/app/notifications/`（同時用到兩個 domain）。
  - 店家看板：已入座且超過結束時間的訂位，訂位卡顯示「已超時 N 分鐘」，座位圖上的桌子改用醒目的顏色；看板每分鐘重新計算。客人超時是查詢時即時算的，不寫入通知，也不改後端。
- **不做**：
  - 訂位修改、取消、未出席的通知。
  - 客人超時的通知紀錄、跳出提示（只在店家看板標示）。
  - Email、瀏覽器推播、全部標成已讀。

## Capabilities

### New Capabilities
- `booking-notifications`：訂位成功時產生通知，以及訂位通知的查詢、標成已讀與權限（後端）。
- `notifications-page`：合併的通知鈴鐺與分成兩個分頁的通知頁 `/notifications`（前端）。
- `booking-board-overtime`：店家看板上標示超時的訂位（前端）。

### Modified Capabilities
- `groups-notifications-page`：「通知鈴鐺」與「通知列表頁」改由 `notifications-page` 取代，鈴鐺不再前往 `/groups/notifications`。此能力目前在 `add-groups-notifications` 中（還沒封存），本 change 要在它封存之後再封存。

## Impact

- **受影響 domain**：`booking`（主責瑋鋐，已同意由永傑做）、`groups`（永傑）。
- **契約變更**（MR 要 @ 立倫）：新增兩個 `booking-notifications` 端點。既有的訂位 API 回應不變。
- **Migration**（MR 要 @ 瑋鋐）：`0014`，新增 `booking_notifications` 表，每個欄位都有中文說明。
- **建表前**：在群組先說表名 `booking_notifications`（AGENTS.md 4.4）。
- **共用資料表**：外鍵參照 `auth_users`、`reservations`；在 booking 的 repository 查詢某店的店家人員（讀 `auth_users`，booking 的 repository 已經這樣讀使用者資料），不改結構，MR @ 立倫。
- **前端共用區** `frontend/lib/app/`：擁有者是永傑本人。
- **既有測試要改**：通知頁網址與元件名稱改變，`groups` 通知頁、導覽列、路由的測試要跟著改，MR 說明會寫出原因。
- **交接說明**：更新 `docs/handoff/groups.md`、`docs/handoff/booking.md`（若存在）。
