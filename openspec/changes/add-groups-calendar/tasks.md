# Tasks

> 依序完成 3 個 MR（design.md D12）。每個 MR 都先寫測試、確認測試失敗，再寫功能（AGENTS.md 7.2）。MR 由永傑自己開（第 9 節規定 AI 不得開 MR）；AI 只依 `.github/pull_request_template.md` 產出 MR 說明，並附上情境表格（7.4）。不修改 `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。

## 1. 前置確認

- [ ] 1.1 在群組告知新表名 `groups`、`group_members`（4.4），驗證：沒有人提出撞名或反對（若組內希望避開 `groups` 這個名稱，在 2.x 開始前改名，見 design.md 的 Risks）
- [ ] 1.2 與瑋鋐、立倫確認共用表的讀取方式（design.md D7）與店家清單 API（D8）由誰新增，驗證：結論記在本檔的「1.2 結論」註記
- [ ] 1.3 從最新的 `dev` 開分支 `feature/groups-api`（目前的 `feature/groups-calendar` 只放這份 OpenSpec 提案，可以併入 MR 1），驗證：分支存在

## 2. MR 1：後端 API 與 migration（@ 立倫、瑋鋐）

- [ ] 2.1 永傑開 Draft MR 1，AI 從 `specs/groups` 整理情境表格供貼上，驗證：Draft MR 已存在，並 @ 立倫、瑋鋐
- [x] 2.2 撰寫 migration 測試（`tests/migrations/test_groups_tables.py`）：升級後兩張表存在、UUID 主鍵有預設值、外鍵、(`group_id`, `user_id`) 唯一、CHECK 限制、可以 downgrade，驗證：測試存在且失敗，沒有使用 skip 或 xfail
- [x] 2.3 撰寫 service 單元測試（`tests/groups/test_service.py`，使用 `FakeGroupsRepository`，固定 `now()`）：開團時開團主自動成為成員、額滿進候補與候補順位、重複報名、已取消或已結束、退出後遞補、候補退出、開團主不能退出、移除他人的權限、修改權限（開團主、admin、他人、店家人員）、`capacity` 調低成 409 與調高自動遞補、`ended` 的計算，驗證：測試存在且失敗
- [x] 2.4 撰寫 API 測試（`tests/groups/test_api.py`，連 `_test` 資料庫，使用 `as_player`、`as_shop_staff`、`as_admin` 與 `jwt_client`）：涵蓋 `specs/groups` 每個 API 情境的狀態碼、錯誤代碼與回應格式，同時搶最後一個名額的情境用兩個 session 驗證，驗證：測試存在且失敗，且每個端點至少有成功與失敗案例各一
- [ ] 2.5 依 1.2 的結論，取得或新增共用表的讀取方法（店家、使用者名稱、遊戲）；若由永傑代為新增，該檔案的修改在 MR 說明 @ 擁有者，驗證：`groups` 沒有自行建立共用表的 model 或 repository
  - 註記：1.2 尚未確認。目前採 design.md D7 的備案：`groups/repository.py` 以唯讀查詢 JOIN `booking_shops`、`auth_users`、`games` 取得名稱與是否存在，沒有建立共用表的 model 或 repository。待擁有者回覆後決定是否改呼叫他們的方法，因此本項維持未完成。
- [x] 2.6 新增 `app/domains/groups/models.py` 與 migration `0003_groups_tables.py`（版本號依當時 `dev` 的最新 migration 決定），驗證：2.2 的測試全部通過
- [x] 2.7 實作 `repository.py`（含 `FOR UPDATE` 鎖、列表聚合與篩選）、`service.py`、`schemas.py`、`router.py`，在 `main.py` 掛載 router，並在 `tests/conftest.py` 的 `TRUNCATE` 加上兩張新表，驗證：2.3、2.4 的測試全部通過，`/docs` 列出 7 個 groups 端點
  - 註記：`tests/conftest.py` 不需修改：`db` fixture 的 `TRUNCATE auth_users, booking_shops CASCADE` 會連帶清空 `groups`、`group_members`。只改了 `main.py` 掛載 router，另外在 `migrations/env.py` 匯入 groups 的 models。
- [ ] 2.8 自我檢查：在 `backend/` 跑 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`，驗證：全部通過、CI 全綠；MR 標明有改契約、含 migration，再改成 Ready for review
  - 註記：本機 `ruff check`、`ruff format --check`、`pytest`（441 passed）已通過；CI 與 MR 狀態待永傑開 MR 後確認。

## 3. MR 2：前端 data、state、參考畫面與交接說明（於 MR 1 合併後從 dev 開分支）

- [ ] 3.1 永傑開 Draft MR 2，AI 從 `specs/groups-calendar-page` 整理情境表格，驗證：Draft MR 已存在
- [ ] 3.2 撰寫 state 測試（`test/domains/groups/`，在 `test/support/fakes.dart` 新增 `FakeGroupsRepository`，用 Riverpod override 替換）：當月載入與每日團數、UTC+8 跨日、切換月份、今天、超過 100 團的分頁載入、開團主篩選與場數、當日列表排序與名額狀態文字、報名／候補／退出／取消揪團的成功與失敗、操作進行中不能重複送出、表單驗證、後端錯誤訊息，驗證：測試存在且失敗
- [ ] 3.3 實作 `domains/groups/data/`（freezed DTO、`GroupsRepository`、`HttpGroupsRepository`），並執行 `dart run build_runner build --delete-conflicting-outputs`，驗證：`flutter analyze` 沒有錯誤
- [ ] 3.4 實作 `domains/groups/state/`（`GroupsCalendarNotifier`、`GroupDetailNotifier`、`GroupFormNotifier`，以及目前使用者 id 的 provider），驗證：3.2 的測試全部通過
- [ ] 3.5 實作 `prototypes/groups/`（只用 Flutter 預設元件，做出所有按鈕、欄位與載入中、沒有資料、錯誤三種狀態），並在 `app/router.dart` 註冊 `/proto/groups`，驗證：後端以 dev 模式啟動並已 seed，手動走過開團、報名、額滿候補、退出遞補（用身分切換器換人）、取消揪團
- [ ] 3.6 撰寫 `docs/handoff/groups.md`（依 `_template.md`，附參考畫面截圖），驗證：涵蓋範本所有欄位
- [ ] 3.7 自我檢查：在 `frontend/` 跑 `flutter analyze`、`flutter test`，驗證：全部通過、CI 全綠；加上 `needs-ui` 標籤後改成 Ready for review

## 4. MR 3：正式月曆頁（於 MR 2 合併後從 dev 開分支）

- [ ] 4.1 撰寫 widget 測試：`/groups` 路由存在、未開啟 `SHOW_PROTOTYPES` 時沒有 `/proto/groups`、寬度 < 600 時上下排列、>= 1024 時左右並排，驗證：測試存在且失敗
- [ ] 4.2 實作 `domains/groups/pages/`（月曆、當日列表、詳細資料、開團與編輯表單），只使用 `groups/state/` 與 `app/theme/`，不寫死顏色、字級、間距，驗證：4.1 的測試通過；用 grep 確認 `pages/` 沒有 `Color(0x`、`EdgeInsets.all(數字)`、`fontSize:` 這類寫死的數值
- [ ] 4.3 在 `app/router.dart` 註冊 `/groups`，並在畫面框架加上入口；依 5.4 刪除 `/proto/groups` 路由，驗證：`flutter test` 全部通過
- [ ] 4.4 自我檢查：在 `frontend/` 跑 `flutter analyze`、`flutter test`，並在 Chrome 手動檢查手機與桌機寬度，驗證：全部通過、CI 全綠，再改成 Ready for review

## Workflow follow-up

- 每個 MR 都經至少一位其他組員審核、CI 全綠後，才合併回 `dev`。
- 三個 MR 都合併後，執行 `/opsx:archive`。
- 地區篩選等瑋鋐在 `booking_shops` 加上地區欄位後，另開 change。
