# Spec Delta

## Purpose

讓新組員依 README 步驟在本機啟動資料庫、MQTT broker 與後端，且不會把秘密或系統檔提交進公開 repo。

## ADDED Requirements

### Requirement: 設定範本只含欄位名與說明
`.env.example` SHALL 列出資料庫連線、`AUTH_MODE`、`LLM_PROVIDER`、雲端模型金鑰、MQTT 連線所需欄位，每個欄位附說明，且 MUST NOT 含任何真實秘密值。

#### Scenario: 範本不含秘密
- **WHEN** 檢視 `.env.example`
- **THEN** 金鑰與密碼欄位為空值或明顯的佔位文字，並含 `AUTH_MODE`、`LLM_PROVIDER` 欄位與說明

### Requirement: 本機服務一鍵啟動
`docker-compose.yml` SHALL 提供 PostgreSQL 16（含 pgvector）與 Mosquitto MQTT broker（本機允許匿名連線），資料庫資料 MUST 存在具名 volume。

#### Scenario: 啟動服務
- **WHEN** 執行 `docker compose up -d`
- **THEN** PostgreSQL 與 Mosquitto 容器皆處於 running，且資料庫可用 `.env` 的連線資訊登入

#### Scenario: 重啟後資料保留
- **WHEN** 執行 `docker compose down` 後再 `up -d`（不加 `-v`）
- **THEN** 資料庫內容仍在

### Requirement: 版本控制排除秘密與系統檔
`.gitignore` SHALL 排除 `.env`、Python、Flutter、Node、VS Code 與 macOS／Windows 系統檔產物，但 MUST NOT 排除 `.env.example`。

#### Scenario: .env 不被追蹤
- **WHEN** 建立 `.env` 後執行 `git status`
- **THEN** `.env` 不出現在未追蹤清單，`.env.example` 仍可被追蹤

### Requirement: 鎖定檔必須提交
`uv.lock` 與 `pubspec.lock` MUST 被版本控制追蹤，`.gitignore` MUST NOT 排除它們。

#### Scenario: 鎖定檔可被追蹤
- **WHEN** 產生 `backend/uv.lock`、`device/uv.lock` 與 `frontend/pubspec.lock` 後執行 `git status`
- **THEN** 三個檔案皆出現在可加入的變更清單，未被忽略

### Requirement: 換行符號與編輯器設定統一
repo SHALL 以 `.gitattributes`（`* text=auto eol=lf`）使所有文字檔以 LF 簽出，並以 `.editorconfig` 統一縮排與結尾換行設定。

#### Scenario: Windows 簽出
- **WHEN** 在 Windows 上 clone 後檢查 `device/` 內的 shell 腳本
- **THEN** 檔案以 LF 結尾，可在樹莓派直接執行

#### Scenario: 編輯器設定存在
- **WHEN** 檢視 `.editorconfig`
- **THEN** 含 `root = true`、LF 換行與結尾換行設定，且與 ruff 行長 100 及 Dart 格式慣例不衝突
### Requirement: README 提供啟動與規則摘要
`README.md` SHALL 含專案簡介、本機啟動步驟、`main`／`dev` 分支規則、commit 格式摘要，並連結 `AGENTS.md` 與 `docs/test-first-flow.md`。

#### Scenario: 連結可達
- **WHEN** 檢視 README 中指向 `AGENTS.md` 與 `docs/test-first-flow.md` 的連結
- **THEN** 兩個連結目標檔案皆存在

#### Scenario: 載明 Flutter 版本與 seed 步驟
- **WHEN** 檢視 README 的啟動步驟
- **THEN** 載明鎖定的 Flutter stable 版本（與 CI 相同），並含執行開發用 seed 指令的步驟

### Requirement: 既有文件不被改動
骨架 MUST NOT 修改或移動 `AGENTS.md`、`CLAUDE.md`、`openspec/` 既有內容、`docs/test-first-flow.md` 與 `docs/images/`。

#### Scenario: 受保護檔案無差異
- **WHEN** 骨架實作完成後對上述路徑執行 `git diff`
- **THEN** 相對於實作開始前沒有任何新增的變更
