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

**D1 影片專案（`rules_qa_video_projects`）。** 一個專案＝一章（Q4）。欄位（草案）：`id`（UUID）、`game_id`、`shop_id`、`created_by`、`chapter_number`、`chapter_title`、`chapter_pages`、`reference_pages`、`video`（JSONB，`video.json` 的內容，含 `state`、`revisions`）、`created_at`、`updated_at`。
- 權限：`shop_staff` 只能存取自己店的專案（別家店的回 404，不透露存在）；`admin` 全部；`player` 403。

**D2 非同步工作（`rules_qa_video_jobs`）。** 草稿（含涵蓋檢查）、產生影片一律做成工作（Q7）：
- `POST` 建立工作，回 202 與工作 id；前端每幾秒查一次 `GET .../jobs/{id}`。
- 欄位（草案）：`id`、`project_id`、`kind`（draft｜render）、`status`（queued｜running｜succeeded｜failed）、`progress`（0–1）、`message`、`error`（店員看得懂的中文與下一步）、`result`（JSONB）、時間。
- 同一個專案同時只能有一個進行中的工作，否則 409 `RULES_VIDEO_JOB_RUNNING`。
- 後端程式內一個背景執行緒依序執行；不需要新套件、不加服務。
- **已知限制**：伺服器重新啟動會中斷工作。啟動時把 running 的工作標成 failed（「伺服器重新啟動，請重試」），可以重新建立。

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
