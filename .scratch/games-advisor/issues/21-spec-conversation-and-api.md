# spec：推薦對話與 API

Type: task
Status: open
Blocked by: 20
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

接著「[spec：桌遊資料與心得管線](20-spec-data-and-review-pipeline.md)」寫好的前半，把推薦對話與 API 的決定寫進 `.scratch/games-advisor/spec.md`，清楚到能直接寫出 AGENTS.md §7 的「情境／操作／預期結果」表格。資料表與設定欄位沿用前半的總覽，不重寫。

範圍與來源（讀各張的 Answer；Comments 只在 Answer 引用時才讀）：

| 範圍 | 來源 |
|---|---|
| 「查桌遊」工具：參數、enum 每則訊息讀資料庫、SQL 篩條件、RRF 排序、心得片段、向量模型不同時當作沒有向量 | 「[條件與偏好怎麼比對桌遊](10-matching-strategy.md)」、「[詞彙表改版或換 embedding 模型時怎麼處理](18-vocabulary-and-embedding-revisions.md)」 |
| 對話 service：對話規則、三道護欄、放寬條件、離題 | 「[Agent 怎麼追問、什麼時候推薦](07-conversation-flow.md)」、[ADR 0002](../../../docs/adr/0002-games-advisor-llm-driven-conversation-flow.md) |
| 最終回覆：structured outputs、推薦理由、丟掉無效的推薦、固定文字 | 「[推薦理由要寫什麼、要不要附出處](11-recommendation-reasons.md)」 |
| API：`POST /api/v1/advisor/messages`、錯誤碼、`response_id` 規則、沒設定模型時回 503 | 「[API 契約與 prototype 頁面](13-api-contract-and-prototype.md)」、「[LLM 設定也改成 games_advisor 自己的一組嗎](19-games-advisor-llm-settings.md)」、[ADR 0001](../../../docs/adr/0001-games-advisor-conversation-state-in-azure.md) |
| 前端：`data/`、`state/`、`prototypes/`、交接說明 `docs/handoff/games_advisor.md` | 「API 契約與 prototype 頁面」、`prototypes/api-contract.html` |
| 評估題組指令、`eval_cases.json` | 「[怎麼驗收推薦結果](14-recommendation-acceptance.md)」 |
| 模型、推理強度、逾時、前端等待上限 | 「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」 |
| 整合層 | [整合層提案](../integrations-proposal.md)：引用第 11 節的表格，不重抄 |

規則：

- 較晚的 ticket 會更正較早的，以 map 的 Decisions so far 標示的更正為準。
- 每條規則註明出自哪張 ticket。
- 不重新決定已定案的事。發現衝突或缺漏，寫在本張 Comments 問立倫，不自己選。

完成條件：

- service、router、前端 `state/` 都有 §7 表格。API 端點至少成功、失敗各一個案例（§7.5）；權限照「API 契約與 prototype 頁面」：三種角色都能用、未登入 401。
- service 的表格用假的 repository 與 `FakeLLMProvider`、`FakeEmbeddingProvider` 的腳本寫得出來（§7.5）。
- 立倫看過 spec 的這一半。

## Comments
