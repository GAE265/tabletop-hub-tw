## Context

- 專案已有 `backend/`（FastAPI、SQLAlchemy 2 同步 session、psycopg、Alembic），`app/domains/booking/` 目前只有共用表 `BookingShop`（`booking_shops`：`id`、`name`）。`auth_users` 為共用表，欄位 `id`、`display_name`、`role`、`shop_id`，`phone` 由 `auth` 擁有者另行加入。
- 現有 migration 為 `0001_baseline`、`0002_games_tables`。本 change 的 migration 接在最新 revision 之後。
- 訂位規則來自一間實際合作店家。營業時間、桌位與費率是合作店家資料，不得提交進 repo；程式與測試只用虛構的同結構資料，真實資料由使用者自行以 DML 寫入（D12）。
- 認證（登入、JWT）由 `auth` 負責；本 change 只使用 `CurrentUser`、`get_current_user`、`require_role`（AGENTS.md §4.5），開發期間以 `X-Dev-User` 取得身分。

## Goals / Non-Goals

**Goals:**
- 提供訂位建立、批次、修改、取消、店員狀態操作的 HTTP API，並附權限檢查。
- 將所有時間、桌位、費用規則放在可單元測試的純函式，service 組合 repository 與純函式，router 保持很薄。
- 在併發下避免同一桌位重複分配。

**Non-Goals:**
- 登入、個資管理、通知、付款、國定假日。
- 跨午夜營業與跨午夜拆單。
- 點餐紀錄與飲料低消驗證。
- 前端畫面（含 `prototypes/` 與交接說明，另開 change）。
- 多店管理介面（資料表都帶 `shop_id`，但本階段只驗證單店流程）。

## Decisions

### D1：分層與目錄
依 AGENTS.md §4.1：`app/domains/booking/{router,schemas,service,repository,models}.py`。純函式（時間規則、桌位分配、費用）放在同 domain 內獨立模組：`rules.py`（時間規則）、`allocation.py`（桌位分配）、`pricing.py`（費用）。它們不 import FastAPI、SQLAlchemy，只由 `service` 呼叫。依賴方向維持 `router → service → repository → models`。

理由：規則複雜，需要大量案例測試，純函式最容易驗證。service 用手寫 `FakeBookingRepository` 做單元測試（AGENTS.md §7.5，不使用 mock 套件）。

### D2：單一 migration，所有 id 為 UUID
一個 MR 最多一個 migration（AGENTS.md §4.4），所以只建立一支 revision，內容：

- `CREATE EXTENSION IF NOT EXISTS btree_gist`
- 建立 8 張表（皆 `id uuid` 主鍵，預設 `gen_random_uuid()`）：
  - `booking_business_hours`：`shop_id`、`weekday`（0=星期日）、`open_time`、`close_time`，`UNIQUE(shop_id, weekday)`，`open_time < close_time`。
  - `booking_closing_hours`：`shop_id`、`closing_date`、`start_time`、`end_time`、`reason`；`start_time` 與 `end_time` 同為 NULL 代表整天公休。
  - `booking_tables`：`shop_id`、`table_code`（`UNIQUE(shop_id, table_code)`，種子與測試用它找資料）、`name`、`min_capacity`、`max_capacity`、`location`、`is_active`。
  - `booking_table_links`：`shop_id`、`table_a_id`、`table_b_id`、`is_combinable`；`CHECK(table_a_id <> table_b_id)`，並以 `UNIQUE(shop_id, LEAST(a,b), GREATEST(a,b))`（unique index）禁止重複與反向重複。
  - `booking_pricing_rules`：`shop_id`、`rule_code`（`UNIQUE(shop_id, rule_code)`）、`rule_name`、`rule_type`、`price`、`unit`、`description`、`is_active`、`effective_from`、`effective_to`。
  - `booking_reservations`：`shop_id`、`reservation_code`（`UNIQUE(shop_id, reservation_code)`）、`user_id`（FK `auth_users`）、`start_at`、`end_at`、`party_size`、`status`、`source`、`special_requests`、`internal_note`、`seated_at`、`completed_at`、`final_fee numeric(10,2)`、`cancelled_at`、`cancel_reason`、`created_at`、`updated_at`。`CHECK(end_at > start_at)`、`CHECK(party_size >= 1)`，`status` 與 `source` 以 CHECK 限制值（`status`：`pending/confirmed/seated/completed/cancelled/no_show`；`source`：`customer_service/phone/walk_in/online`）。
  - `booking_reservation_tables`：`reservation_id`、`table_id`、`shop_id`、`start_at`、`end_at`、`is_active`，以及 D6 的 exclusion constraint。
  - `booking_reservation_logs`：`shop_id`、`reservation_id`、`action`、`old_data jsonb`、`new_data jsonb`、`operator_type`（`customer/staff/ai/system`）、`operator_id`（uuid，可為空）、`operator_name`、`created_at`。
- 取消者沿用 `booking_reservation_logs` 的 `operator_*`，不在訂位上另加欄位。
- 寫入時 `status` 一律明確指定，不依賴預設值。

建表前先在群組告知 8 個表名（AGENTS.md §4.4）。migration 由瑋鋐審核；已合併的 migration 不得再修改。

### D3：時間一律以 `timestamptz` 儲存，以 `Asia/Taipei` 判斷
規則判斷（星期、營業時間、是否跨日、3 個日曆月）一律轉成 `Asia/Taipei` 後處理。星期以 `isoweekday() % 7` 對應 0=星期日；平日／週末費率依此判斷。API 的時間欄位使用 ISO 8601、UTC。

### D4：桌位分配演算法
1. 取出啟用桌位與目標時段內的有效訂位（`confirmed`、`seated`），依 D5 計算衝突，得到可用桌集合。
2. 單桌：篩出容量符合者，取 `max_capacity` 最小（同值取 `table_code` 小者）。
3. 多桌：桌位少（約 9 張），直接列舉大小 2 到 n 的子集合，過濾總 `max_capacity ≥ 人數`；以 `booking_table_links` 建雙向圖，判斷組合在「僅 `is_combinable=true` 邊」下是否連通（等級 1）、在「所有邊」下是否連通（等級 2）、否則等級 3。排序鍵為（等級、桌數、總 max、`table_code` 排序）。
4. 沒有候選則回報桌位不足。

替代方案：圖搜尋或整數規劃。桌數僅約 9，子集合最多 511 個，列舉簡單可驗證，故不採用複雜解法。人數很大且需要超過可用桌數時，直接判定不足。

### D5：衝突與緩衝
對每張候選桌，查詢其所屬的 `booking_reservation_tables` 與訂位（狀態為 `confirmed`/`seated`，排除正在修改的訂位）。若他筆訂位的 `user_id` 與目前不同，把其區間 `[start_at, end_at + 5 分鐘)` 當作占用；相同則為 `[start_at, end_at)`。同時，新訂位的 `end_at + 5 分鐘` 不得與他人訂位 `start_at` 重疊（同使用者則為 0）。緩衝分鐘數為 `booking` 內的常數 `BUFFER_MINUTES = 5`。

### D6：併發以資料庫約束保護
普通 UNIQUE 無法表達「同桌時段不得重疊」，因此在 `booking_reservation_tables` 使用 PostgreSQL exclusion constraint（需 `btree_gist`）：

`EXCLUDE USING gist (shop_id WITH =, table_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&) WHERE (is_active)`

`confirmed`／`seated` 的訂位其桌位列 `is_active=true`；取消、no_show、completed 時改為 `false` 以釋放桌位。訂位時間變更時，同一交易內同步更新桌位列的 `start_at/end_at`。所有寫入在單一交易內執行，違反約束（SQLAlchemy 包裝的 `psycopg.errors.ExclusionViolation`）時回滾，重新分配一次，仍失敗則回傳桌位不足。`no_show → seated` 改回時重新設 `is_active=true`，若約束違反即代表桌位已被占用，直接拒絕。

限制：約束只保護「實際時間重疊」。5 分鐘緩衝（不同使用者）因為「同使用者為 0」的例外，無法寫成約束，仍由 D5 的應用層查詢檢查；兩個不同使用者並發訂在同桌且相隔不足 5 分鐘時，約束擋不住（見風險）。
替代方案：`pg_advisory_xact_lock(shop_id)` 整店序列化，可同時涵蓋緩衝，但選擇以資料庫約束為主，故不採用。

### D7：重疊處理與合併都在同一交易
- 建立訂位遇到同電話重疊：未帶 `confirm_overlap` 就回傳重疊清單（HTTP 409，錯誤碼 `BOOKING_OVERLAP_CONFIRM_REQUIRED`，`details` 含舊訂位）；帶旗標後在交易內先取消舊訂位（釋放桌位）、再分配新訂位，失敗則整筆回復。
- 修改後與自己的訂位重疊：回傳詢問（409，`BOOKING_MERGE_CONFIRM_REQUIRED`）；`merge=true` 與新人數一起送出後，建立新訂位（區間為聯集）並取消被合併的兩筆。
- 全有或全無的批次用同一個交易，任一時段失敗即回復。
- 批次內各時段分配桌位時，已分配的前一時段要納入衝突計算。

### D8：no_show 不自動化
沒有排程，也沒有背景工作。`no_show` 只會由玩家開始後取消、或店員手動標記產生。`no_show → seated` 的修正需重新檢查原桌位衝突。

### D9：費用
讀取 `booking_pricing_rules` 的 `WEEKDAY_HOURLY_FEE`、`WEEKEND_HOURLY_FEE`、`BILLING_ROUNDING_UNIT_HOURS`、`BILLING_MAX_HOURS`、`BOOKING_MIN_HOURS`，每次請求查詢（量小，直接查詢）。計費時數 = min(ceil(分鐘數 / 60 / 單位) × 單位, 上限)。

### D10：身分與權限
- router 以 `Depends(get_current_user)` 取得 `CurrentUser`，傳給 service；service 以 `require_role` 檢查角色（AGENTS.md §4.5），不 import FastAPI。
- 玩家端：角色限 `player`、`admin`；除了 `admin`，只能讀寫 `user_id` 等於自己的訂位，否則 403。
- 店員端：角色限 `shop_staff`、`admin`；`shop_staff` 只能操作 `shop_id` 等於自己所屬店家的訂位，否則 403。`admin` 不受店家限制。
- 操作記錄：`operator_type` 為 `customer`、`staff`、`system`；`operator_id` 取 `CurrentUser.id`；`operator_name` 由 service 透過 `auth_users` 共用 repository 讀取 `display_name`。
- 訂位聯絡電話取自 `auth_users.phone`；玩家沒有電話時，建立訂位回 422（`BOOKING_PHONE_REQUIRED`）。玩家個資（姓名、電話、Email）不能透過訂位 API 修改。
- 測試使用 `conftest.py` 的 `as_player`、`as_shop_staff`、`as_admin`，不自行產生使用者或 token。

### D11：RESTful API
路徑不放動詞，動作用 HTTP 方法與子資源表達（AGENTS.md §4.3）。錯誤格式 `{"error": {"code", "message", "details"}}`；列表用 `page`、`page_size`，回 `{"items", "total"}`。

| 用途 | 端點 | 說明 |
|---|---|---|
| 預估費用 | `POST /api/v1/booking-quotes` | 不寫入，回傳場地費與週末飲料低消提醒 |
| 建立（含批次） | `POST /api/v1/bookings` | body 的 `slots` 為 1 到多個時段；全有或全無；201 |
| 我的訂位 | `GET /api/v1/bookings`、`GET /api/v1/bookings/{id}` | 玩家看自己的；分頁 |
| 修改、取消 | `PATCH /api/v1/bookings/{id}` | 改日期、時間、人數、備註（可帶 `merge`）；或 `{"status": "cancelled"}` |
| 店員改狀態 | `PATCH /api/v1/bookings/{id}` | `{"status": "seated" | "completed" | "no_show" | "cancelled"}`，依角色與狀態流轉檢查 |
| 店員改桌 | `PUT /api/v1/bookings/{id}/tables` | 整組取代桌位，需通過衝突檢查 |
| 店員看板 | `GET /api/v1/shops/{shop_id}/bookings?from=&to=` | 依日期範圍，分頁 |

錯誤碼對應：桌位被訂走或不足 409（`BOOKING_TABLE_TAKEN`、`BOOKING_NO_TABLE_AVAILABLE`）、同電話或合併需確認 409、狀態不允許 409、時間規則違反與欄位驗證 422、未登入 401、沒有權限 403、找不到 404。

### D12：真實店家資料由使用者自行以 DML 寫入
因為真實營業時間、桌位與費率屬合作店家資料，不寫進 migration、seed 或測試，也不提供匯入指令。使用者自行準備 DML 寫入 `booking_business_hours`、`booking_closing_hours`、`booking_tables`、`booking_table_links`、`booking_pricing_rules`。

- 測試用虛構資料，結構與真實配置相同（容量、相鄰、可併桌關係）。
- 費率至少需要 `WEEKDAY_HOURLY_FEE` 與 `WEEKEND_HOURLY_FEE`，缺少時回 503。
- 資料內容只存在資料庫，不得出現在 repo 與 MR 說明。

## Risks / Trade-offs

- [緩衝期間在並發下可能被突破：約束不含 5 分鐘緩衝] → 不同使用者、同桌、相隔小於 5 分鐘且完全同時送出才會發生，機率很低，店員可改桌補救；若不能接受，改為加 `pg_advisory_xact_lock`。
- [`booking_reservation_tables` 時間欄位是冗餘資料，修改時間漏同步會造成誤判] → 所有時間變更集中於同一個 repository 函式，並以整合測試覆蓋。
- [`auth_users.phone` 若不唯一，同電話重疊（以電話判斷）與緩衝（以 `user_id` 判斷）可能不一致] → 請 `auth` 擁有者決定電話是否唯一；本 change 在 spec 註明依賴。
- [依賴另一個 MR 的 `auth_users.phone`] → 兩個 MR 的 migration 需串接，需先與立倫協調順序；`booking` migration 的 `down_revision` 以合併後的最新 revision 為準。
- [單一 migration 一次建 8 張表，審核量大] → 以整合測試驗證所有約束，審核者可對照測試。

## Migration Plan

1. 與立倫確認 `auth_users.phone` 的 MR 與順序；群組告知 8 個表名。
2. 先寫 migration 測試（表、約束、exclusion constraint 存在且生效），再寫 revision。
3. 以 `uv run alembic upgrade head` 套用，並驗證 `downgrade` 可回復（刪除 8 張表；`btree_gist` extension 保留）。
4. 使用者自行以 DML 寫入店家設定資料，供手動驗證。

## Open Questions

- `auth_users.phone` 是否唯一、是否必填（影響同電話規則）。
- 店員看板是否需要更多篩選（狀態、桌位）？目前只做日期範圍。
- 前端畫面（`prototypes/booking/` 與 `docs/handoff/booking.md`）是否另開 change？
