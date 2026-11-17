## 1. 實作

- [x] 1.1 新增 `backend/app/domains/rules_ingest/__init__.py` 與 `models.py`：`GameManualPage`（表 `games_manual`，欄位 `games_id`、`page`、`content`，主鍵 `(games_id, page)`，外鍵 `games.id` 無 cascade，`CheckConstraint("page >= 1", name="ck_games_manual_page_positive")`）
- [x] 1.2 新增 `backend/migrations/versions/0003_games_manual.py`（`down_revision = "0002"`，升級建表與約束，降級 `drop_table`）
- [x] 1.3 `backend/migrations/env.py` 匯入 `rules_ingest` 的 models
- [x] 1.4 新增 `backend/app/domains/rules_ingest/repository.py`：`upsert_page(games_id, page, content)` 使用 `INSERT ... ON CONFLICT DO UPDATE`；外鍵違反轉成 `GameNotFoundError`
- [x] 1.5 在 `openspec/specs` 無需更動；確認 `.env.example` 不需新增欄位（本 change 無新設定）

## 2. 資料庫與環境

- [x] 2.1 在開發資料庫 7501 的 `board_game_ocr`（schema `tabletop-hub-tw_ocr`）跑 `uv run alembic upgrade head`，確認 `0003` 建表、約束與 spec 一致
- [x] 2.2 跑 `alembic downgrade 0002` 再升回 head，確認可往返
- [x] 2.3 遠端環境：7501 的 `board_game` 裡 vector 已裝在他人的 schema，改在新資料庫 `board_game_ocr` 的 `tabletop-hub-tw_ocr` schema 跑完 0001→0003

## 3. 測試（先實作後補，依使用者決定）

- [x] 3.1 migration 測試（`backend/tests/migrations/`）：主鍵、頁碼檢查（0、-1）、外鍵（桌遊不存在、刪除有規則書的桌遊被擋、無規則書可刪）、升級與降級
- [x] 3.2 repository 測試（`backend/tests/rules_ingest/`，API 層級的資料庫測試）：新增、覆蓋、覆蓋成空字串、不影響其他頁、桌遊不存在拋 `GameNotFoundError`、缺號頁碼
- [x] 3.3 每個 spec scenario 都對應到一個測試

## 4. 發 MR 前

- [x] 4.1 在 `backend/` 跑 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`，全部通過
- [ ] 4.2 產出 MR 說明（依 `.github/pull_request_template.md`）：情境表格、change 名稱 `games-manual-table`、@ 瑋鋐審 migration、註明舊表處理方式與先實作後補測試
