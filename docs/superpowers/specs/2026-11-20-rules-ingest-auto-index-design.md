# 規則書匯入後自動建立問答索引

## 意圖

在 `/#/proto/rules-ingest` 完成一批規則書頁面匯入後，立即為該遊戲建立 `rules_qa_chunks`，讓規則問答可以直接檢索新匯入內容。

## 目標與範圍

- 全部頁面匯入完成後，前端呼叫一次後端索引 API。
- 後端沿用現有 `build_index`：讀取該遊戲所有已入庫頁面、切段、產生 embedding，並以交易取代該遊戲舊索引。
- 參考畫面呈現索引處理中、成功段落數或失敗原因。
- 匯入失敗的頁面不阻止索引已成功匯入的頁面；若沒有可索引內容，顯示明確錯誤。

## 不在範圍

- 不改正式規則問答頁面或規則書入庫流程的 API 契約。
- 不在每張圖片上傳後重建索引；整批操作結束後只重建一次。
- 不改 embedding 模型設定與 chunk 切分方式。

## 方案

1. **建議：批次匯入結束後呼叫索引 API。** 保留現有逐頁匯入 API，新增 `rules_qa` 索引端點，由參考畫面整批匯入完成後呼叫一次。貼合目前 UI 的批次操作，避免逐頁重複產生 embedding。
2. 在每次後端單頁匯入後自動索引。會讓多頁上傳重複索引部分資料，增加耗時與 embedding 成本，因此不採用。

## 設計決策

- 索引端點由 `rules_qa` 提供，並在 service 層檢查店員或管理員權限；不讓 `rules_ingest` 直接依賴 `rules_qa` repository/model。
- 前端在所有頁面上傳操作結束後呼叫端點，將建立的段落數與匯入結果一同呈現。
- 索引失敗不回滾已完成的頁面匯入；畫面明確提示可重試索引。

## 預計修改檔案

- `backend/app/domains/rules_qa/router.py`
- `backend/app/domains/rules_qa/service.py`
- `backend/tests/rules_qa/test_api.py` 與相關 service 測試
- `frontend/lib/domains/rules_qa/data/rules_qa_repository.dart`
- `frontend/lib/domains/rules_ingest/state/manual_pages_state.dart`
- `frontend/lib/prototypes/rules_ingest/rules_ingest_proto_page.dart`
- `frontend/test/support/fakes.dart` 與 rules_ingest state/widget 測試
- `docs/handoff/rules_ingest.md`（若存在，補上操作行為）

