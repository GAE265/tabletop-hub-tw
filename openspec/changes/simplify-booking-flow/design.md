## Context

目前 `add-reservation-system` 的訂位系統已實作完成（42/46 tasks），桌位衝突判斷透過 `is_conflict` 搭配 `BUFFER_MINUTES=5`，開始時間無粒度限制，API 支援 `slots` 陣列的多時段批次訂位。本次簡化是對既有 booking domain 的純刪減與調整，不引入新概念。

## Goals / Non-Goals

**Goals:**
- 移除緩衝時間：`is_conflict` 改為單純時間區間重疊判斷
- 新增時間粒度驗證：`start_at` 與 `end_at` 分鐘數限 `0` 或 `30`
- 移除多時段批次訂位：API 從 `slots` 陣列改為單一時段欄位

**Non-Goals:**
- 不改變資料庫 schema（exclusion constraint 本就無緩衝概念）
- 不改變桌位分配策略（單桌優先、多桌組合的排序邏輯）
- 不改變費用計算規則
- 不改變訂位狀態流轉邏輯
- 不改變前端正式頁面（`pages/`），只改 `data/`、`state/`、`prototypes/`

## Decisions

### D1: 取消緩衝 → 直接設 `BUFFER_MINUTES=0`，不刪除參數

`is_conflict` 的 `buffer_minutes` 參數保留但預設值改為 `0`，讓函式簽章維持向後相容。同一使用者緩衝本來就是 0，差異只在將不同使用者的緩衝也設為 0。

**替代方案：** 完全刪除 `buffer_minutes` 參數。不採用，因為參數存在不造成維護負擔，且有助於未來若需要回復緩衝時的追溯。

### D2: 時間粒度驗證 → 在 `validate_slot` 中新增檢查

新增 `validate_time_granularity(slot: Slot)`，檢查 `start_at` 與 `end_at` 在公司時區下的分鐘數為 `0` 或 `30`。放入 `validate_slot` 中，建立與修改訂位自然都受此限制。

錯誤碼: `BOOKING_TIME_GRANULARITY`，422。

### D3: 取消批次 → `BookingCreate.slots` 改為單一時段欄位

Schema `BookingCreate` 的 `slots: list[SlotSchema]` 改為 `start_at` + `end_at` 兩個直接欄位（或用單一 `SlotSchema` 物件），不再包在陣列中。

- `service.create` 不再呼叫 `validate_batch` / `allocate_batch`
- `service.modify` 同樣只處理單一時段
- `validate_batch` 與 `allocate_batch` 標記 deprecated 或直接移除

**替代方案：** 保留 `slots` 陣列但限制長度為 1。不採用，因為這會在 API 層留下不必要的複雜度，前端仍要處理陣列結構。

### D4: `reservation-pricing` spec 不受影響

費用計算依賴 `start_at` 與 `end_at` 的時間差，與時間粒度或是否為批次無關。週末飲料提醒也不受影響。

## Risks / Trade-offs

- **店家無法在尖峰時段安排無縫接場** → 店家接受 14:00–16:00 後下一組客人最早 16:00 入座（無緩衝），由店家自行在營業規則中調整（例如只開放整點開始）。
- **時間粒度限制降低彈性** → 客人無法訂 14:15，這是刻意的簡化。店家可自行決定是否要開放更多時段（未來可考慮 15 分粒度，但目前就是整點/半點）。
- **失去批次訂位的便利性** → 客人想訂同日兩個時段需分兩次請求。這是可接受的權衡，因為多時段是少數情境。
