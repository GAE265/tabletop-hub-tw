# Tasks

> 順序：先寫後端測試、再寫後端程式；前端等後端完成並經確認後再做。

## 1. 前置確認

- [ ] 1.1 從匯入的 `games.json` 查出《血與刃的白薔薇》的 `bgg_id`，記在 `game_definitions.py` 的註解。驗證：`bgg_id` 在 `games` 表中唯一對到該遊戲。
- [ ] 1.2 在群組告知三個表名 `matches`、`match_participants`、`match_turns`（4.4）。驗證：群組訊息已發出。
- [x] 1.3 確認 `uv run alembic heads` 只有一個 head（`0007`），新 migration `0008` 接在它後面。驗證：指令輸出。

## 2. 後端測試案例與測試程式（先於功能，7.2）

- [x] 2.1 產出 Draft MR 說明（存 `docs/mr_info/feature-matches-record.md`，依 `.github/pull_request_template.md`，情境表格對應 spec），由使用者貼到 Draft MR 並 @ 一位組員確認。驗證：檔案存在，表格每一行對應一個測試。
- [x] 2.2 寫 `backend/tests/migrations/test_matches_tables.py`：三張表與每個欄位的 comment 非空且為中文、`group_id` 外鍵參照 `groups.id` 且為 `SET NULL`、comment 為「所屬揪團；不一定屬於揪團」、揪團被刪除後這局仍在且 `group_id` 為空、約束（座位、帳號、回合編號重複）、多位無帳號可並存、`score`／`placement` 可為空、升級與降版。驗證：測試存在且目前失敗（不得 xfail／skip）。
- [x] 2.3 寫共用表讀取方法的測試：`GameRepository.get_game`、`BookingRepository.get_shop`、`AuthUserRepository.get_user`（存在與不存在）。驗證：測試存在且目前失敗。
- [x] 2.4 寫 `backend/tests/matches/fakes.py`（`FakeMatchesRepository`）與 service 單元測試：權限（有帳號的參加者／非參加者／admin）、覆蓋與競爭轉 409、結果覆蓋的確認清除、確認統計與 `is_valid`、`played_seat_numbers` 驗證、移除參加者的各種限制。驗證：測試存在且目前失敗。
- [x] 2.5 寫 `backend/tests/matches/test_api.py`，對應 spec 每個 scenario（開局、查詢、加入、回合、結果、確認、移除參加者）。驗證：每個 scenario 至少一個測試，目前失敗。

## 3. 後端實作

- [x] 3.1 新增共用表讀取方法（只讀不寫）：`GameRepository.get_game`、`BookingRepository.get_shop`（既有類別加方法）、新檔 `domains/auth/repository.py` 的 `AuthUserRepository.get_user`。驗證：2.3 的測試通過；MR 說明 @ 立倫、瑋鋐。
- [x] 3.2 新增 `domains/matches/models.py`（含 Enum 中文註解、表與欄位 comment）與 migration `0008`。驗證：2.2 的測試通過。
- [x] 3.3 新增 `game_definitions.py`（白薔薇的 `game_data` 模型、陣營 Enum）。驗證：`game_data` 缺欄位、負數、多餘欄位、型別錯誤、`played_seat_numbers` 為空／重複的測試通過。
- [x] 3.4 新增 `repository.py`、`schemas.py`、`service.py`（開局、加入、移除、記錄回合、覆蓋、記錄結果、確認、查詢與人數統計）。驗證：2.4 的 service 單元測試通過。
- [x] 3.5 新增 `router.py`，在 `main.py` 掛載（立倫的共用區；`tests/conftest.py` 的 TRUNCATE 用 CASCADE，不用改）。驗證：2.5 的 API 測試通過，`/docs` 看得到所有端點與錯誤格式。
- [x] 3.6 競爭情境：同一回合同時新增只會成功一筆；移除參加者與新增回合同時送出不會留下對不上的資料。驗證：對應 API 測試通過。
- [x] 3.7 後端自我檢查：在 `backend/` 跑 `uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`。驗證：全部通過。

## 4. 前端（後端完成並經使用者確認後才做）

- [ ] 4.1 寫 `frontend/test/support/fakes.dart` 的 `FakeMatchesRepository` 與 `matches` state 測試（對應 matches-record-prototype 的 scenario）。驗證：測試存在且目前失敗。
- [ ] 4.2 新增 `domains/matches/data/`（freezed DTO、`MatchesRepository`、`HttpMatchesRepository`，`snake_case` 對應）。驗證：`flutter analyze` 無問題。
- [ ] 4.3 新增 `domains/matches/state/`（載入、重新整理、各操作含移除參加者、「待確認覆蓋」與取消）。驗證：4.1 的測試通過。
- [ ] 4.4 新增 `prototypes/matches/` 參考畫面（開局含選座位、加入參加者、移除參加者、記錄回合含出牌座位、記錄結果、確認、覆蓋提示、載入中／沒有資料／錯誤），`app/router.dart` 加 `/proto/matches`（永傑的共用區）。驗證：以 `--dart-define=SHOW_PROTOTYPES=true` 手動跑一遍所有操作；沒有該參數時路由不存在。
- [ ] 4.5 撰寫 `docs/handoff/matches.md`（依 `_template.md`，含截圖）。驗證：每個操作都標明 `state/` 方法與後端 API。

## 5. 發 MR 前

- [ ] 5.1 前端在 `frontend/` 跑 `flutter analyze`、`flutter test`；後端再跑一次 3.7 的檢查。驗證：全部通過。
- [ ] 5.2 更新 `docs/mr_info/feature-matches-record.md`（@ 立倫：契約、共用區、`games`／`auth_users` 讀取方法；@ 瑋鋐：migration、`booking_shops` 讀取方法；@ 永傑：`router.dart`、`needs-ui` 標籤），由使用者自行貼上。驗證：表格每一行都有對應測試。

## Workflow follow-up

- MR 一律由組員自己開，AI 不開 MR、不改 MR 狀態（第 9 節）。
- 成就與天梯、其他遊戲的回合格式、`score`／`cooperative` 結果記法，另開 change。
