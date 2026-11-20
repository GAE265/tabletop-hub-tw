# Design

## Context

- 訂位建立時就是 `confirmed`（`BookingService.create`），沒有「待店家確認」的步驟，所以「訂位成功」＝建立成功。
- 揪團通知（`add-groups-notifications`）已經有一套做法：通知表只存種類與對象，文字由前端組；同一個交易寫入；`GET` 附 `unread_count`、`PATCH {"read": true}`；前端每 60 秒查一次未讀數。
- 訂位的時間、狀態都在 `reservations`；已入座是 `seated`，結束時間是 `end_at`。

## Goals / Non-Goals

**Goals**：訂位成功時通知玩家與店家人員；鈴鐺與通知頁同時看得到揪團與訂位通知；店家看板看得出哪些客人超時。

**Non-Goals**：共用的通知表、訂位修改／取消的通知、超時的通知紀錄、推播。

## Decisions

### D1：booking 自己一張 `booking_notifications`，不和揪團共用

和 `groups_notifications` 同樣的欄位，只把 `group_id` 換成 `reservation_id`（外鍵指向 `reservations.id`，訂位不會被刪除，用 `RESTRICT` 與其他訂位表一致）。
- 共用一張表要新增共用資料表、決定擁有者、改 AGENTS.md 的清單，也要改已經合併的揪團通知；兩個 domain 各一張表，彼此不需要知道對方。
- 代價是前端要查兩次未讀數，見 D4。

### D2：兩種通知種類，文字由前端依種類組成

- `booking_confirmed`（給訂位的玩家）：「你在「店名」的訂位已成功」。
- `shop_new_booking`（給該店的店家人員）：「新訂位：11/22（日）19:00・4 人」。
- 同一則訂位給不同人看的意思不同，用種類區分，前端不必判斷目前使用者的角色。
- 揪團通知會排除「做這個動作的人」；訂位成功的通知刻意發給訂位的玩家本人，讓他在鈴鐺裡留有紀錄（使用者決定）。

### D3：同一個交易寫入；收件人在交易裡查

在 `create` 的 `work()` 裡，建立訂位之後查該店的店家人員（`role = 'shop_staff' AND shop_id = 店家`），一起寫入通知。訂位因桌位衝突重做時，通知也跟著重做，不會多寫。

### D4：前端：鈴鐺加總、通知頁兩個分頁、放在 `app/notifications/`

- `booking/state` 新增 `bookingUnreadCountProvider`，與 `groupUnreadCountProvider` 一樣每 60 秒查一次（共用 `notificationPollIntervalProvider`）。
- 鈴鐺顯示兩者相加；兩邊都查詢失敗時不顯示數字，只有一邊失敗時顯示另一邊的數字。
- 通知頁 `/notifications`：「揪團」「訂位」兩個分頁，分頁標題各自顯示未讀數。只有訂位有未讀時，預設開「訂位」分頁，其他情況開「揪團」。
- `groups` 的通知列表改成不含 Scaffold 的 `GroupNotificationsList`，`booking` 新增 `BookingNotificationsList`；`app/notifications/` 把兩者組成一頁。這樣 `groups` 與 `booking` 互不 import。
- 點訂位通知：`booking_confirmed` 前往「我的訂位」`/booking/mine`，`shop_new_booking` 前往「店家看板」`/booking/board`。

### D5：超時在前端即時算

`overtimeMinutes(status, endAt, now)`：狀態是 `seated` 且現在已超過結束時間至少 1 分鐘時，回傳超過的分鐘數，否則為 null。
- 看板已經有訂位的狀態與結束時間，不需要新的 API。
- 「現在」由 `bookingClockProvider` 提供，測試可以固定時間。
- 店家看板每分鐘重新計算一次（只重畫，不重新查詢 API）。
- 座位圖新增「已超時」的顏色與圖例，只在店家看板出現。

## Risks / Trade-offs

- 店家看板不會自動重新查詢，別的店員把客人辦離店後，要按重新整理才會消失。之後要自動更新可以另外做。
- 兩張通知表、兩次查詢：未讀數每 60 秒多一次請求，量很小。
- `groups-notifications-page` 的要求被改掉，要等 `add-groups-notifications` 封存後再封存本 change。
