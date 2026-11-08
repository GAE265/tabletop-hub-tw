# spec：桌遊資料與心得管線

Type: task
Status: open
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

新建 `.scratch/games-advisor/spec.md`，把桌遊資料與心得管線的決定整理進去，清楚到能直接寫出 AGENTS.md §7 的「情境／操作／預期結果」表格。「[spec：推薦對話與 API](21-spec-conversation-and-api.md)」接著寫後半。

spec 開頭先寫全篇共用的部分：目的、術語（引用 `GLOSSARY.md` 的提案區，不另外定義）、資料表總覽、設定欄位總覽。

範圍與來源（讀各張的 Answer；Comments 只在 Answer 引用時才讀）：

| 範圍 | 來源 |
|---|---|
| 桌遊基本資料：repo 外的 JSON、匯入指令、資料表與欄位 | 「[收錄哪些桌遊、存哪些欄位](06-game-coverage-and-fields.md)」、「[桌遊基本資料從哪裡取得](02-game-data-sources.md)」 |
| 心得：repo 外的 `reviews.json`、心得片段的欄位 | 「[心得來源走哪條路](16-review-source-decision.md)」 |
| 標籤詞彙表：`tag_vocabulary.json`、歸納指令、同步的四種變動 | 「[標籤詞彙表怎麼定](08-tag-vocabulary.md)」、「[詞彙表改版或換 embedding 模型時怎麼處理](18-vocabulary-and-embedding-revisions.md)」 |
| 心得管線：上標籤、人工驗證草稿與匯入、心得摘要、心得片段、每款一個交易 | 「[心得怎麼變成標籤](09-review-to-tags-pipeline.md)」 |
| 向量：`GAMES_ADVISOR_EMBEDDING_*`、記下產生向量的模型、改維度的做法、向量放哪張資料表 | 「詞彙表改版或換 embedding 模型時怎麼處理」、「[條件與偏好怎麼比對桌遊](10-matching-strategy.md)」 |
| 批次指令共用規則：複製 settings 換掉三個值、`LLM_PROVIDER=fake` 時拒絕執行、逾時 300 秒 | 「[LLM 設定也改成 games_advisor 自己的一組嗎](19-games-advisor-llm-settings.md)」、「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」 |
| 整合層的設定欄位 | [整合層提案](../integrations-proposal.md)第 7 節 |

規則：

- 較晚的 ticket 會更正較早的，以 map 的 Decisions so far 標示的更正為準。
- 每條規則註明出自哪張 ticket。
- 不重新決定已定案的事。發現衝突或缺漏，寫在本張 Comments 問立倫，不自己選。
- 不寫心得原文、抓取的資料、真實的資源名稱或金鑰（AGENTS.md §2.1、§2.2）。

完成條件：

- 每個後端指令、repository 都有 §7 表格：正常情況、輸入錯誤或缺少欄位、狀態衝突（有的話）。指令在本機執行、沒有權限問題，就寫「不適用」並說明。
- 資料表的欄位、型別、主鍵（UUID）、命名都符合 AGENTS.md §4.4；向量維度從設定讀。
- 立倫看過 spec 的這一半。

## Comments
