# Spec Delta

## Purpose

導覽列依角色多出管理員專用的項目。

## ADDED Requirements

### Requirement: 管理員才有的導覽項目
目前身分是管理員時，主要導覽列 SHALL 在最後多一個「匯入」（`/rules-ingest`，key `shell-nav-rules-ingest`），在 `/rules-ingest` 時為選取狀態。玩家、店家人員或沒有身分時 MUST NOT 顯示這個項目，其他項目不變。

#### Scenario: 管理員
- **WHEN** 目前身分是管理員
- **THEN** 導覽列有「匯入」，點下前往 `/rules-ingest`

#### Scenario: 選取
- **WHEN** 管理員在 `/rules-ingest`
- **THEN** 「匯入」為選取狀態，其他項目不是

#### Scenario: 其他人
- **WHEN** 目前身分是玩家或店家人員
- **THEN** 導覽列沒有「匯入」
