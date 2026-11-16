## 0. 前置與流程（AGENTS.md §7.2、§4.4）

- [ ] 0.1 在群組告知 8 個新表名（`booking_business_hours`、`booking_closing_hours`、`booking_tables`、`booking_table_links`、`booking_pricing_rules`、`booking_reservations`、`booking_reservation_tables`、`booking_reservation_logs`）
- [ ] 0.2 與立倫（auth 擁有者）確認 `auth_users.phone` 的 MR 與合併順序，以及電話是否唯一、是否必填
- [ ] 0.3 從 specs 整理「情境／操作／預期結果」表格（§7.4）給使用者確認，作為 Draft MR 說明（MR 由使用者自行開）
- [x] 0.4 設定只使用 `DATABASE_URL` 一個連線（不新增環境變數）

## 1. 資料庫（先測試後 migration）

- [x] 1.1 撰寫 migration 測試 `tests/migrations/test_booking_tables.py`：8 張表與欄位存在；UUID 主鍵；唯一與 CHECK 約束；table_links 禁止重複與反向重複；exclusion constraint 擋下同桌時間重疊，`is_active=false` 時不擋
- [x] 1.2 新增單一 Alembic revision：`CREATE EXTENSION IF NOT EXISTS btree_gist` 與 8 張表、約束、exclusion constraint；驗證 downgrade
- [x] 1.3 在 `domains/booking/models.py` 定義 8 個 SQLAlchemy model
- [x] 1.4 對本機資料庫執行 `uv run alembic upgrade head`，確認 1.1 的測試通過

## 2. Repository（API 測試等級，連本機資料庫）

- [x] 2.1 撰寫 repository 測試：營業時間、公休、啟用桌位與關係、費率規則的查詢
- [x] 2.2 撰寫 repository 測試：時段內有效訂位及其桌位、同電話有效訂位、同使用者有效訂位
- [x] 2.3 撰寫 repository 測試：建立訂位與桌位關聯、更新狀態、寫入 `booking_reservation_logs`、產生唯一 `reservation_code`、釋放桌位、時間變更同步桌位列
- [x] 2.4 實作 `repository.py`，通過 2.1–2.3

## 3. 時間規則（booking-rules，純函式）

- [x] 3.1 撰寫 `rules.py` 單元測試，涵蓋 booking-rules 每個 scenario：營業日與時間、公休時段（含整天與跨過休息）、最短時數、不跨日、不得早於現在、3 個日曆月、批次人數相同與時段不重疊
- [x] 3.2 實作時區轉換與 `weekday`（0=日）對應函式
- [x] 3.3 實作營業日、營業時間、公休時段驗證
- [x] 3.4 實作最短時數、不跨日、不得早於現在、3 個日曆月上限驗證
- [x] 3.5 實作批次驗證（各時段人數相同、時段彼此不重疊）

## 4. 費用（reservation-pricing，純函式）

- [x] 4.1 撰寫 `pricing.py` 單元測試（平日 60、週末 80、1 小時 15 分進位、超過 5 小時、實際時間與預約不同、週末提醒、平日無提醒）
- [x] 4.2 實作計費時數（進位、上限）、場地費、平日週末判斷、週末飲料低消提醒

## 5. 桌位分配（table-allocation，純函式）

- [x] 5.1 以虛構的 9 桌配置（結構同真實配置）撰寫 `allocation.py` 單元測試：單桌最小可容納、13 人、25 人鏈狀、退回相鄰不可併、退回不相鄰、桌位不足、小團體
- [x] 5.2 撰寫衝突與緩衝測試（同使用者 0、他人 5 分鐘、修改排除自己）
- [x] 5.3 實作衝突與緩衝判斷
- [x] 5.4 實作單桌選擇
- [x] 5.5 實作多桌子集合列舉、等級判斷（雙向圖、鏈狀連通）與排序
- [x] 5.6 實作批次分配（前一時段已分配的桌位納入衝突）

## 6. 訂位流程（reservation-lifecycle，service）

- [x] 6.1 在 `tests/booking/fakes.py` 寫 `FakeBookingRepository`，撰寫 service 單元測試涵蓋 reservation-lifecycle 與同電話重疊的每個 scenario
- [x] 6.2 實作交易包裝；捕捉 `ExclusionViolation` 後回滾並重新分配一次，仍失敗回傳桌位不足；釋放桌位時設 `is_active=false`
- [x] 6.3 實作建立訂位（狀態 `confirmed`、`source=online`、寫入記錄、電話必填）
- [x] 6.4 實作同電話重疊：回傳提醒、確認後取消舊訂位並建立新訂位、失敗回復
- [x] 6.5 實作批次建立（全有或全無）
- [x] 6.6 實作玩家修改（優先沿用原桌、排除自己、失敗保留原訂位）
- [x] 6.7 實作修改時重疊的合併流程
- [x] 6.8 實作取消（開始前 `cancelled`、開始後 `no_show`、已入座拒絕）
- [x] 6.9 實作店員操作：入座、完成並計算 `final_fee`、手動 no_show、no_show 改回入座、改桌
- [x] 6.10 實作訂位查詢（單筆、我的清單、店員依日期範圍）
- [x] 6.11 實作角色與擁有者檢查（`require_role`、玩家只能動自己的、店員只能動自己的店家）

## 7. API（router 與 schemas）

- [x] 7.1 撰寫 API 測試：每個端點至少成功與失敗各一個案例，另含未登入 401、沒有權限 403（用 `as_player`、`as_shop_staff`、`as_admin`；玩家動別人的訂位、店員動別家店）
- [x] 7.2 定義 `schemas.py` 請求與回應，驗證錯誤統一為 `{"error": {...}}`
- [x] 7.3 實作玩家端 endpoint：`POST /api/v1/booking-quotes`、`POST /api/v1/bookings`、`GET /api/v1/bookings`、`GET /api/v1/bookings/{id}`、`PATCH /api/v1/bookings/{id}`
- [x] 7.4 實作店員端 endpoint：`PATCH /api/v1/bookings/{id}`（入座、完成、取消、no_show）、`PUT /api/v1/bookings/{id}/tables`、`GET /api/v1/shops/{shop_id}/bookings`
- [x] 7.5 在 `app/main.py` 掛載 booking router

## 8. 匯入指令（D12）

- [x] 8.1 取消：依使用者決定，不提供匯入指令，店家設定由使用者自行準備 DML（已移除先前實作與測試）

## 9. 並發與收尾

- [x] 9.1 撰寫並發整合測試（兩個請求搶最後一張桌，一個成功、一個桌位不足），以及批次失敗回復、重疊取代、合併的整合測試
- [x] 9.2 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest` 全部通過
- [x] 9.3 以 `AUTH_MODE=dev` 啟動服務，用 `X-Dev-User` 手動走過主要流程，店家設定資料由使用者自行以 DML 提供
- [ ] 9.4 依 `.github/pull_request_template.md` 產出 MR 說明（含情境表格與對應測試）貼給使用者，並標註 @ 瑋鋐審核 migration、@ 立倫（API 契約與 `auth_users.phone`）

## 實作備註（與原計畫不同之處）

- 依使用者指示，未採測試先行；`auth_users.phone` 直接加在 `0003_booking_tables` migration，不等 auth 的 MR（合併時要與立倫對齊，避免兩支 migration 都加 phone）。
- repository 與 service 沒有另寫 `FakeBookingRepository` 單元測試，改由 `tests/booking/test_api.py`（真實資料庫）與 `tests/migrations/test_booking_tables.py` 涵蓋；既有的 `test_baseline.py` 因 `auth_users` 新增 `phone` 而更新欄位清單。
- 並發測試（9.1）以 `RacingRepository` 讓兩個請求同時讀到空桌位再寫入，驗證 exclusion constraint 與重試。
- 本機開發用獨立資料庫 `tabletop_hub_tw`（7501、`public` schema，連線字串不帶 `options=`），只使用一個連線；店家設定資料由使用者自行以 DML 寫入。
