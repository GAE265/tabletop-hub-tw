# Design

## Context

- 規格：根目錄 `影片生產器規格.md` 的產品流程 1–6。1d 的原始範圍（見已歸檔的 `add-rules-video-maker` proposal）：API、資料表、前端精靈、發布、OCR 或從 `rules_ingest` 讀規則書、部署設定。
- 引擎（命令列）都以「資料夾」運作：`video.json`、`assets/`、`cache/`（段影片、旁白）、`out/`、`revisions/`。
- 已有、可沿用：
  - `rules_ingest`（瑋鋐）：照片 → Vision OCR → `games_manual` 每頁 Markdown；`shop_staff`、`admin` 可用；有前端頁面。
  - `integrations/storage`：`put`／`get`／`delete`，有本機（`STORAGE_LOCAL_DIR`）與雲端兩種實作。
  - 前端：`core/platform/image_picker.dart`（file_picker，手機上可以選相機）、`lesson_video_player.dart`（只支援 YouTube）。
- **沒有**：背景工作的機制、進度回報、手機上標區域的方式。

## Goals / Non-Goals

**Goals**：檢查點前，店員只用手機完成「上傳規則書 → 草稿 → 拍素材、標區域 → 產生 → 看」；長時間工作離開頁面再回來仍看得到進度與結果；失敗時說得出原因與下一步。

**Non-Goals**：見 proposal「這階段不做」與「檢查點之後再決定」。

## Decisions（2026-11-21 永傑確認 Q1–Q8）

**D1 影片專案（`rules_qa_video_projects`）。** 一個專案＝一章（Q4）。
- MR 1 的欄位：`id`（UUID）、`game_id`、`shop_id`、`created_by`、`chapter_number`（≥ 1）、`chapter_title`（1–50 字，去掉前後空白後不可為空）、`created_at`、`updated_at`。
- 本章頁、參考頁、段資料等欄位**等 MR 4 用到時再加**（2026-11-21 永傑決定：沒有寫入也沒有測試的欄位，審核看不出設計對不對；段資料欄位會決定資料庫與 `video.json` 誰是正本，要在 MR 4 一起決定）。
- **`step`（目前步驟）不存欄位，由其他狀態推出**。MR 1 沒有其他狀態，固定回 `pages`（上傳規則書）；之後的 MR 依草稿、素材、工作的狀態推出 `draft`、`assets`、`render` 等值，加值時在該 MR 寫明推導規則。
- 建立：店員的店家用登入身分的 `shop_id`，body 帶別家店回 403；管理員必須帶 `shop_id`（沒帶 422，店家不存在 404）。
- **同一間店、同一款遊戲、同一章可以建立多個專案**（2026-11-21 永傑決定）：例如重拍一版或比較兩份草稿，不加唯一限制。
- 列表：`page`（≥ 1）、`page_size`（1–100，預設 20），依 `updated_at` 由新到舊；回 `{items, total}`。
- 權限：`shop_staff` 只能存取自己店的專案（別家店的回 404，不透露存在）；`admin` 全部；`player` 403；沒登入 401。

**D2 非同步工作（`rules_qa_video_jobs`，MR 2；2026-11-21 永傑確認）。** 草稿（含涵蓋檢查）、產生影片、修改一律做成工作（Q7）：
- **kind**：`draft`（產生草稿）、`render`（產生影片）、`revise`（用一句話修改）。處理函式分別在 MR 4、MR 8、MR 10 接上；MR 2 只做機制，用測試裡的假處理函式驗證。
- **狀態**：`queued`（等待）→ `running`（處理中）→ `succeeded`（完成，結果在 `result`）或 `failed`（失敗，原因在 `error`）。`succeeded`、`failed` 不再改變；重試＝建立新工作。
- **欄位**：`id`、`project_id`、`kind`、`status`、`progress`（0–1）、`message`（現在在做什麼）、`error`（給店員看）、`error_detail`（給開發者看：例外類型與訊息，最多 2000 字，不在 API 回傳）、`result`（JSONB）、`created_by`、`created_at`、`started_at`、`finished_at`。
- **同時兩個工作回 409**：部分唯一索引保證同一個專案 `queued`／`running` 最多一筆；寫入違反時回 409 `RULES_VIDEO_JOB_RUNNING`，`details` 附進行中的工作 id。由資料庫保證，兩個請求同時送進來也只有一個成功。
- **卡死的工作的出口**：建立新工作時，同專案 `running` 且 `started_at` 超過 **30 分鐘**的工作先標為 `failed`（「工作逾時，已中止」），再建立新的。未超時的仍回 409。逾時中止後，原本的執行緒若之後才做完，也不會改寫它的狀態（結束與回報進度都只更新 `running` 的工作）。
- **處理函式必須設逾時**：MR 4、MR 8、MR 10 的處理函式呼叫 LLM、TTS、ffmpeg 時都必須設逾時（LLM 用 `LLM_TIMEOUT_SECONDS`；ffmpeg 子程序要加上限），不能依賴 30 分鐘的出口。
- **背景執行緒**：後端啟動時開一個執行緒（FastAPI lifespan），關閉時停止；`RULES_VIDEO_WORKER=false` 不啟動。每次取一個最早的 `queued` 工作（`FOR UPDATE SKIP LOCKED`），同時改成 `running`。建立工作時通知執行緒立刻取，平常每 2 秒檢查一次。處理函式用 `report(進度, 說明)` 回報，每次用獨立的短交易寫入。
- **伺服器重新啟動**：啟動時、執行緒開始前，把 `running` 的工作標為 `failed`（「伺服器重新啟動，工作中斷，請重新開始」）；`queued` 保留繼續做。**已知限制**：假設後端只有一個程序。
- **例外的記錄**：處理函式拋出例外時，(1) 伺服器 log 用 `logger.exception` 記下工作 id、kind 與堆疊；(2) `error`：拋出 `JobFailed("…")` 用那句話，其他例外用「發生未預期的錯誤，請重試；若持續發生請通知管理員」；(3) `error_detail`：例外類型與訊息。寫入失敗結果時本身又出錯，只記 log，執行緒繼續；那個工作停在 `running`，30 分鐘後由上面的出口釋放。沒有對應 kind 的處理函式：`failed`（「這種工作還沒有實作」）。
- **API**：`GET /rules-videos/{id}/jobs`（新的在前、分頁）、`GET /rules-videos/{id}/jobs/{job_id}`；權限同專案。建立工作的 API 在 MR 4、MR 8、MR 10（建立時回 202）。

**D3 規則書頁面。** 沿用 `rules_ingest` 的上傳與 OCR，不另做。草稿工作從 `games_manual` 讀店員選的本章頁與參考頁（`read_manual_pages`）。`games_manual` 沒有語言欄位，頁面的 `lang` 一律記為 `zh`（之後需要再加設定）。

**D4 用語對照表（`rules_qa_video_terms`）。** 每款遊戲一份（Q5 b）：`game_id`（主鍵）、`terms`（JSONB，格式同 `terms.json`：`en`、`zh`、`key`、`avoid`、`category`）、`updated_at`。
- `PUT /api/v1/games/{game_id}/video-terms`：只有 `admin`，上傳 JSON，用 `load_terms` 的規則驗證（格式錯回 422）。
- 草稿工作有對照表就帶入，沒有就不帶，並在草稿結果註明「沒有用語對照表」。

**D5 存放（Q1）。** 本機磁碟，中間隔一層存放介面：
- 素材照片、成品影片：透過 `integrations/storage`（本機實作，`STORAGE_LOCAL_DIR`）；之後要換雲端只換設定。
- 工作資料夾（展開的 `video.json`、素材、段影片與旁白快取、`out/`）：放在設定的本機目錄 `RULES_VIDEO_WORK_DIR/<專案 id>/`，由一個小的工作區介面（`integrations/storage` 內）取得路徑，之後可以換實作。快取保留，才能「只重做受影響的段」。
- **保留期限與是否刪除不在這階段決定**（涉及規則書內容，AGENTS.md 2.2，永傑與團隊討論）。相關 MR 的說明列出選項與後果：例如「發布後刪素材照片」「N 天後刪快取（之後修改要全部重做）」「刪專案時一併刪除」。

**D6 素材上傳與區域（Q3 a）。**
- 每個素材一張照片：上傳、換一張、旋轉（0／90／180／270）。
- 有區域的素材：在照片上用手指拖出矩形，一次一個區域，可以拖角落微調；座標存成相對比例 `[x, y, 寬, 高]`（與 `video.json` 相同）。
- **開工前先做小實驗**確認精準度（tasks 1.3）。
- 必拍素材都有照片、區域都有座標之前，「產生影片」回 422 並列出缺什麼。

**D7 進度回報。** `render_video` 加一個進度回呼（`integrations/video`）：排版、旁白（第幾句）、段影片（第幾段／共幾段，沿用快取的直接跳過）、疊進度條、混音。工作的 `progress`、`message` 依此更新。

**D8 播放（Q8）。** 成品 mp4 由後端提供網址；前端加 `video_player` 套件，`lesson_video_player.dart` 補上 `file` 來源。

**D9 手機版面。** 單欄、按鈕在拇指範圍、斷點用 `core/layout/`；專案頁顯示「目前在哪一步、下一步做什麼」；進行中的工作顯示進度與說明；失敗時顯示哪一步失敗、原因、可以做什麼。直接做正式頁面（`pages/`），不另做參考畫面。

**D10 驗收環境（Q2）。** 永傑的電腦跑後端與網頁，手機連同一個 Wi‑Fi；身分用開發模式的店員帳號（`X-Dev-User`）。需要：後端與網頁綁定區網位址、CORS 允許手機來源、網頁的 `API_BASE_URL` 指向電腦的區網位址；伺服器上的 ffmpeg 與字型沿用本機的設定。

## Risks / Trade-offs（依嚴重程度）

1. **[手機上拖框不夠準]** → 開工前先做小實驗；不夠準就回來討論（加放大、或換做法）。
2. **[工作會被伺服器重新啟動中斷]** 已知限制。→ 失敗時說明原因，可以重試；快取保留，重試時已完成的段不重做。
3. **[手機照片品質]** OCR 錯字帶進草稿；素材反光、歪斜（第 4 階段才偵測）直接出現在影片。→ 店員在步驟 1、4 看得到結果並可以重拍。已知限制。
4. **[檢查點前不能在手機上用一句話修改草稿]** → 用「重新產生草稿」（沿用照片與區域）。修改頁是檢查點之後一定要做的 MR。已知限制。
5. **[LLM 費用與時間]** → 一個專案同時只有一個工作；工作紀錄留存。

## Open Questions

- 檢查點後：伺服器部署要不要做、怎麼做（永傑到時決定）。手機修改頁一定要做。
- 保留期限與是否刪除（永傑與團隊討論，D5）。
