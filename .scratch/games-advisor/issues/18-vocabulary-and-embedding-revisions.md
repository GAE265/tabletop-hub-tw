# 詞彙表改版或換 embedding 模型時怎麼處理

Type: grilling
Status: resolved
Blocked by: 09
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

「[心得怎麼變成標籤](09-review-to-tags-pipeline.md)」定了每款桌遊重跑就是覆蓋，但沒有處理兩種整批的變動：

1. 詞彙表改版：同步詞彙表時，檔案刪掉或改掉某個代碼，資料表裡已有的標籤與每款的標籤（`games_advisor_game_tags`）怎麼處理，例如連帶刪除、拒絕同步，或要求先重標。改版後要不要全部重標；要不要重新歸納詞彙表、什麼情況下重新歸納。
2. 換 embedding 模型或 `EMBEDDING_DIM`：心得摘要向量與心得片段向量都要重產。向量欄位是 `vector(EMBEDDING_DIM)`，維度改變時要新增 migration；重產期間推薦怎麼辦。
3. 要不要記錄資料庫裡的標籤與向量是哪一版詞彙表、哪個 embedding 模型產生的。

同步詞彙表指令的測試案例需要第 1 題的答案。

## Answer

2026-11-08 與立倫 grilling 定案（4 輪）。

**總覽**

- 詞彙表：repo 裡的 `tag_vocabulary.json` 是正本，同步就是讓資料表和檔案一致。檔案刪掉的代碼，桌遊上的標籤跟著刪掉；新代碼要重標才會出現在桌遊上。資料庫不記錄詞彙表版本。
- embedding：`games_advisor` 用自己的一組設定。每個向量記下產生它的模型，模型和目前設定不同就當作沒有向量。換模型就重跑兩個既有指令。
- 背景（立倫說明）：開發期間，立倫和組員各用自己的 LLM、embedding 模型與 PostgreSQL，可能各自有一個 Foundry project；最後可能整合成一個 Foundry，也可能維持多個 Foundry 與 PostgreSQL。設定分開，兩種結果都不用改程式。

**1. 同步詞彙表遇到變動（ticket 第 1 題）**

同步依代碼比對檔案和資料表：

| 檔案的變動 | 同步怎麼處理 | 之後要做的事 |
|---|---|---|
| 刪掉代碼 | 刪掉這個標籤，連帶刪掉所有桌遊上的這個標籤，印出哪幾款少了哪個標籤 | 不用重標 |
| 新增代碼 | 新增標籤，還沒有任何桌遊有它 | 印出提醒：重跑上標籤（15 款全部）並重做人工驗證 |
| 改代碼 | 當作刪掉舊代碼、新增新代碼（程式分不出改名和「刪一個、加一個」） | 同新增 |
| 只改名稱或定義 | 原地更新，桌遊上的標籤與信心分數都保留 | 印出「哪些定義改了，可以考慮重標」，由立倫判斷 |

- 程式不強制重標。重標時一律 15 款全部重跑；上標籤每次都產生全新草稿，人工驗證也全部重做。
- 「心得怎麼變成標籤」的格式檢查（代碼格式、不重複、名稱與定義不是空的、最多 30 個）照舊，有一項不符合就整份拒絕。
- 匯入標籤草稿時，草稿裡有詞彙表沒有的代碼（產生草稿之後詞彙表又同步過），就整份拒絕，要重跑上標籤。這和「草稿多出標籤、改了分數就整份拒絕」一致。
- 「查桌遊」工具參數的 enum（標籤、類別、機制、排除清單）每則玩家訊息都從資料庫讀一次。同步後下一則訊息就用新清單，不用重啟後端。
- 沒有採用的方案：
  - 拒絕同步，要先清掉桌遊上的標籤：還是要多一個刪除步驟。
  - 停用標籤：多一個欄位、多一種狀態要測。
  - 改定義就刪掉桌遊上的這個標籤、強制重標：改定義多半只是修措辭。
  - 有新增代碼就清空所有桌遊的標籤：重標完成前，推薦用不到任何標籤。
  - 匯入草稿時跳過詞彙表沒有的代碼。
  - 工具 enum 在後端啟動時讀一次：同步後忘了重啟，LLM 可能填已經刪掉的代碼。

**2. 什麼時候重新歸納詞彙表**

- 只在新增桌遊時考慮。補心得、改提示詞都不重新歸納。
- 上標籤的提醒（某個標籤 0 款使用，或 15 款中有 12 款以上使用）只當參考，不自動觸發。
- 歸納指令遇到檔案已存在會拒絕覆蓋，所以重新歸納要寫到另一個路徑，由立倫把要的標籤手動搬進 `tag_vocabulary.json`，走 MR。
- 沒有採用的方案：每次補心得都重新歸納；提醒累積到幾個就自動重新歸納。

**3. 評估題組和詞彙表的一致性**

- 加一個 pytest：評估題組 `backend/tests/games_advisor/eval_cases.json` 用到的每個代碼都在 `tag_vocabulary.json` 裡。兩個檔案都在 repo，改詞彙表卻忘了改題組的 MR，CI 不會通過。

**4. games_advisor 自己的 embedding 設定**

```
GAMES_ADVISOR_EMBEDDING_PROVIDER=  # fake | cloud；沒填就是 fake
GAMES_ADVISOR_EMBEDDING_ENDPOINT=
GAMES_ADVISOR_EMBEDDING_API_KEY=
GAMES_ADVISOR_EMBEDDING_MODEL=     # 部署名稱；也是記在每個向量上的模型名稱
GAMES_ADVISOR_EMBEDDING_DIM=       # 沒填就是 1536
```

- 五個欄位都分開，不退回全域的 `EMBEDDING_*`。組員與 CI 不用填，預設就是 fake。
- 全域的 `EMBEDDING_DIM` 保留不動（資料庫骨架的 spec 要求它存在），`games_advisor` 不讀它。
- 整合層的 factory 改成接收一組設定值（`EmbeddingConfig`），不自己讀設定，整合層仍然不知道 domain（AGENTS.md §4.2）。後端啟動時建一個給「查桌遊」用，批次指令各自建一個。
- 整合層提案不再新增全域的 `EMBEDDING_PROVIDER`、`EMBEDDING_ENDPOINT`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`，規則書 RAG 需要時由他們自己提。
- 理由：Foundry 只有立倫使用，金鑰不和組員共用（「確認可用的 Azure OpenAI 資源」）；組員開發時各用自己的資源，最後也不一定整合。共用全域設定時，全域 endpoint 填誰的資源都有問題，別人換模型也會影響推薦。
- 沒有採用的方案：全組共用一組 `EMBEDDING_MODEL`、`EMBEDDING_DIM`；只分開模型與維度，provider、endpoint、金鑰仍共用。

**5. 記錄產生向量的模型（ticket 第 3 題）**

- 心得摘要向量與心得片段都多存一欄，記下產生時的 `GAMES_ADVISOR_EMBEDDING_MODEL`，用 fake 時記 `fake`：`games_advisor_games.review_summary_embedding_model`、`games_advisor_review_excerpts.embedding_model`。
- 「查桌遊」遇到模型和目前設定不同的向量，當作沒有向量（心得摘要在相似度名次排最後、心得片段回空清單，「條件與偏好怎麼比對桌遊」已定），並寫一筆 warning log。
- 評估題組指令開始前，只檢查 `games_advisor` 的這兩種向量：有模型不同的就拒絕執行，印出是哪幾款，提醒照第 6 點重跑。其他 domain 的向量由各自負責（§4.2，repository 只查自己的資料表）。
- 記的是部署名稱。「專題專用 Foundry 要部署哪些模型」定了部署名稱和模型名稱相同；之後換到別的 Foundry，只要沿用這個命名就不用重產，名稱不同就當成換模型、要重跑。
- 沒有採用的方案：
  - 不記錄：large 換 small 都是 1536 維，只看維度偵測不到；換模型忘了重跑時，相似度排序亂掉卻查不出原因。
  - 模型不同就讓整則訊息失敗（503）。
  - 評估題組不檢查，只靠 warning log：分數偏低卻看不出原因，可能貼進 MR。

**6. 換模型與改維度（ticket 第 2 題）**

- 換模型：重跑「產生心得摘要」「產生心得片段」。心得摘要會跟著重寫（多 15 次 LLM 呼叫，約 NTD 20），心得片段由程式切，只多 embedding 費用。不另寫「只重算向量」的子指令。
- 改維度：建立向量欄位的 migration 從 `GAMES_ADVISOR_EMBEDDING_DIM` 讀維度，不寫死數字（AGENTS.md §4.4）。真的要改維度時，再新增一個 migration：清空兩種向量（心得片段整列刪掉，重跑時重新產生）、改欄位維度，然後重跑上面兩個指令。這個 migration 現在不寫：large 縮成 1536 維，換成 small 也是 1536 維。
- 重產期間不用特別處理：照第 5 點，還沒重產的桌遊當作沒有向量，推薦照常回傳，也不會拿新舊模型的向量混著比。

**術語**：`GLOSSARY.md` 不變。

**留給其他 ticket 的事**

- [整合層提案](../integrations-proposal.md)：已改第 4、6.2、7、9、11.1 節（factory 接收 `EmbeddingConfig`、`GAMES_ADVISOR_EMBEDDING_*`、出入第 5 點）。
- 「[需要整合層提供哪些介面](12-integrations-interface.md)」、「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」：embedding 的設定名稱改成 `GAMES_ADVISOR_EMBEDDING_*`，寫在各自的 Comments。
- 「[LLM 設定也改成 games_advisor 自己的一組嗎](19-games-advisor-llm-settings.md)」（新 ticket）：同樣的理由也適用 `LLM_*`。
- `spec.md`：同步的四種變動與提醒文字、匯入草稿的代碼檢查、工具 enum 每則訊息讀取、評估題組與詞彙表的 pytest、兩個模型欄位與「查桌遊」的過濾、評估指令的檢查、`GAMES_ADVISOR_EMBEDDING_*` 設定、改維度的做法。

## Comments

- 2026-11-08（來自「[需要整合層提供哪些介面](12-integrations-interface.md)」）：換 embedding 模型就是改 `EMBEDDING_MODEL`，維度變了就一起改 `EMBEDDING_DIM`。整合層只檢查向量長度等於 `EMBEDDING_DIM`，不知道資料庫裡的向量是哪個模型產生的；要不要記錄模型、怎麼偵測不一致，在這張決定。
- 2026-11-08（來自「[怎麼驗收推薦結果](14-recommendation-acceptance.md)」）：評估題組（`backend/tests/games_advisor/eval_cases.json`）用詞彙表代碼指定標籤；詞彙表刪掉或改掉代碼時，題組檔也要跟著改。
- 2026-11-08（來自「[專題專用 Foundry 要部署哪些模型](17-foundry-model-deployments.md)」）：embedding 選 `text-embedding-3-large`，帶 `dimensions=1536`，`EMBEDDING_DIM=1536`。之後如果換成 small，維度一樣是 1536，向量欄位不用改；但兩個模型的向量不能混用，全部都要重產。只看維度偵測不到換了模型。
- 2026-11-08 grilling 進行中（第 1 輪）：同步詞彙表時檔案少了代碼，就連帶刪除所有桌遊上的這個標籤並印出清單；改代碼視為刪舊加新；只改名稱或定義時原地更新、標籤留著，印出「可以考慮重標」；只在新增桌遊時才考慮重新歸納詞彙表；加 pytest 檢查評估題組用到的代碼都在 `tag_vocabulary.json`；換 embedding 模型就重跑「產生心得摘要」「產生心得片段」，不另寫指令；兩種向量都記錄產生時的 `EMBEDDING_MODEL`，查桌遊時模型不同就當作沒有向量並寫 warning log；建立向量欄位的 migration 從設定讀 `EMBEDDING_DIM`，改維度時再新增 migration 清空向量、改欄位，現在不寫。
- 2026-11-08 grilling 進行中（第 2 輪）：新增代碼時同步只印提醒，重標一律 15 款全部重跑、人工驗證重做；標籤草稿有詞彙表沒有的代碼時匯入整份拒絕；資料庫不記錄詞彙表版本；工具參數的 enum 每則訊息從資料庫讀，同步後不用重啟。待定：立倫提出合併到同一個資料庫後，其他 domain 的資料表可能用不同的 embedding 模型，評估題組指令的檢查範圍與 `EMBEDDING_MODEL` 是否全組共用要重新考慮。
- 2026-11-08 grilling 進行中（第 3 輪）：立倫的意思是合併進同一個資料庫後，其他 domain 的資料表可能用不同的 embedding 模型。定案：games_advisor 用自己的一組 embedding 設定，和規則書 RAG 分開（不共用全域 `EMBEDDING_MODEL`、`EMBEDDING_DIM`）；評估題組指令開始前只檢查 games_advisor 的心得摘要向量與心得片段向量，模型和目前設定不同就拒絕執行並印出是哪幾款。待定：分開哪些設定欄位、整合層提案怎麼改、預設值。
