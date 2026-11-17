## Why

目前訂位流程包含三個增加複雜度與混淆的設計：5 分鐘緩衝（造成桌位釋放時間不一致）、開始時間不受限制（店家難安排時段）、以及一次請求可提交多時段（增加前端表單複雜度與批次交易風險）。簡化這三點讓訂位流程對玩家與店家都更直覺，程式也更易維護。

## What Changes

- **取消緩衝時間**：移除 `BUFFER_MINUTES` 常數，桌位衝突判斷改為單純的時間重疊，不再為不同玩家保留 5 分鐘前後緩衝。**BREAKING**：現有訂位的桌位佔用邏輯變更。
- **限制訂位時間為整點或 30 分**：`start_at` 與 `end_at` 的分鐘數只能是 0 或 30，建立與修改訂位皆適用。**BREAKING**：原有非整點/半點的訂位請求將被拒絕。
- **取消多時段批次訂位**：API 從接收 `slots` 陣列改為單一時段。移除 `validate_batch`、`allocate_batch` 等批次相關函式。**BREAKING**：API 契約變更。

## Capabilities

### New Capabilities
<!-- 本次不新增 capability，僅修改現有 booking 相關規則 -->

### Modified Capabilities
- `booking-rules`: 新增時間粒度驗證（開始與結束時間限整點或 30 分）；移除多時段批次驗證（`validate_batch`）。
- `table-allocation`: 移除緩衝時間（`BUFFER_MINUTES`），衝突判斷簡化為純時間重疊；移除 `allocate_batch`。
- `reservation-lifecycle`: 建立訂位 API 從接收多時段改為單一時段；修改訂位同樣適用新時間粒度規則。

## Impact

- 受影響 domain：`booking`
- 主責：瑋鋐
- API 契約變更：`POST /api/v1/bookings`、`PATCH /api/v1/bookings/{id}` 的 request body 結構改變（`slots` → 單一時段）
- 不含 migration
- 前端需同步調整：`BookingCreate` DTO、訂位表單
