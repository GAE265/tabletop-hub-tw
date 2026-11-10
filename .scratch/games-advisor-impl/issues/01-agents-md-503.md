# 01：AGENTS.md §4.3 補上 503

Status: ready-for-human
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §18
MR: （還沒開）

## 要做什麼

§4.3 的錯誤狀態碼清單沒有 503。games_advisor 用 503 `GAMES_ADVISOR_UNAVAILABLE` 表示 Azure 暫時連不上，組員已在 2026-11-09 同意補上。AI 不改 AGENTS.md，由立倫親手修改並開 MR。

## 驗收條件

- [ ] 立倫親手在 AGENTS.md §4.3 的錯誤狀態碼加上 503
- [ ] MR 說明的情境表格寫「不適用」，理由是只改文件（AGENTS.md §7.4）
- [ ] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結
