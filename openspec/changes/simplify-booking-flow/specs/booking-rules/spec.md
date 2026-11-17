## ADDED Requirements

### Requirement: 訂位時間粒度限制
訂位的 `start_at` 與 `end_at` 在公司時區下的分鐘數 SHALL 為 0 或 30。建立與修改訂位皆適用。

#### Scenario: 整點開始與結束
- **WHEN** 客戶訂 14:00–16:00
- **THEN** 系統接受時間驗證

#### Scenario: 半點開始與結束
- **WHEN** 客戶訂 14:30–17:00
- **THEN** 系統接受時間驗證

#### Scenario: 開始分鐘非整點或半點
- **WHEN** 客戶訂 14:15–16:00
- **THEN** 系統拒絕並回傳 `BOOKING_TIME_GRANULARITY`

#### Scenario: 結束分鐘非整點或半點
- **WHEN** 客戶訂 14:00–16:45
- **THEN** 系統拒絕並回傳 `BOOKING_TIME_GRANULARITY`

#### Scenario: 修改訂位也受限制
- **WHEN** 玩家修改訂位，新的開始或結束時間分鐘數非 0 或 30
- **THEN** 系統拒絕修改並保留原訂位

## MODIFIED Requirements

### Requirement: 訂位時長與跨日限制
單筆訂位 SHALL 至少 1 小時（以 `pricing_rules.BOOKING_MIN_HOURS` 為準），開始與結束時間 MUST 為整點或 30 分。單筆訂位 MUST NOT 跨越日曆日期；第一階段不支援跨午夜拆單。

#### Scenario: 不足 1 小時
- **WHEN** 客戶訂 14:00–14:30
- **THEN** 系統拒絕訂位

#### Scenario: 半點開始整點結束
- **WHEN** 客戶訂 14:30–16:00
- **THEN** 系統接受時間驗證

#### Scenario: 跨日被拒絕
- **WHEN** 訂位 `start_at` 與 `end_at` 在公司時區屬於不同日期
- **THEN** 系統拒絕訂位

## REMOVED Requirements

### Requirement: 多時段批次訂位
**Reason**: 簡化訂位流程，一次請求只建立單一時段。
**Migration**: 建立多時段的客戶需分次提交請求。前端移除多時段表單，改為單一時段選擇。
