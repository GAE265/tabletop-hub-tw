# spec：桌遊資料與心得管線

Type: task
Status: resolved
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

## Answer

2026-11-08 完成，立倫確認結案。前半寫在 [spec.md](../spec.md)。

**spec 前半的內容**

- 共用部分：目的與需求 2 的說明段落、術語（引用 `GLOSSARY.md`）、4 張資料表的欄位與型別、`.env` 設定總覽、程式常數、檔案總覽。
- 桌遊資料與心得管線：執行順序、批次指令的共用規則、7 個子指令各自的規則與 §7 表格、`reviews.json` 後端讀哪些欄位、向量的共用規則、repository 與 migration 的測試。
- 新定的格式：`games.json`、`tag_vocabulary.json`、標籤草稿，以及歸納詞彙表兩次 LLM 呼叫的輸出。
- `game` 物件的欄位名稱跟著桌遊資料表（〔API〕留給 spec 定的）。

**寫 spec 時發現的缺漏，立倫的決定**（詳見 Comments）

| 題目 | 決定 |
|---|---|
| Q1 「設定值」放哪裡 | 程式常數。本機改值不用 MR，合併進 `dev` 仍走 MR（AGENTS.md §8.1） |
| Q2 類別、機制怎麼存 | 桌遊資料表的 `text[]` 欄位 |
| Q3 輸入檔格式錯 | 整份拒絕 |
| Q4 0 篇心得的桌遊重跑 | 清空舊的心得摘要、心得片段、標籤；沒帶 `--bgg-id` 時處理全部桌遊 |
| Q5 匯入標籤草稿跟什麼比 | 上標籤多寫一份原始檔 |
| Q6 心得摘要怎麼測模型出錯 | 不改整合層提案；重試邏輯共用、在上標籤測；摘要只測 embedding 出錯時舊資料保留 |
| Q7 `tag_vocabulary.json` 位置 | `backend/app/domains/games_advisor/` |
| Q8 9 條小細節 | 全部照預設：指令模組 `commands`、子指令名稱、結束碼 0/1/2 等 |

**留給其他 ticket 的事**

- 「[spec：推薦對話與 API](21-spec-conversation-and-api.md)」：沿用資料表與設定總覽；信心門檻、每款片段數、RRF 的 k 是程式常數（spec §4.2）；「查桌遊」的向量過濾、評估題組開始前的檢查、評估題組與詞彙表一致的 pytest。
- 「[把 spec 拆成 TDD 實作 ticket](22-split-spec-into-tdd-tickets.md)」：4 張表的 migration 怎麼分 MR。

## Comments

- 2026-11-08 寫 spec 時發現的缺漏（spec 裡標「待確認 Qn」）。每題附 AI 助理的建議，等立倫決定：
  - **Q1 「設定值」放哪裡**：標籤數上限 30、信心門檻 0.5、片段長度 4 個值、每款片段數 2、RRF 的 k。前面 ticket 都叫「設定值」，沒說放程式常數還是 `.env`。建議：程式常數，集中在 games_advisor 一個檔案；改值走 MR，評估題組的分數才比得起來。
  - **Q2 類別、機制怎麼存**：建議放在桌遊資料表的 `text[]` 欄位。另一個做法是另開兩張表，15 款用不到。
  - **Q3 輸入檔格式錯時**（`games.json`、`reviews.json`）：建議整份拒絕、什麼都不寫，和同步詞彙表、匯入標籤草稿一致。另一個做法是只跳過錯的那款。
  - **Q4 0 篇心得的桌遊重跑時**：上一次的心得摘要、心得片段、標籤要清空還是保留。建議清空，符合「重跑就是覆蓋」，作者要求刪除心得時，刪掉 `reviews.json` 那篇再重跑就清乾淨。
  - **Q5 匯入標籤草稿「只有刪除」跟什麼比**：「心得怎麼變成標籤」沒說基準。建議上標籤多寫一份不要動的原始檔，匯入時比對。
  - **Q6 心得摘要的測試**：要測重試與跳過，但提案的 `FakeLLMProvider.generate` 只回固定文字、不能照腳本拋例外。建議提案的 fake 加 `generate` 的腳本參數（和 `json_outputs`、`responses` 同一套）。其他做法：測試裡自己寫小的子類別；摘要改用 `generate_json`。
  - **Q7 `tag_vocabulary.json` 放哪裡**：建議 `backend/app/domains/games_advisor/tag_vocabulary.json`，和讀它的程式放一起。
  - **Q8 小細節照 AI 助理的預設寫**：
    1. 指令模組 `app.domains.games_advisor.commands`，子指令 `import-games`、`summarize-reviews`、`build-excerpts`、`draft-vocabulary`、`sync-vocabulary`、`draft-tags`、`import-tags`、`eval`。
    2. 結束碼：0 全部完成、1 沒有完成、2 部分完成（有款被跳過）。
    3. `--bgg-id` 可以給多個。
    4. `games.json`：11 個欄位必填、不接受其他欄位；人數、時長至少 1，年齡至少 0。
    5. 片段長度：中文算字元數（不含空白），英文算單字數；在不超過上限的最後一個「。！？」或「. ! ?」後面切，沒有句號就照上限切；整篇太短就保留 1 段。
    6. 心得摘要的字數不由程式檢查。
    7. 詞彙表草稿不做同步的格式檢查，由同步把關。
    8. 上標籤：草稿路徑已存在就拒絕；詞彙表是空的就拒絕；熱門標籤的提醒門檻寫成「已匯入桌遊數的 80% 以上」；跳過清單與提醒印在終端機。
    9. 同步詞彙表整份在一個交易裡完成。
- 2026-11-08 立倫決定 Q1–Q6（已寫進 spec）：
  - Q1：程式常數。立倫希望改值不用走 MR；本機改常數做實驗不用 MR，但合併進 `dev` 仍要走 MR（AGENTS.md §8.1 不准直接推 `dev`）。
  - Q2：桌遊資料表的 `text[]` 欄位。
  - Q3：輸入檔格式錯就整份拒絕。
  - Q4：0 篇心得的桌遊重跑時清空舊的心得摘要、心得片段、標籤；所以沒帶 `--bgg-id` 時處理資料庫裡全部桌遊。
  - Q5：上標籤多寫一份原始檔，匯入時比對。
  - Q6：不改整合層提案。立倫問「使用者不會觸發，還要測模型連不上嗎」：規則沒要求（§7.5 只管 API）。重試與跳過寫成共用函式，在上標籤測一次；心得摘要只用 embedding 拋錯測「失敗時舊資料保留」。
  - Q7、Q8：立倫要先釐清。
- 2026-11-08 立倫決定 Q7、Q8（已寫進 spec）：
  - Q7：`backend/app/domains/games_advisor/tag_vocabulary.json`。
  - Q8：9 條全部照 AI 助理的預設。spec 補上對應的測試案例：`games.json` 拼錯欄位、時長 0；片段沒有句號、整篇太短；同步到一半失敗整份回滾；上標籤遇到草稿已存在、詞彙表是空的。
