# 09：前端的 core/platform 四個介面、data、state

Status: ready-for-agent
Blocked by: 01
Spec: [spec](../../host/spec.md) §14.1、§14.2、§14.3、§14.5、§14.7
MR: [#68](https://github.com/GAE265/tabletop-hub-tw/pull/68)

## 要做什麼

只依賴 spec §11、§12 的 API 契約，可以和後端的 02 到 07 同時做。不碰 `pages/` 與 `app/theme/`（AGENTS.md §5.4、§9）。

1. `frontend/lib/core/platform/` 加四個介面（spec §14.1）：收音、播音、螢幕常亮、頁面看不看得見。各有網頁的實作與給測試用的 fake。直接用瀏覽器的 API，不新增音訊套件。做法參考 [Flutter Web 怎麼收音與即時播音](../../host/issues/05-flutter-web-audio.md)與原型 [`.scratch/host/prototypes/`](../../host/prototypes/)。
   - 行不通時先停下來回報，不自己加 `record` 或 `flutter_sound`。
2. `frontend/lib/domains/host/data/`（spec §14.2）：三個一般請求的 DTO 與 repository；WebSocket 的通道，收送二進位與 JSON 訊息。`web_socket_channel` 改成直接宣告。
3. `frontend/lib/domains/host/state/`（spec §14.3）：一個控制器，方法照那一節的表。收到 `flush` 要停播並丟掉舊那一段的聲音；一段播完要送 `playback_done`。
4. 提醒的狀態（spec §14.5）：這張做出每一種狀況的狀態值；字句放在哪裡由畫面決定，在 [10](10-prototype-handoff-and-live-checks.md)。
5. fake repository 與 fake 通道放 `frontend/test/support/fakes.dart`（AGENTS.md §7.5）。

## 要動的檔案

- `frontend/lib/core/platform/`（四個新介面）
- `frontend/lib/domains/host/data/`、`frontend/lib/domains/host/state/`（新）
- `frontend/pubspec.yaml`、`frontend/pubspec.lock`
- `frontend/test/support/fakes.dart`、`frontend/test/domains/host/`、`frontend/test/core/`

## 動到別人的地方

- `frontend/lib/core/platform/`：加四個介面。擁有者永傑。PR 說明要寫原因並 @ 永傑（AGENTS.md §2 第 3 點）。
- `frontend/pubspec.yaml`：`web_socket_channel` 改成直接宣告，PR 說明要寫理由（AGENTS.md §2 第 4 點）。

## 驗收條件

- [ ] 先 commit 會失敗的測試，再 commit 功能（AGENTS.md §7.2）
- [ ] spec §14.7 的 U-01 到 U-20 每一行都有測試而且通過
- [ ] 只能在網頁上用的程式都在 `core/platform/` 的介面後面，`domains/host/` 沒有直接 import 瀏覽器的 API（AGENTS.md §5.3）
- [ ] 前端沒有任何阿里雲的設定與金鑰（AGENTS.md §5.3）
- [ ] 沒有新增音訊套件
- [ ] `flutter analyze`、`flutter test` 通過
- [ ] 做完的最後一個 commit 把本檔的 `Status` 改成 `resolved`
