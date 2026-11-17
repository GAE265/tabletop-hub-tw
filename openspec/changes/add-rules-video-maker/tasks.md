# Tasks

> 依序完成 4 個 MR（design.md D11）。每個 MR 都先寫測試、確認測試失敗，再寫功能（AGENTS.md 7.2）。MR 由永傑自己開（第 9 節規定 AI 不得開 MR）；AI 只依 `.github/pull_request_template.md` 產出 MR 說明，並附上情境表格（7.4）。不修改 `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。

## 1. 前置確認

- [ ] 1.1 在組內決定 `integrations/tts`、`storage`、`video` 的擁有者，並由組員更新 AGENTS.md 第 3 節（design.md Open Questions 1），驗證：AGENTS.md 已列出擁有者
  - 註記（2026-11-17）：組內同意三個資料夾由永傑負責。待有權限的組員更新 AGENTS.md 第 3 節後打勾。
- [ ] 1.2 決定雲端儲存與 TTS 服務、是否新增 `azure-storage-blob`、旁白的聲音（Open Questions 2、3），驗證：結論記在本檔
  - 註記（2026-11-17）：組內同意 TTS 用 Azure AI Speech（REST，用既有的 `httpx`）、儲存用 Azure Blob Storage（新增 `azure-storage-blob`）、合成用 ffmpeg（執行環境安裝 ffmpeg 與 Noto Sans TC）。旁白的聲音尚未決定（由 `TTS_VOICE` 設定，不影響程式）。
- [x] 1.3 確認組內自製的 3 支影片是否也放到同一個雲端儲存（Open Questions 4），結論同步到 `add-rules-qa` design.md D9，驗證：兩份 design.md 一致
  - 結論（2026-11-17）：自製影片放 YouTube；本 change 的 mp4 存在雲端儲存，`rules_qa_videos.source` 區分兩種來源，播放器依來源自動切換（mp4 用 `video_player`，在本 change 新增）。
- [x] 1.4 在群組告知新表名（4.4），驗證：沒有人提出撞名或反對
  - 註記：2026-11-17 已告知，沒有人反對。
- [ ] 1.5 等 `add-rules-qa` MR 1 合併（`rules_qa_videos`、`rules_ingest` 頁面讀取方法），驗證：`dev` 上有 `backend/app/domains/rules_qa/`

## 2. MR 1：`integrations/tts`、`storage`、`video`（@ 瑋鋐、立倫）

- [ ] 2.1 永傑開 Draft MR 1，AI 從 `specs/media-integrations` 整理情境表格，驗證：Draft MR 已存在
- [ ] 2.2 撰寫 fake 與介面行為的測試（`tests/integrations/test_tts_fakes.py`、`test_storage_fakes.py`、`test_video_fakes.py`）與 factory 測試（缺少設定時的錯誤訊息），驗證：測試存在且失敗
- [ ] 2.3 撰寫 external 測試（雲端 TTS、雲端儲存、ffmpeg 實際合成），加上 `@pytest.mark.external`，缺少設定時直接失敗並說明缺哪個設定，驗證：`uv run pytest` 不執行它們
- [ ] 2.4 實作三個介面、fake、`local` 儲存、雲端與 ffmpeg 實作與 factory；`.env.example` 加上欄位名與說明，驗證：2.2 通過；本機 `uv run pytest -m external` 的結果寫進 MR 說明
- [ ] 2.5 自我檢查：`uv run ruff check .`、`uv run ruff format --check .`、`uv run pytest`，驗證：全部通過、CI 全綠，再改成 Ready for review

## 3. MR 2：後端影片製作 API（於 MR 1 合併後從 dev 開分支；@ 立倫、瑋鋐）

- [ ] 3.1 永傑開 Draft MR 2，AI 從 `specs/rules-video-maker` 整理情境表格，驗證：Draft MR 已存在
- [ ] 3.2 撰寫 migration 測試（三張表、外鍵、`status` 的 CHECK、編號唯一、可以 downgrade），驗證：測試存在且失敗
- [ ] 3.3 撰寫 service 單元測試（fake LLM、TTS、儲存、合成器、repository、規則書來源）：涵蓋 `specs/rules-video-maker` 每個情境，包含狀態轉換、建立者與 admin 的權限、用語改寫、素材補齊、合成成功與失敗、逾時視為失敗、發布取代既有影片，驗證：測試存在且失敗
- [ ] 3.4 撰寫 API 測試（連 `_test` 資料庫，使用 `as_player`、`as_shop_staff`、`as_admin`），每個端點至少有成功與失敗案例各一，驗證：測試存在且失敗
- [ ] 3.5 實作 models、migration、repository、prompts、service、schemas、router 與背景合成，在 `main.py` 建立 provider，驗證：3.2–3.4 全部通過，`/docs` 列出 6 個 rules-videos 端點
- [ ] 3.6 自我檢查（同 2.5），MR 標明有改契約、含 migration，驗證：全部通過、CI 全綠，再改成 Ready for review

## 4. MR 3：前端 data、state、參考畫面與交接說明（於 MR 2 合併後）

- [ ] 4.1 永傑開 Draft MR 3，AI 從 `specs/rules-video-maker-page` 整理情境表格，驗證：Draft MR 已存在
- [ ] 4.2 撰寫 state 測試（`FakeRulesVideoRepository`、可控制時間的輪詢）：入口權限、已有／沒有規則書、腳本修改與驗證、確認、上傳與失敗、還有素材沒拍、合成輪詢到成功與失敗、離開時停止輪詢、發布與取代提醒，驗證：測試存在且失敗
- [ ] 4.3 實作 `data/`、`state/`，驗證：4.2 通過
- [ ] 4.4 實作 `prototypes/rules_video/`，註冊 `/proto/rules_video`，驗證：後端以 dev 模式（fake TTS、`local` 儲存、本機 ffmpeg）手動走完一支影片
- [ ] 4.5 撰寫 `docs/handoff/rules_video.md`（附截圖），驗證：涵蓋範本所有欄位
- [ ] 4.6 自我檢查：`flutter analyze`、`flutter test`，加上 `needs-ui` 標籤，驗證：全部通過、CI 全綠

## 5. MR 4：正式頁面（於 MR 3 合併後）

- [ ] 5.1 撰寫 widget 測試：路由、入口只對店家人員與管理員顯示、每個狀態對應的畫面、RWD，驗證：測試存在且失敗
- [ ] 5.2 實作 `pages/`，只使用 `state/` 與 `app/theme/`，驗證：5.1 通過，grep 沒有寫死的樣式
- [ ] 5.3 註冊正式路由與入口，依 5.4 刪除 `/proto/rules_video`，驗證：`flutter test` 全部通過
- [ ] 5.4 自我檢查並在 Chrome 手動檢查手機與桌機寬度，驗證：全部通過、CI 全綠

## Workflow follow-up

- 四個 MR 都合併後，執行 `/opsx:archive`。
- 任務佇列、規則書太長時的分段摘要、背景音樂與轉場，之後另開 change。
