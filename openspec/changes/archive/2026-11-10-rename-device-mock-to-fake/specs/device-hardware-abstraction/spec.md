# Spec Delta

## ADDED Requirements

### Requirement: 提供 fake 實作
系統 SHALL 為攝影機與馬達各提供 fake 實作，行為可預測且不需任何硬體。

#### Scenario: fake 攝影機
- **WHEN** 對 fake 攝影機要求影格
- **THEN** 回傳預先設定的影格或固定測試影格

#### Scenario: fake 馬達記錄動作
- **WHEN** 對 fake 馬達下達轉動指令
- **THEN** 動作被記錄供測試檢查，且不拋出硬體錯誤

## REMOVED Requirements

### Requirement: 提供 mock 實作
**Reason**: 依 AGENTS.md 7.5，測試替身統一稱為 fake；僅用詞變更，行為不變。
**Migration**: 改用「提供 fake 實作」，內容與驗收行為完全相同。
