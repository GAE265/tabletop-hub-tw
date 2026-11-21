# 規則書匯入後自動建立索引實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 參考匯入畫面完成一批頁面上傳後，建立該遊戲的 `rules_qa_chunks` 並顯示索引結果。

**Architecture:** 新增 `POST /api/v1/rules-lessons/{game_id}/index`，由 `rules_qa` service 驗證店員／管理員權限並呼叫既有 `build_index`。前端沿用 `RulesQaRepository` 呼叫端點；匯入 state 在頁面上傳完成後索引一次，畫面顯示處理狀態、段落數及可重試錯誤。

**Tech Stack:** FastAPI、SQLAlchemy、Flutter、Riverpod、Dio。

**Spec:** `docs/superpowers/specs/2026-11-20-rules-ingest-auto-index-design.md`

## Global Constraints

- Domain 之間只能呼叫對方的 service，不直接使用對方 repository 或 models。
- router 解析請求、驗證身分並呼叫 service；不得放商業邏輯。
- service 不 import FastAPI，權限不符回 403。
- 前端頁面不直接呼叫 API；操作放在 state，測試 fake 集中於 `frontend/test/support/fakes.dart`。
- 規則書已入庫頁面在索引成功前不回滾；索引錯誤需讓使用者能辨識並重試。

## Review Focus

- 部分頁面上傳失敗：依已成功入庫頁面建索引，保留頁面匯入結果。
- 所有頁面上傳失敗：不建立索引，畫面保留匯入錯誤。
- 沒有可索引文字：顯示後端錯誤，不清除原索引。
- embedding 服務錯誤：不回報成功，允許重新索引。
- 非店員／管理員呼叫端點：回 403，不變更 chunks。

---

### Task 1: 後端索引 API

**Files:**
- Modify: `backend/app/domains/rules_qa/router.py`
- Modify: `backend/app/domains/rules_qa/service.py`
- Modify: `backend/tests/rules_qa/test_api.py`
- Modify: `backend/tests/rules_qa/test_service.py`

**Interfaces:**
- Produces: `POST /api/v1/rules-lessons/{game_id}/index`，成功回 `{ "chunk_count": <int> }`。
- Service 接收 `CurrentUser` 與 `game_id`，檢查 `shop_staff`／`admin`，使用既有頁面讀取 service、embedding provider 與 `build_index`；端點不得由 router 直接執行索引邏輯。

- [ ] 先新增 API/service 測試，涵蓋成功段落數、未授權、遊戲不存在、無頁面與 embedding 失敗。
- [ ] 以既有 `build_index` 實作 service 索引方法，只有索引完整成功時回傳段落數。
- [ ] 在 router 掛載端點並回傳 `chunk_count`。
- [ ] 執行後端相關測試與 lint/format 檢查。

### Task 2: 前端匯入後自動索引

**Files:**
- Modify: `frontend/lib/domains/rules_qa/data/rules_qa_repository.dart`
- Modify: `frontend/lib/domains/rules_ingest/state/manual_pages_state.dart`
- Modify: `frontend/lib/prototypes/rules_ingest/rules_ingest_proto_page.dart`
- Modify: `frontend/test/support/fakes.dart`
- Modify: `frontend/test/domains/rules_ingest/manual_pages_state_test.dart`
- Modify: `frontend/test/domains/rules_ingest/manual_pages_widget_test.dart`

**Interfaces:**
- Consumes: 後端 Task 1 的索引端點。
- Produces: `RulesQaRepository.indexRulebook(int gameId) -> Future<int>`，回傳 chunk 數。

- [ ] 在 fake 與 widget/state 測試先涵蓋全成功、部分成功、全失敗、索引失敗與重試。
- [ ] 實作 repository API 呼叫與匯入 state 的單次索引流程；僅在至少一頁成功匯入時觸發。
- [ ] 畫面顯示索引中、完成段落數及失敗訊息，錯誤時提供再次執行索引的操作。
- [ ] 執行前端相關測試與 `flutter analyze`。

### Task 3: 更新交接說明

**Files:**
- Modify: `docs/handoff/rules_ingest.md`

- [ ] 說明整批匯入後會自動建立問答索引、部分匯入與索引失敗時畫面行為。
- [ ] 對照實作確認操作與提示文字一致。
