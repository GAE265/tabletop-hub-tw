## ADDED Requirements

### Requirement: 場地費計算
系統 SHALL 依訂位日期的星期（公司時區）選擇費率：星期一至五採 `WEEKDAY_HOURLY_FEE`（NT$60），星期六、日採 `WEEKEND_HOURLY_FEE`（NT$80），單位為每人每小時。計費時數 SHALL 以 `BILLING_ROUNDING_UNIT_HOURS` 無條件進位，並以 `BILLING_MAX_HOURS`（5 小時）為上限。場地費 = 人數 × 計費時數 × 費率。費率與規則值 SHALL 從 `booking_pricing_rules` 讀取。系統 MUST NOT 考慮國定假日。

#### Scenario: 平日整點
- **WHEN** 平日 4 人訂位 2 小時
- **THEN** 預估場地費為 4 × 2 × 60 = 480

#### Scenario: 不足一小時進位
- **WHEN** 平日 2 人訂位 1 小時 15 分
- **THEN** 計費時數為 2 小時，場地費為 2 × 2 × 60 = 240

#### Scenario: 超過 5 小時包日
- **WHEN** 週六 3 人訂位 8 小時
- **THEN** 計費時數為 5 小時，場地費為 3 × 5 × 80 = 1200

### Requirement: 預估與結算費用
訂位建立與修改時，系統 SHALL 回傳依預約時間計算的預估費用。店員標記 `completed` 時，系統 SHALL 以 `seated_at` 至 `completed_at` 的實際使用時間依同一套規則計算 `final_fee`。系統 MUST NOT 要求預付款或訂金，MUST NOT 整合付款。

#### Scenario: 實際時間與預約不同
- **WHEN** 預約 2 小時但實際使用 2 小時 20 分
- **THEN** `final_fee` 以 3 小時計費

#### Scenario: 不收訂金
- **WHEN** 玩家建立訂位
- **THEN** 流程中沒有任何付款步驟

### Requirement: 週末飲料低消提示
星期六、日的訂位 SHALL 在回應中附帶提醒：每位客人至少一杯飲料，點心不能代替。系統 MUST NOT 驗證實際點餐內容，由店員核對。星期一至五 SHALL NOT 顯示低消提醒。

#### Scenario: 週末提醒
- **WHEN** 玩家建立星期六的訂位
- **THEN** 回應含每人至少一杯飲料的提醒

#### Scenario: 平日無提醒
- **WHEN** 玩家建立星期一的訂位
- **THEN** 回應不含飲料低消提醒
