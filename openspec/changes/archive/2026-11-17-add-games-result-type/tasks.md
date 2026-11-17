# Tasks

## 1. 測試案例與測試（先寫，此時應該失敗，AGENTS.md 7.2）

- [x] 1.1 在 MR 說明列出情境表（對應 specs/games-result-type/spec.md），@ 立倫確認；驗證：表格每行有對應測試
- [x] 1.2 寫資料庫層測試（API 測試分類，連資料庫，沿用 `backend/tests/games_advisor/` 的 games 測試位置與 fixture）：三個合法值可寫入、`ranking`／空字串／`Faction` 被擋、不給值為空、升級後既有列為空、降版移除欄位、欄位 comment 非空；驗證：`uv run pytest` 這些測試失敗且原因是欄位不存在
- [x] 1.3 寫匯入／匯出／同步測試（用 fake 資料，單元層）：匯出帶 `result_type`、匯入有值、舊格式檔案通過、非法值被擋且無變動、同步蓋掉值；驗證：測試失敗
- [x] 1.4 寫推薦 API 回應不含 `result_type` 的測試；驗證：此測試在實作前就通過（防止日後意外多欄位）

## 2. 資料庫與 model

- [x] 2.1 在 `app/core/games/models.py` 新增 `ResultType`（`StrEnum`，三值各有中文註解）與 `Game.result_type`（`Text`、可為空、中文 `comment=`）、`ck_games_result_type`；驗證：1.2 的 model 層測試通過；不改其他欄位
- [x] 2.2 新增 `migrations/versions/0004_games_result_type.py`（只加欄位與 CHECK，附 downgrade）；驗證：`uv run alembic upgrade head`、`downgrade -1`、再 `upgrade head` 都成功，`alembic heads` 只有一個

## 3. 匯入／匯出／同步

- [x] 3.1 `games_advisor/schemas.py` 的 `GameData` 加 `result_type: ResultType | None = None`，確認 `ExportedGame` 自動帶出，並更新該 docstring 的欄位數說明；驗證：1.3 測試通過
- [x] 3.2 確認既有 games_advisor 測試不因新欄位失敗；驗證：`uv run pytest backend/tests/games_advisor` 全過

## 4. 文件與收尾

- [x] 4.1 若 `docs/` 有描述 `games.json`／匯出檔欄位的文件，補上 `result_type`（先 grep 確認；沒有就略過）；驗證：grep 無遺漏
- [x] 4.2 自我檢查：`uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest` 全過
- [x] 4.3 依 `.github/pull_request_template.md` 產出簡短 MR 說明給使用者（不自行開 MR）；標明契約變更要 @ 立倫、migration 要 @ 瑋鋐
