# 06：三個一般請求的端點、權限、30 分鐘清除

Status: resolved
Blocked by: 03
Spec: [spec](../../host/spec.md) §2、§11
MR: [#68](https://github.com/GAE265/tabletop-hub-tw/pull/68)

## 要做什麼

`host` 的 `router.py`、`schemas.py`、`service.py`，以及在 `main.py` 掛路由。

1. 三個端點（spec §11.1）：
   - `POST /api/v1/hosting-sessions`：開一場主持。
   - `GET /api/v1/hosting-sessions`：列出自己還保留著的主持（0 或 1 筆）。
   - `POST /api/v1/hosting-sessions/{id}/connections`：拿一次性通行碼；帶不同的 `turn_taking_mode` 就是切換接話方式。
2. `session` 的欄位三個端點共用（spec §11.2）。
3. 一次性通行碼：60 秒內有效、只能用一次、只對那一場主持有效。這張做發出與核對的方法；真的拿它連 WebSocket 在 [07](07-websocket-and-relay.md)。
4. 權限寫在 `service`（spec §2.2）：三種角色都能開；只有開的人與管理員能拿通行碼，別人回 403 `PERMISSION_DENIED`。
5. 一個人同一時間只有一場：再開一場，舊的直接清掉，不回 409（spec §2.1）。
6. 清掉的時機：沒有任何裝置連著滿 30 分鐘，或已結束滿 30 分鐘。清掉時連圖裡的整局記憶一起清。時間用可以控制的假時鐘測。
7. 一場主持只在後端記憶體，不建資料表，沒有 `repository.py` 與 `models.py`（spec §1）。
8. 錯誤碼 `HOST_SESSION_NOT_FOUND`（spec §11.5）。

## 要動的檔案

- `backend/app/domains/host/router.py`、`schemas.py`、`service.py`（新）
- `backend/app/main.py`（掛路由；`dev` 的 `groups` 也改過這裡，留意位置）
- `backend/tests/host/`

## 動到別人的地方

無。`main.py` 與 `core/` 的擁有者是立倫。這張改了 API 契約，PR 說明照 AGENTS.md §8.1 要 @ 系統整合主責，也就是立倫自己。

## 驗收條件

- [x] 先 commit 會失敗的測試，再 commit 功能（AGENTS.md §7.2）
- [x] spec §11.6 的 A-01 到 A-18 每一行都有測試而且通過
- [x] spec §9 的 M-08、M-09 有測試而且通過
- [x] 「沒有權限」的測試用 `as_player`、`as_shop_staff`、`as_admin`（AGENTS.md §4.5）
- [x] `service` 沒有 import FastAPI；`router` 沒有商業邏輯（AGENTS.md §4.2）
- [x] 沒有新增 migration
- [x] AGENTS.md §2 第 7 點的後端三項檢查通過
- [x] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`

## Comments

- 2026-11-22：做完，沒有新增 migration。
- 2026-11-22：改了一個自己剛寫的測試（AGENTS.md §7.5 要寫理由）：`test_service` 的 `test_list_shows_current_position` 期望值數錯了。從開場按 4 次下一步，會經過開局準備、夜晚第一步、夜晚第二步，到第 1 回合階段 1；原本寫成階段 2。同一張的 API 測試（A-08）算的是對的。
- 2026-11-22：切換接話方式的做法：拿通行碼時帶了不同的 `turn_taking_mode`，回應裡的 `session` 先給新的值，通行碼記著它；真的切換發生在裝置用這張通行碼連上的時候。所以別人拿不到通行碼，也就改不了（A-13）。
- 2026-11-22：`main.py` 多了主持的接線（查規則接 `rules_qa` 的只檢索方法、思考模型接 `integrations/llm`）。寫在 `main.py` 是為了讓 `host` 不必 import `rules_qa` 的 `repository`（AGENTS.md §4.2）。
