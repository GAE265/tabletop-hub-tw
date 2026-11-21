# 13：店家沒有推薦的桌遊時顯示提示

Status: claimed
Blocked by: PR [#73](https://github.com/GAE265/tabletop-hub-tw/pull/73)（店家管理：`shop_games` 資料表與 `shops` domain）
Spec: [spec](../../games-advisor/spec.md) §19
MR:

## 要做什麼

玩家從某間店進到桌遊推薦頁（網址帶 `shop_id`）時，推薦 Agent 推薦的桌遊如果那間店的庫存沒有，就在那張推薦卡片顯示「這間店目前沒有這款桌遊」。沒帶店家時和原本一樣，沒有提示。

- 後端：`POST /api/v1/advisor/messages` 的請求多一個選填的 `shop_id`，每張卡片多一個 `in_stock`。由程式查庫存，不經過 LLM。
- 前端：`/games-advisor?shop_id=<店家 id>`，`data/`、`state/` 與正式頁面一起改（立倫 2026-11-21 決定直接改正式頁面）。
- 訂位頁進到推薦頁的按鈕不在這張的範圍。

## 驗收條件

- [ ] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [x] spec §19.4 的每一列都有測試而且通過
- [x] AGENTS.md §2 第 7 點的檢查通過（後端三項、前端兩項）
- [x] `docs/handoff/games_advisor.md` 補上 `shop_id`、`in_stock` 與提示文字
- [ ] MR 說明 @ 永傑（改了正式頁面與 `app/router.dart`）
- [ ] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結
