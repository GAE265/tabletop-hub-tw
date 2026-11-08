# 04：整合層介面與 fake

Status: ready-for-agent
Blocked by: 無
Spec: [spec](../../games-advisor/spec.md) §4.1、§17
MR: （還沒開）

## 要做什麼

照[整合層提案](../../games-advisor/integrations-proposal.md)做 `integrations/llm`、`integrations/embedding` 的新介面、例外與 fake，讓後面的 MR 不用 Azure 就能寫測試。同時加上 spec §4.1 的設定欄位，後端啟動時多建一個 games_advisor 的 embedding provider。雲端實作留給 08。

## 驗收條件

- [ ] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [ ] 提案 §11.1–§11.3 的每一列都有測試而且通過。§11.1 中需要雲端實作的 4 列除外（見 08）
- [ ] `.env.example` 只寫欄位名與說明（AGENTS.md §2.1）
- [ ] AGENTS.md §2 第 7 點的三項檢查通過
- [ ] MR @ 瑋鋐（整合層擁有者）
- [ ] 合併前把本檔的 `Status` 改成 `resolved`、`MR` 填上連結
