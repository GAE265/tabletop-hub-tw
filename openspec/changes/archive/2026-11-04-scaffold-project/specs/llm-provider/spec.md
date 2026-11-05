# Spec Delta

## Purpose

讓 domain 以單一介面呼叫 LLM，雲端與地端可用設定切換，測試不必連外部服務。

## ADDED Requirements

### Requirement: 統一的 LLM 呼叫介面
系統 SHALL 提供 `LLMProvider` 介面，含 `generate(prompt)` 並回傳文字；任何 domain MUST NOT 直接 import 模型廠商 SDK。

#### Scenario: 透過介面呼叫
- **WHEN** service 取得 `LLMProvider` 並呼叫 `generate("hi")`
- **THEN** 回傳字串，service 不需知道實作是哪一種

### Requirement: 測試用固定回覆實作
系統 SHALL 提供 `FakeLLMProvider`，對任何輸入回傳固定文字，且不發出任何網路請求。

#### Scenario: 固定輸出
- **WHEN** 以不同 prompt 呼叫 `FakeLLMProvider.generate`
- **THEN** 皆回傳相同的預設固定文字

#### Scenario: 可自訂回覆
- **WHEN** 以指定文字建立 `FakeLLMProvider`
- **THEN** `generate` 回傳該指定文字

### Requirement: 由設定選擇實作
`LLM_PROVIDER` 設定 SHALL 決定使用的實作；骨架階段只支援 `fake`，其他值 MUST 在啟動時明確報錯。

#### Scenario: 設為 fake
- **WHEN** `LLM_PROVIDER=fake`
- **THEN** 取得的實作為 `FakeLLMProvider`

#### Scenario: 未支援的值
- **WHEN** `LLM_PROVIDER=cloud` 但雲端實作尚未提供
- **THEN** 取得實作時拋出說明「尚未實作」的明確錯誤，而非靜默退回 fake
