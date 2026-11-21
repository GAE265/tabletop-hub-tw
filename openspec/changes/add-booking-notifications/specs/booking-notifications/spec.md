# Spec Delta

## Purpose

訂位成功時通知訂位的玩家與該店的店家人員，並提供查詢與標成已讀的 API（後端）。

## ADDED Requirements

### Requirement: 訂位成功時產生通知
玩家（或管理員）以 `POST /api/v1/bookings` 建立訂位成功時，系統 SHALL 在同一個交易裡寫入：
- 一則 `booking_confirmed` 給訂位的使用者。
- 每位該店店家人員（`role = 'shop_staff'` 且 `shop_id` 等於訂位的店家）各一則 `shop_new_booking`。

建立失敗時 MUST NOT 寫入任何通知。其他店家的店家人員 MUST NOT 收到通知。

#### Scenario: 訂位成功
- **WHEN** 玩家在「測試店」建立訂位成功
- **THEN** 玩家有一則 `booking_confirmed`，「測試店」的每位店家人員各有一則 `shop_new_booking`，都指向這筆訂位

#### Scenario: 別家店的人員
- **WHEN** 玩家在「測試店」建立訂位成功
- **THEN** 「別家店」的店家人員沒有任何通知

#### Scenario: 訂位失敗
- **WHEN** 建立訂位回 409（桌位不足）或 422（欄位錯誤）
- **THEN** 沒有寫入任何通知

### Requirement: 查詢自己的訂位通知
`GET /api/v1/booking-notifications?page=&page_size=` SHALL 只回傳目前使用者的通知，新的在前，格式為 `{"items": [...], "total": N, "unread_count": M}`。`unread_count` 是全部未讀數，不受分頁影響。每則包含 `id`、`type`、`booking`（`id`、`reservation_code`、`shop_name`、`start_at`、`end_at`、`party_size`）、`read_at`（null 代表未讀）、`created_at`。

#### Scenario: 列出通知
- **WHEN** 玩家有兩則通知，一則已讀
- **THEN** 回 200，新的在前，`total=2`、`unread_count=1`

#### Scenario: 看不到別人的通知
- **WHEN** 另一位玩家查詢
- **THEN** 回 200，`items` 為空

#### Scenario: 分頁
- **WHEN** 有 3 則通知，`page_size=2&page=2`
- **THEN** 回 1 則，`total=3`

#### Scenario: 未登入
- **WHEN** `AUTH_MODE=jwt` 且沒帶 token
- **THEN** 回 401

### Requirement: 標成已讀
`PATCH /api/v1/booking-notifications/{notification_id}`，body `{"read": true}`，SHALL 把自己的通知標成已讀並回傳該則通知。已讀的再標一次，`read_at` 不變。別人的通知或不存在的 id MUST 回 404 `BOOKING_NOTIFICATION_NOT_FOUND`。body 不是 `{"read": true}` 時回 422。

#### Scenario: 標成已讀
- **WHEN** 對自己的未讀通知送 `{"read": true}`
- **THEN** 回 200，`read_at` 有值，之後查詢 `unread_count` 少 1

#### Scenario: 重複標成已讀
- **WHEN** 對已讀的通知再送一次
- **THEN** 回 200，`read_at` 和第一次相同

#### Scenario: 別人的通知
- **WHEN** 對別人的通知送 `PATCH`
- **THEN** 回 404 `BOOKING_NOTIFICATION_NOT_FOUND`，該通知維持未讀

#### Scenario: 格式錯誤
- **WHEN** body 是 `{"read": false}`
- **THEN** 回 422

### Requirement: 訂位通知資料表
資料表 `booking_notifications` SHALL 以 migration `0014` 建立：`id`（UUID）、`user_id`（外鍵 `auth_users`）、`reservation_id`（外鍵 `reservations`）、`type`（只允許 `booking_confirmed`、`shop_new_booking`）、`read_at`（空值代表未讀）、`created_at`。資料表與每個欄位 MUST 有中文說明。降版 MUST 完整移除。

#### Scenario: 中文說明
- **WHEN** 升級到 `0014`
- **THEN** 資料表與每個欄位都有中文說明

#### Scenario: 種類限制
- **WHEN** 寫入未定義的 `type`
- **THEN** 資料庫拒絕

#### Scenario: 降版
- **WHEN** 從 `0014` 降到 `0013`
- **THEN** `booking_notifications` 不存在
