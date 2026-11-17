## 1. Migration

- [ ] 1.1 建立 `backend/migrations/versions/0004_seating_plan.py`：`ALTER TABLE seating_tables ADD COLUMN` 六個欄位（`floor`、`x`、`y`、`width`、`height`、`shape`），全部 NOT NULL 附 server_default，含 downgrade

## 2. 後端 Model 與 Repository

- [ ] 2.1 `models.py`：`BookingTable` 新增六個 Mapped 欄位（`floor`、`x`、`y`、`width`、`height`、`shape`）
- [ ] 2.2 `records.py`：新增 `TableStatus` dataclass
- [ ] 2.3 `repository.py`：新增 `get_tables_with_status` 方法，依 shop_id、時間範圍、可選 floor 查詢桌位與佔用狀態

## 3. 後端 Service 與 API

- [ ] 3.1 `schemas.py`：新增 `TableStatusOut`、`SeatingPlanOut` schema
- [ ] 3.2 `service.py`：新增 `get_tables_status` 方法，組合 repository 查詢、判斷權限（玩家只能看到自己訂位的 booking 資訊）
- [ ] 3.3 `router.py`：新增 `GET /api/v1/shops/{shop_id}/tables/status` 端點

## 4. 後端測試

- [ ] 4.1 `tests/domains/booking/`：新增 `test_seating_plan_api.py`，涵蓋 spec 中所有 scenario（含查詢指定時段、未帶時間、未帶樓層、不同狀態、權限、店家不存在、未登入）
- [ ] 4.2 `tests/domains/booking/` 或 `tests/conftest.py`：新增測試用桌位 fixture（1F A–G + B1 H–I 虛構座標）

## 5. 前端 Data 層

- [ ] 5.1 `booking.dart`：新增 `TableInfo`、`SeatingPlan` DTO
- [ ] 5.2 `booking_repository.dart`：`BookingRepository` 新增 `getTablesStatus` 抽象方法，`HttpBookingRepository` 實作

## 6. 前端 State 層

- [ ] 6.1 `booking_state.dart`：`BookingState` 新增 `seatingPlan`、`selectedTable` 欄位；`BookingNotifier` 新增 `loadSeatingPlan`、`selectTable` 方法

## 7. 前端座位圖元件

- [ ] 7.1 `frontend/lib/core/` 或 `domains/booking/`：新增 `SeatingPlanWidget`（`InteractiveViewer + Stack + Positioned`，支援縮放平移、點擊桌子、依狀態著色）
- [ ] 7.2 新增 `TableWidget` 子元件（`GestureDetector` 包 `Container`，依 status 顯示綠／紅／藍色）

## 8. 前端 Prototype 頁面

- [ ] 8.1 `prototypes/booking/staff_seating_proto_page.dart`：店員看板 prototype（日期範圍篩選、樓層下拉、座位圖 + 訂位列表、點擊桌子顯示詳情）
- [ ] 8.2 修改 `prototypes/booking/booking_list_proto_page.dart`：客人查詢頁面加入當天座位圖（藍色標示自己的訂位）
- [ ] 8.3 `router.dart`：註冊 `/proto/booking/staff` 路由

## 9. 前端測試

- [ ] 9.1 `test/support/fakes.dart`：`FakeBookingRepository` 新增 `getTablesStatus` 實作
- [ ] 9.2 `test/domains/booking/`：擴充 `booking_state_test.dart`，涵蓋座位圖狀態的載入與點擊

## 10. 交接說明

- [ ] 10.1 `docs/handoff/booking-seating.md`：依 `docs/handoff/_template.md` 格式撰寫，說明店員看板與客人座位圖的頁面、元件、API、狀態處理、正式頁面製作注意事項
