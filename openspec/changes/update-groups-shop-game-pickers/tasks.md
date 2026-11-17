# Tasks

> 兩個 MR（design.md 的 Risks：揪團的後端與前端放同一個 MR，避免 `dev` 中途壞掉）。每個 MR 都先寫測試、確認測試失敗，再寫功能（AGENTS.md 7.2）。MR 由永傑自己開；AI 只產出 MR 說明，存在 `docs/mr_info/<分支名稱>.md`。不修改 `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。

## 1. 前置確認

- [ ] 1.1 在群組告知新表名 `group_games`（4.4），驗證：沒有人提出撞名或反對
- [ ] 1.2 把本提案的情境表格給組員看過（7.2），驗證：至少一位組員確認

## 2. MR 1：遊戲清單 API（@ 立倫）

- [ ] 2.1 撰寫 repository 與 API 測試（`tests/core/test_games_list.py`，連 `_test` 資料庫）：列出並排序、中文搜尋、英文不分大小寫、`%` 與 `_` 被當成一般字元、沒有符合、分頁、分頁參數錯誤 422、JWT 未登入 401，驗證：測試存在且失敗
- [ ] 2.2 實作 `GameRepository.search_games`、`core/games/service.py`、`core/games/schemas.py`、`core/games/router.py`，在 `main.py` 掛載，驗證：2.1 全部通過，`/docs` 出現 `GET /api/v1/games`
- [ ] 2.3 自我檢查：`uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`，驗證：全部通過、CI 全綠

## 3. MR 2：揪團的店家與遊戲下拉選單（後端＋前端；@ 立倫、瑋鋐）

- [ ] 3.1 撰寫 migration 測試（`tests/migrations/test_group_games.py`）：升級後 `group_games` 存在且有中文說明、`groups.game_id` 已移除、既有資料搬移、遊戲刪除時對應被刪而揪團保留、降級還原第一款遊戲，驗證：測試存在且失敗
- [ ] 3.2 修改 service 與 API 測試：`game_ids` 多款與順序、空陣列、不存在 404 與 `details.game_ids`、重複 422、PATCH 取代與清除、只改其他欄位時遊戲不變、列表的 `games` 正確且不重複；把原本用 `game_id` 的測試改成 `game_ids`（契約變更，MR 說明寫理由），驗證：測試存在且失敗
- [ ] 3.3 實作 `models.py`（`GroupGame`）、migration（編號依當時 `dev`）、repository、service、schemas，驗證：3.1、3.2 全部通過
- [ ] 3.4 撰寫前端 state 與 widget 測試：店家清單載入、沒選店家、店家載入失敗與重試；遊戲搜尋（debounce）、選擇、多選順序、移除、排除已選、沒有結果；編輯帶入既有遊戲；送出的 `game_ids`；卡片與詳細頁顯示多款遊戲，驗證：測試存在且失敗
- [ ] 3.5 實作前端 `data/`（`ShopOption`、`GameOption`、`Group.games`、`listShops`、`searchGames`）、`state/`（`shopOptionsProvider`、遊戲搜尋、`GroupFormData.games`）、`pages/`（表單、卡片、詳細頁），刪除 `knownShopsProvider` 與兩個 ID 文字欄位，驗證：3.4 全部通過；grep 確認 `pages/` 沒有寫死的樣式
- [ ] 3.6 自我檢查：後端與前端的檢查全部通過；#39 合併後在瀏覽器手動走過開團（選店家、搜尋並選多款遊戲）、編輯、詳細頁，驗證：全部通過、CI 全綠

## Workflow follow-up

- 兩個 MR 都合併後，執行 `/opsx:archive`。
