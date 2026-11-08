# 09：前端與交接說明

Status: ready-for-agent
Blocked by: 無（截圖要等其他 ticket，見驗收條件）
Spec: [spec](../../games-advisor/spec.md) §14
MR: （還沒開）

## 要做什麼

做前端的 `data/`、`state/`、參考畫面 `/proto/games_advisor` 與交接說明，只依賴 spec §13 的 API 契約。不碰 `pages/` 與 `app/theme/`（AGENTS.md §5.4、§9）。

## 驗收條件

- [ ] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [ ] spec §14.2 的每一列都有測試而且通過
- [ ] AGENTS.md §2 第 7 點的前端檢查通過（`flutter analyze`、`flutter test`）
- [ ] MR 加 `needs-ui` 標籤，@ 永傑（參考畫面的路由改到永傑擁有的 `router.dart`）
- [ ] 交接說明附參考畫面的截圖。要等 06、07、08 合併，而且已經匯入真的桌遊、產生心得片段，才拍得到推薦卡片；不用等 10 的詞彙表
- [ ] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結
