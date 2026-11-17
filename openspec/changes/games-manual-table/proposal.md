## Why

規則書 OCR 入庫（`rules_ingest`，#5）最後要把每一頁的 Markdown 文字存進資料庫，但目前本 repo 沒有存放的資料表。遠端開發資料庫已有一張手動建立的 `games_manual`，不在任何 migration 裡，結構也沒有頁碼檢查，外鍵還是 `ON DELETE CASCADE`，與 ADR 0003 衝突。先把這張表納入 Alembic，後續的掃描入庫 API 與 OCR 才有穩定的寫入目標。

## What Changes

- 新增 migration `0003`：建立 `games_manual`（沿用舊表名與欄位 `games_id`、`page`、`content`），主鍵 `(games_id, page)`。
- `games_id` 外鍵指向 `games.id`，**不加** `ON DELETE CASCADE`（ADR 0003：參照 `games.id` 的表不可跟著桌遊刪除）。
- 加上 `CHECK (page >= 1)`（舊表沒有）。
- 新增 SQLAlchemy model 與 repository，提供以 `(games_id, page)` 為鍵的 upsert（強制覆蓋）。
- 不含任何 API 端點、OCR 或查詢／編輯／刪除功能；那些是後續 change（`PUT /api/v1/games/{game_id}/manual-pages/{page}`）。

## Capabilities

### New Capabilities
- `games-manual-storage`: 規則書每頁 Markdown 文字的資料表結構、約束，以及依 `(games_id, page)` 覆蓋寫入的 repository。

### Modified Capabilities
<!-- 無：database-baseline 等既有 spec 的需求不變 -->

## Impact

- **Domain／主責**：`rules_ingest`（瑋鋐）。`games_manual` 由本 domain 擁有，不是共用資料表；`games` 是共用表（立倫），只讀它的 `id`，不改結構。
- **Migration**：有（`0003`），依 AGENTS.md §4.4 由瑋鋐審核；MR 要 @ 瑋鋐。
- **契約**：無 API、MQTT、domain 間介面變更。
- **程式**：`backend/migrations/versions/0003_games_manual.py`、`backend/app/domains/rules_ingest/{models,repository}.py`，並在 `migrations/env.py` 匯入新 model。
- **新增套件**：無。
- **部署注意**：舊的開發資料庫（7500 的 `games` schema）有手動建立的 `games_manual`（0 筆），那邊若要改用 migration，要先 drop 或改名。新的開發環境（7501 的 `board_game_ocr`）沒有舊表，不受影響。
