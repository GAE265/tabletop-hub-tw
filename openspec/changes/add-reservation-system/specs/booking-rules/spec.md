## ADDED Requirements

### Requirement: 營業日與營業時間驗證
系統 SHALL 依 `business_hours` 驗證訂位：訂位日期的星期（0=星期日）必須有營業時間設定，且 `start_at`、`end_at` 必須落在 `open_time` 至 `close_time` 之內。所有時間 SHALL 以公司時區（`Asia/Taipei`）判斷。

#### Scenario: 公休日被拒絕
- **WHEN** 客戶訂星期二（weekday=2，無營業時間設定）的位
- **THEN** 系統拒絕訂位並回傳非營業日錯誤

#### Scenario: 超出營業時間被拒絕
- **WHEN** 客戶訂 12:00–14:00（營業時間為 13:00–22:00）
- **THEN** 系統拒絕訂位

#### Scenario: 營業時間內可訂位
- **WHEN** 客戶訂 14:00–16:00 且通過其他規則
- **THEN** 系統接受時間驗證

### Requirement: 公休時段驗證
系統 SHALL 拒絕與 `closing_hours` 有任何時間交集的訂位。`start_time` 與 `end_time` 皆為 NULL 的紀錄代表整天公休。

#### Scenario: 與休息時段有交集
- **WHEN** 公休時段為 2026-11-18 12:00–14:00，客戶訂當日 13:00–15:00
- **THEN** 系統拒絕訂位

#### Scenario: 跨過休息時段
- **WHEN** 公休時段為 12:00–14:00，客戶訂 11:30–15:00
- **THEN** 系統拒絕訂位

#### Scenario: 整天公休
- **WHEN** 某日 `closing_hours` 的 `start_time` 與 `end_time` 為 NULL
- **THEN** 系統拒絕該日所有訂位

### Requirement: 訂位時長與跨日限制
單筆訂位 SHALL 至少 1 小時（以 `pricing_rules.BOOKING_MIN_HOURS` 為準），開始時間不限整點或半點。單筆訂位 MUST NOT 跨越日曆日期；第一階段不支援跨午夜拆單。

#### Scenario: 不足 1 小時
- **WHEN** 客戶訂 14:00–14:45
- **THEN** 系統拒絕訂位

#### Scenario: 非整點開始
- **WHEN** 客戶訂 14:10–16:40
- **THEN** 系統接受時間驗證

#### Scenario: 跨日被拒絕
- **WHEN** 訂位 `start_at` 與 `end_at` 在公司時區屬於不同日期
- **THEN** 系統拒絕訂位

### Requirement: 提前期限
訂位 `start_at` MUST NOT 早於當下，且 MUST NOT 晚於當下起算的 3 個日曆月。系統 SHALL 允許當天訂位，不設最少提前時間。

#### Scenario: 開始時間已過
- **WHEN** 現在是 13:20，客戶訂當日 13:00–15:00
- **THEN** 系統拒絕訂位

#### Scenario: 當天稍後時段
- **WHEN** 現在是 13:20，客戶訂當日 13:30–15:00
- **THEN** 系統接受時間驗證

#### Scenario: 超過 3 個日曆月
- **WHEN** 今天是 2026-11-16，客戶訂 2027-02-17 的位
- **THEN** 系統拒絕訂位

### Requirement: 多時段批次訂位
客戶 SHALL 能於同一次請求提交同一天的多個時段。每個時段 SHALL 建立一筆獨立訂位，各時段人數 MUST 相同，時段之間 MUST NOT 互相重疊，且每個時段 MUST 通過所有訂位規則。批次 SHALL 為全有或全無：任一時段失敗，整批不建立。

#### Scenario: 全部成功
- **WHEN** 客戶同日提交 14:00–16:00 與 18:00–20:00，人數皆為 4，且都有桌位
- **THEN** 系統建立兩筆獨立訂位

#### Scenario: 其中一個時段失敗
- **WHEN** 客戶提交兩個時段，第二個時段無可用桌位
- **THEN** 系統不建立任何訂位並回傳失敗原因

#### Scenario: 批次內時段重疊
- **WHEN** 客戶提交 14:00–16:00 與 15:00–17:00
- **THEN** 系統拒絕整個批次

### Requirement: 同電話時段重疊處理
同一電話（取自 `auth_users.phone`）SHALL 可建立多筆訂位；玩家沒有電話時 MUST 拒絕建立訂位（422，`BOOKING_PHONE_REQUIRED`）。若新訂位與同電話的有效訂位（`confirmed`、`seated`）有任何時間重疊，系統 SHALL 先回傳重疊提醒且不建立任何訂位；客戶確認後，系統 SHALL 在同一交易內取消所有重疊的舊訂位（`cancel_reason` 註明被新訂位取代）並建立新訂位。若新訂位建立失敗，交易 SHALL 回復並保留舊訂位。

#### Scenario: 沒有電話不能訂位
- **WHEN** 玩家的 `auth_users.phone` 為空並提交訂位
- **THEN** 系統拒絕並回傳 `BOOKING_PHONE_REQUIRED`，不建立訂位

#### Scenario: 未確認前不建立
- **WHEN** 客戶提交與自己既有訂位重疊的新訂位，且未帶確認旗標
- **THEN** 系統回傳 409（`BOOKING_OVERLAP_CONFIRM_REQUIRED`）與受影響的既有訂位，且資料庫無任何變更

#### Scenario: 確認後取代舊訂位
- **WHEN** 客戶帶確認旗標重新提交，且新訂位可分配桌位
- **THEN** 系統取消所有重疊的舊訂位並建立新訂位，舊訂位的 `cancel_reason` 註明被取代

#### Scenario: 確認後新訂位失敗
- **WHEN** 客戶帶確認旗標提交，但新訂位無法分配桌位
- **THEN** 系統回傳失敗，舊訂位維持 `confirmed`
