# 10：評估題組與詞彙表

Status: ready-for-human
Blocked by: 03、06、07、08、12
Spec: [spec](../../games-advisor/spec.md) §6、§15
MR: （還沒開）

## 要做什麼

在 `commands` 加上評估題組指令 `eval`，包含評審建議（spec §15.6：每張卡片多呼叫一次模型，檢查推薦理由有沒有寫出依據裡沒有的內容，不算分）。用 03、12 收的真資料照 spec §6 跑完心得管線，定案真的 `tag_vocabulary.json` 與 10 題 `eval_cases.json`，再用真的模型跑一次評估題組。

## 驗收條件

- [ ] 開 Draft MR，MR 說明列出情境表格（AGENTS.md §7.2、§7.4）
- [ ] spec §15.5、§15.6 的每一列都有測試而且通過
- [ ] 在本機照 spec §6 跑完匯入與心得管線；立倫編輯 `tag_vocabulary.json`、在標籤草稿上刪標籤
- [ ] 寫 10 題 `eval_cases.json`：AI 起草，立倫審核定稿（spec §15.2）
- [ ] 跑評估題組，把三種分數、token 用量與評審統計貼進 MR 說明（spec §15.4）。Demo 題沒過時，照 spec §16 的升級路徑處理
- [ ] 第一次跑完後，立倫對照評審建議和自己的勾選，把一致的張數寫進 MR 說明（spec §15.6）
- [ ] AGENTS.md §2 第 7 點的三項檢查通過
- [ ] 合併前把本檔與 12 的 `Status` 改成 `resolved`、`MR` 填上連結
