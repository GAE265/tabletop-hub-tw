## Why

平台的 `booking` domain（#6 訂位與客服）目前只有共用資料表 `booking_shops`，沒有任何可建立、修改、取消訂位的服務，也沒有自動分配桌位與預估費用的能力。第一階段需要訂位後端，讓玩家自助訂位、店員可調整與結算。

## What Changes

- 在既有 `backend/` 新增 `app/domains/booking/`（router、schemas、service、repository、models），依 AGENTS.md §4 的分層與 RESTful 規則實作。
- 新增 Alembic migration（單一 revision，瑋鋐審核），建立 8 張訂位相關資料表：`booking_business_hours`、`booking_closing_hours`、`booking_tables`、`booking_table_links`、`booking_pricing_rules`、`booking_reservations`、`booking_reservation_tables`、`booking_reservation_logs`。主鍵一律 UUID，店家使用既有共用表 `booking_shops`，使用者使用共用表 `auth_users`。
- `booking_reservation_tables` 帶 `start_at`、`end_at`、`is_active` 與 `btree_gist` exclusion constraint，作為併發防重複訂桌的資料庫保護。
- 新增訂位建立、多時段批次建立（全有或全無）、修改、取消 API。
- 新增營業時間、公休時段、單日不跨日、最長提前 3 個日曆月、不得早於現在等驗證。
- 新增自動桌位分配：單桌優先，必要時多桌合併（`booking_table_links` 的相鄰與可併桌關係）。
- 新增同電話時段重疊的處理：提醒後由玩家確認，確認後取消舊訂位並建立新訂位。
- 修改訂位與自己其他訂位重疊時，合併成一筆涵蓋兩者時間的新訂位。
- 新增預估費用計算（平日 60、假日 80，每人每小時，進位至小時，上限 5 小時）。
- 新增店員操作：標記入座、完成（含結算費用）、取消、手動標記 no_show、修改桌位。
- 新增權限：玩家只能操作自己的訂位；店員只能操作自己所屬店家的訂位；每個端點附「沒有權限」測試。
- 新增 booking 的匯入指令：從 `.env` 的 `BOOKING_SOURCE_DATABASE_URL` 指向的來源資料庫，匯入營業時間、公休、桌位、關係與費率規則。真實店家資料不提交進 repo（AGENTS.md §2 規則 2）。
- 前置依賴：`auth_users` 需要 `phone` 欄位（同電話重疊規則使用）。由 `auth` 擁有者（立倫）以另一個 MR 與 migration 提供，本 change 不修改 `auth_users`。
- 不含：Google OAuth、登入（`auth` domain 負責）、個資管理、付款、通知、國定假日、跨午夜營業、點餐與飲料低消驗證（由店員核對）、前端畫面。

## Capabilities

### New Capabilities
- `booking-rules`: 訂位時間規則驗證（營業日與時段、公休時段、不跨日、最短時數、提前上限、不得早於現在）、多時段批次、同電話重疊處理。
- `table-allocation`: 自動桌位分配（單桌、多桌合併等級排序）、桌位衝突與緩衝（同使用者 0 分鐘，其他 5 分鐘）、併發保護、店員改桌。
- `reservation-lifecycle`: 狀態流轉（confirmed、seated、completed、cancelled、no_show）、取消規則、修改與合併、操作記錄、角色與擁有者權限。
- `reservation-pricing`: 預估費用與結算費用計算、平假日判斷、週末飲料低消提示。

### Modified Capabilities
<!-- 專案尚無既有 spec -->

## Impact

- 後端：新增 `backend/app/domains/booking/`、`backend/migrations/versions/` 一支 migration、`backend/tests/booking/`、`backend/tests/migrations/`；`app/main.py` 掛載 booking router。
- 資料庫：新增上述 8 張表，並啟用 `btree_gist` extension。共用表 `booking_shops`（瑋鋐擁有）與 `auth_users`（立倫擁有）只被參照，不修改結構。
- 依賴 `auth_users.phone`（立倫的 MR）。在它合併前，本 change 的 migration 與同電話測試無法完成。
- 設定：`.env.example` 新增 `BOOKING_SOURCE_DATABASE_URL`（只寫欄位名與說明）。
- 不新增第三方套件（fastapi、sqlalchemy、psycopg、alembic 皆已存在）。
