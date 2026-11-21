# 06：三個一般請求的端點、權限、30 分鐘清除

Status: ready-for-agent
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

- [ ] 先 commit 會失敗的測試，再 commit 功能（AGENTS.md §7.2）
- [ ] spec §11.6 的 A-01 到 A-18 每一行都有測試而且通過
- [ ] spec §9 的 M-08、M-09 有測試而且通過
- [ ] 「沒有權限」的測試用 `as_player`、`as_shop_staff`、`as_admin`（AGENTS.md §4.5）
- [ ] `service` 沒有 import FastAPI；`router` 沒有商業邏輯（AGENTS.md §4.2）
- [ ] 沒有新增 migration
- [ ] AGENTS.md §2 第 7 點的後端三項檢查通過
- [ ] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`
