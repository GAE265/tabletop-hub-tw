# RAG 教材有哪些可以重用

Type: research
Status: resolved
Map: [桌遊推薦 Agent + 桌遊 RAG](../map.md)

## Question

依教材表格 `團隊專題/99_其他/RAG/games_advisor-rag-materials.md` 的路徑讀檔（排名前面的先讀），並參考影片教材 `團隊專題/99_其他/RAG/README.md` 與 `補充知識.md`，回答：

1. 哪些做法適合 games_advisor：從多輪對話擷取條件與偏好、用心得產生標籤、條件篩選加向量搜尋、重排序、推薦理由附出處、推薦品質評估。
2. 哪些程式碼可以改寫進 `backend/`。每段寫出原始路徑與要改什麼。改寫後要符合 AGENTS.md §4：domain 不得直接 import 模型廠商 SDK，資料庫用同步 SQLAlchemy 加 pgvector。
3. 哪些不要用，以及原因，例如依賴 LangChain 或課程服務、依賴 Notebook 全域狀態、用 FAISS 而非 pgvector。

結果寫在 git 外：`團隊專題/99_其他/RAG/games_advisor-rag-reuse.md`。教材屬於私人課程內容，不得寫進 repo；本檔的 Answer 只寫結論摘要，不貼教材原文。

## Answer

完整結果在 git 外：`團隊專題/99_其他/RAG/games_advisor-rag-reuse.md`（含逐項路徑、要改的地方，以及教材表格不準的列）。

1. **適合的做法**
   - 條件與偏好存成有型別的對話狀態，每輪只擷取有變動的欄位，再由程式合併。
   - 標籤用固定詞彙表，以結構化輸出擷取。
   - 先用 SQL 篩選條件，再依向量距離排序。
   - 推薦理由用證據編號引用心得，由 service 檢查引用是否都在提供的範圍內。
   - 驗收時，條件滿足率和偏好命中率分開計算。
   - 重排序：教材只有 Cross-Encoder 示範，只能參考概念。
2. **可改寫的程式**：都只取骨架。要拿掉 LangChain、廠商 SDK 和全域狀態，再拆進 service、repository、integrations。最值得用的三段：
   - 結構化擷取（`04_running_state.ipynb` 的 `RExtract`，搭配 aidev-030 講輸出結構的頁面）：改用 Azure 的 strict JSON schema，只保留「失敗重試一次」。
   - `rag-demo-main/vector_store.py` 的 `search`：改成同步 SQLAlchemy 加 pgvector 的 cosine distance 排序；資料表為空時回空清單；零向量要在 embedding 層擋掉（原程式會把 NaN 排到第一名）。
   - `rag-with-citations_引用來源信度.py` 的 `ask()`：證據編號對應到心得 ID；「沒有候選」改由 SQL 查無結果判斷，不用未校準的相似度門檻。
3. **不用的部分**：LangChain、NVIDIA 課程端點、FAISS 的 pickle 索引、把向量庫當對話記憶、Notebook 全域狀態、Gradio 與 LangServe、Firestore／Cosmos／File Search，以及 domain 直接 `import openai`。

**留給其他 ticket 的事**

- Azure 部署是否支援 strict schema：在「確認可用的 Azure OpenAI 資源」確認。
- 結構化輸出的介面名稱（研究中暫稱 `generate_structured`）：在「需要整合層提供哪些介面」和瑋鋐談定。
