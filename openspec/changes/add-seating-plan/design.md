## Context

- `add-reservation-system` change 已建立 `seating_tables`（含 `id`、`shop_id`、`table_code`、`table_name`、`min_capacity`、`max_capacity`、`location`、`is_active`、`created_at`）與 `seating_tables_rel`（含 `seating_tables_id_a`、`seating_tables_id_b`、`shop_id`、`is_combinable`）。
- 現有 migration 為 `0001_baseline`、`0002_games_tables`、`0003_booking_tables`。本 change 的 migration 接在 `0003` 之後。
- 前端已有 `BookingListProtoPage`（玩家查詢）與對應的 `booking_state.dart`、`booking_repository.dart`。
- 座位圖使用固定邏輯畫布 1000×700（像素座標），不做 RWD（prototype 階段）；正式頁面由永傑後續製作。
- 桌子狀態只看「該時段內是否有有效訂位（`confirmed`、`seated`）佔用」，不顯示被哪筆訂位佔用（點擊桌子才查詳情）。

## Goals / Non-Goals

**Goals:**
- `seating_tables` 擴充座標欄位（`floor`、`x`、`y`、`width`、`height`、`shape`），不影響現有分配邏輯。
- 新增 API `GET /api/v1/shops/{shop_id}/tables/status`，回傳桌子狀態（`available`／`unavailable`）。
- 前端店員看板 prototype：座位圖 + 現有訂位列表，篩選條件（日期範圍、樓層）。
- 前端客人訂位查詢 prototype：顯示座位圖 + 自己的訂位。

**Non-Goals:**
- 不修改 `allocation.py` 的桌位分配邏輯。
- 不加入 rotation、不加入 `seating_tables_rel.distance`。
- 不顯示椅子、不處理 RWD、不做正式頁面（`pages/`）。
- 不做桌位編輯功能（店員不能在前端改桌子座標）。
- 不顯示被哪筆訂位佔用（`unavailable` 只標示狀態，點擊桌子後才以 API 查詢詳情）。

## Decisions

### D1：擴充 `seating_tables` 而非新建表
在現有 `seating_tables` 以 Alembic `op.add_column` 加入 6 個欄位：`floor`、`x`、`y`、`width`、`height`、`shape`。不建立新表。

理由：桌子本身就是同一張表，座標是屬性的延伸；新增 migration 比新建表簡單，且不影響現有 `reservation_tables` 的外鍵。

### D2：新增 migration `0004_seating_plan.py`
- `upgrade`：`ALTER TABLE seating_tables ADD COLUMN` 六個欄位，全部 `NOT NULL` 並附 `server_default`。
- `downgrade`：移除六個欄位。
- 不寫入任何測試資料（D12 原則）。真實店家資料與測試用的虛構配置皆由使用者／測試以 DML 寫入。
- 欄位定義：

| 欄位 | 型別 | 預設值 | 說明 |
|---|---|---|---|
| `floor` | `smallint` | `1` | 1=1F, -1=B1 |
| `x` | `integer` | `0` | 畫布 X 座標（像素） |
| `y` | `integer` | `0` | 畫布 Y 座標（像素） |
| `width` | `integer` | `100` | 桌子寬度（像素） |
| `height` | `integer` | `100` | 桌子高度（像素） |
| `shape` | `varchar(30)` | `'rectangle'` | 形狀，目前固定 `rectangle` |

### D3：ORM model 擴充
`BookingTable`（`models.py`）新增六個 Mapped 欄位，型別對應 D2，加上 nullable=False 與 server_default。

理由：維持單一 model 對應單一表（AGENTS.md §4.2）。

### D4：`GET /api/v1/shops/{shop_id}/tables/status` API
- **Query params**：`from`（optional, ISO 8601 UTC）、`to`（optional, ISO 8601 UTC）、`floor`（optional, int）。未帶 `from`/`to` 時查詢當天 00:00–23:59:59（依 `Asia/Taipei`）。
- **Response**：`{"floor": 1, "tables": [{"id", "table_code", "max_capacity", "x", "y", "width", "height", "shape", "status": "available"|"unavailable", "booking": null|{...}}]}`
- **權限**：`player`、`shop_staff`、`admin` 皆可呼叫。`booking` 欄位僅在目前使用者為該訂位的 `user_id` 或使用者為 `shop_staff`/`admin` 時回傳。
- **可用性判斷**：該桌在時間範圍內有任何 `confirmed` 或 `seated` 的 `reservation_tables`（`is_active=true`），即為 `unavailable`。

### D5：repository 層
`BookingRepository`（抽象介面）新增 `get_tables_with_status(shop_id, start_at, end_at, floor=None) -> list[TableStatus]`。

`TableStatus` 為 records.py 中的新 dataclass，包含桌子資訊與可選的訂位摘要。

SQL 查詢邏輯：
```sql
SELECT st.*, rt.reservation_id
FROM seating_tables st
LEFT JOIN reservation_tables rt
  ON rt.shop_id = st.shop_id
  AND rt.table_id = st.id
  AND rt.is_active = true
  AND rt.start_at < :end_at
  AND rt.end_at > :start_at
  AND rt.reservation_id IN (
    SELECT r.id FROM reservations r
    WHERE r.status IN ('confirmed', 'seated')
  )
WHERE st.shop_id = :shop_id
  AND st.is_active = true
  [AND st.floor = :floor]
```

### D6：前端座位圖元件
使用 Flutter 原生 `InteractiveViewer` + `Stack` + `Positioned`。

- **畫布**：`SizedBox(width: 1000, height: 700)`，包在 `InteractiveViewer` 內（`constrained: false`，`minScale: 0.25`，`maxScale: 2.0`）。
- **桌子**：`Positioned(left: x, top: y, child: Container(width: width, height: height))` 著色。
- **顏色**：`available` = 綠色、`unavailable` = 紅色、自己的訂位 = 藍色。
- **點擊**：`GestureDetector.onTap` → 開啟 bottom sheet 顯示該桌的訂位詳情（呼叫 `GET /api/v1/bookings/{id}`）。
- **形狀**：目前只有 `rectangle`，不設 `BorderRadius`。

### D7：前端狀態層
`BookingState` 新增：
- `seatingPlan`: `SeatingPlan?`（含 `floor`、`tables` 列表）
- `selectedTable`: `TableInfo?`（點擊桌子後的詳情）

`BookingNotifier` 新增方法：
- `loadSeatingPlan(shopId, {from?, to?, floor?})`
- `selectTable(tableId)`

### D8：前端資料層
`BookingRepository` 新增抽象方法 `getTablesStatus(...)`。
`HttpBookingRepository` 實作。
`Booking` DTO 新增 `TableInfo`、`SeatingPlan` 類別。

### D9：篩選條件
店員看板 prototype 的篩選條件：
- 日期範圍（`from`、`to`，預設今天）
- 樓層下拉（`1F`、`B1`，預設 `1F`）
- 狀態（沿用現有下拉選單）

客人端只顯示「今天」的訂位，不提供日期篩選（玩家只需看當天）。

### D10：前端 prototype 路由
- 店員看板：`/proto/booking/staff`
- 客人座位圖：嵌在現有 `/proto/booking/list` 中（或新路由 `/proto/booking/my-seats`）

### D11：不新增 `seating_tables_rel.distance`
`distance` 欄位已確認移除，維持現有 `is_combinable` 手動標註。多桌分配邏輯（`allocation.py`）不受本 change 影響。

## Risks / Trade-offs

- [現有訂位系統倚賴 `seating_tables`，新增 NOT NULL 欄位若 migration 有誤可能中斷] → migration 全部欄位附 `server_default`，且僅在 dev 分支先行驗證。
- [座位圖 prototype 不做 RWD，正式頁面可能需要重構] → prototype 階段可接受，交接說明會標註 RWD 需求。
- [玩家端座位圖洩漏他人訂位資訊] → `tables/status` 的 `booking` 欄位僅在使用者為該訂位 owner 或店員時回傳；`unavailable` 不附訂位詳情。

## Migration Plan

1. 建立 `0004_seating_plan.py`（`ALTER TABLE ADD COLUMN` 六欄位，附 `server_default`）。
2. `uv run alembic upgrade head` 套用；`downgrade` 驗證可回復。
3. 以 DML 寫入測試用的虛構桌位資料（驗證 API）。
4. 前端 prototype 完成後，由永傑製作正式頁面。

## Open Questions

- 無。
