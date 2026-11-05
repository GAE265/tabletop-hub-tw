# ci-checks Specification

## Purpose

在合併前自動擋下 lint、格式與測試失敗，落實 AGENTS.md 8.3 的 CI 要求。

## Requirements

### Requirement: MR 觸發檢查
GitHub Actions SHALL 在對 `dev` 或 `main` 發出 pull request 時自動執行後端、前端與 device 檢查，三者為獨立 job。

#### Scenario: 發 MR 到 dev
- **WHEN** 開啟或更新目標為 `dev` 的 pull request
- **THEN** 當時 workflow 內已存在的各 job（後端、前端、device）皆被觸發

#### Scenario: 一般推送不觸發
- **WHEN** 推送到功能分支且尚未開 pull request
- **THEN** 不執行這些檢查

### Requirement: 後端檢查內容
後端 job SHALL 依序執行 `ruff check`、`ruff format --check`、`pytest`，並提供 PostgreSQL 16 + pgvector 服務。

#### Scenario: 格式不符
- **WHEN** 程式碼未通過 `ruff format --check`
- **THEN** 後端 job 失敗

### Requirement: 前端檢查內容
前端 job SHALL 執行 `flutter analyze` 與 `flutter test`。

#### Scenario: 靜態分析錯誤
- **WHEN** `flutter analyze` 回報錯誤
- **THEN** 前端 job 失敗

### Requirement: device 檢查內容
device job SHALL 在 `device/` 執行 `ruff check`、`ruff format --check`、`pytest`，不需任何硬體或服務。

#### Scenario: 測試失敗
- **WHEN** `device/` 的 pytest 有失敗
- **THEN** device job 失敗

### Requirement: 各 job 獨立
任一 job 失敗 MUST NOT 阻止其他 job 執行，使 PR 上能同時看到各自的結果。

#### Scenario: 後端失敗時前端仍執行
- **WHEN** 後端 job 失敗
- **THEN** 前端與 device job 仍然執行完畢

### Requirement: Flutter 版本與 README 一致
CI 使用的 Flutter stable 版本 SHALL 與 README 載明的版本相同。

#### Scenario: 版本一致
- **WHEN** 比對 `ci.yml` 與 README 中的 Flutter 版本
- **THEN** 兩者相同

### Requirement: 不在 CI 中暴露秘密
workflow MUST NOT 內嵌真實秘密；CI 用的資料庫帳密為僅限 CI 的測試值。

#### Scenario: 檢視 workflow
- **WHEN** 檢視 `ci.yml`
- **THEN** 不含雲端模型金鑰或正式環境連線字串
