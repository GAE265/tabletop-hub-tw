# 詞彙表改版或換 embedding 模型時怎麼處理

Type: grilling
Status: open
Blocked by: 09
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

「[心得怎麼變成標籤](09-review-to-tags-pipeline.md)」定了每款桌遊重跑就是覆蓋，但沒有處理兩種整批的變動：

1. 詞彙表改版：同步詞彙表時，檔案刪掉或改掉某個代碼，資料表裡已有的標籤與每款的標籤（`games_advisor_game_tags`）怎麼處理，例如連帶刪除、拒絕同步，或要求先重標。改版後要不要全部重標；要不要重新歸納詞彙表、什麼情況下重新歸納。
2. 換 embedding 模型或 `EMBEDDING_DIM`：心得摘要向量與心得片段向量都要重產。向量欄位是 `vector(EMBEDDING_DIM)`，維度改變時要新增 migration；重產期間推薦怎麼辦。
3. 要不要記錄資料庫裡的標籤與向量是哪一版詞彙表、哪個 embedding 模型產生的。

同步詞彙表指令的測試案例需要第 1 題的答案。

## Comments

- 2026-11-08（來自「[需要整合層提供哪些介面](12-integrations-interface.md)」）：換 embedding 模型就是改 `EMBEDDING_MODEL`，維度變了就一起改 `EMBEDDING_DIM`。整合層只檢查向量長度等於 `EMBEDDING_DIM`，不知道資料庫裡的向量是哪個模型產生的；要不要記錄模型、怎麼偵測不一致，在這張決定。
