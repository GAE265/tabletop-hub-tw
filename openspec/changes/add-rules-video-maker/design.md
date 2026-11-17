# Design

## Context

- `add-rules-qa` 新增 `rules_qa_videos`（一款遊戲一支教學影片，只存網址與標題）與規則問答；本 change 讓店家自己產生影片並發布到這張表。
- 規則書由 `rules_ingest`（瑋鋐）逐頁入庫到 `games_manual`；`rules_qa` 透過它的 service 讀取頁面（`add-rules-qa` design.md D4）。
- 使用者決定：影片用「照片＋AI 旁白＋字幕」自動合成；說明書沿用規則書入庫，**這款遊戲已有規則書時以規則書為主，不用重拍**；先用文字跟店員確認腳本，再依腳本要求實體素材。
- 目前 `integrations/` 只有 `llm`、`embedding`、`ocr`、`mqtt`，沒有語音、檔案儲存、影片處理。後端也還沒有部署用的容器映像設定。

## Goals / Non-Goals

**Goals:**
- 店員只需要確認文字、拍配件照片，就能得到可發布的教學影片。
- 腳本內容只根據規則書，用語依 AGENTS.md 10.2。
- 所有外部服務包在 `integrations/` 介面後面，domain 測試不需要金鑰、不需要 ffmpeg。

**Non-Goals:**
- AI 生成動態畫面、運鏡、轉場特效、背景音樂。
- 手動剪輯或調整時間軸。
- 多語言旁白；玩家使用影片生產器。
- 正式環境的任務佇列（本次用背景執行，見 D6）。

## Decisions

**D1 放在 `rules_qa` domain。**
影片生產器的產出就是 `rules_qa` 的教學影片，發布時寫入 `rules_qa_videos`，放在同一個 domain 不需要跨 domain 呼叫。AGENTS.md 第 3 節沒有對應的新 domain，若組內認為應該獨立成 domain，要由組員先修改 AGENTS.md。

**D2 說明書沿用 `rules_ingest`，以規則書為主。**
建立專案時先讀規則書頁面：有就直接產生腳本；沒有就回 409 `RULES_VIDEO_NO_RULEBOOK`，前端引導店員用 `rules_ingest` 既有的逐頁匯入 API 拍說明書，完成後再建立專案。影片生產器不自己做 OCR，入庫的規則書也同時給規則問答使用。

**D3 資料表。**

`rules_qa_video_projects`：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | uuid，主鍵 | |
| `game_id` | bigint，外鍵 `games.id`（不 cascade） | 這支影片教哪一款遊戲 |
| `created_by` | uuid，外鍵 `auth_users.id` | 建立專案的店家人員 |
| `status` | text，CHECK in (`script_draft`, `collecting_materials`, `rendering`, `ready`, `failed`, `published`) | 目前進行到哪一步 |
| `video_key` | text，可為空 | 完成影片在檔案儲存的 key；`ready` 以後才有 |
| `error_message` | text，可為空 | 合成失敗的原因；`failed` 時才有 |
| `rendering_started_at` | timestamptz，可為空 | 開始合成的時間，用來判斷是否卡住 |
| `created_at`、`updated_at` | timestamptz | |

`rules_qa_video_sections`：`id`（uuid）、`project_id`（外鍵，cascade：段落屬於專案）、`section_number`（從 1 開始，與 `project_id` 唯一）、`title`、`narration`。

`rules_qa_video_materials`：`id`（uuid）、`project_id`（外鍵，cascade）、`material_number`（從 1 開始，與 `project_id` 唯一）、`section_number`、`description`、`photo_key`（可為空，空值代表還沒上傳）。

若 AGENTS.md 1.10 已合併，每張表與欄位都加上 `comment=`，`status` 的每個值也寫中文註解。

**D4 腳本與素材清單用 `generate_json`。**
都是一次性的結構化輸出，不需要對話，用 `LLMProvider.generate_json(instructions, input, schema)`：
- 腳本：input 是規則書全部頁面（依頁碼排序），schema 為 `{sections: [{title, narration}]}`。規則書太長時（超過設定的字數上限），只取前面的頁面並在 instructions 說明，風險見下方。
- 素材清單：input 是確認後的腳本，schema 為 `{materials: [{section_number, description}]}`。後端驗證：`section_number` 必須存在、最多 15 項、每段至少一項（缺的由後端補，見 spec）。
- 兩者都做「次」的用語檢查，改寫一次，仍不符合回 503（與 `add-rules-qa` D6 相同的做法，共用同一個檢查函式）。

**D5 三個新的 `integrations/`。**

| 資料夾 | 介面 | 雲端實作 | fake |
|---|---|---|---|
| `tts/` | `TTSProvider.synthesize(text) -> AudioClip(data, seconds)` | Azure AI Speech REST（用既有的 `httpx`），聲音與語言由設定決定 | 依字數產生固定長度的靜音音檔 |
| `storage/` | `FileStorage.put/get/delete`，`put` 回傳可以播放或下載的網址 | 雲端物件儲存（例如 Azure Blob Storage） | 記憶體；另有 `local`（本機資料夾＋後端下載路由）供開發 |
| `video/` | `VideoRenderer.render(segments, width, height) -> bytes` | `FfmpegVideoRenderer`：以 `subprocess` 呼叫 ffmpeg，暫存檔放在臨時資料夾 | 記錄片段、回傳固定內容 |

設定：`TTS_PROVIDER`、`TTS_ENDPOINT`、`TTS_API_KEY`、`TTS_VOICE`；`STORAGE_PROVIDER`、`STORAGE_LOCAL_DIR`、`STORAGE_CONNECTION_STRING`、`STORAGE_CONTAINER`；`FFMPEG_PATH`（預設 `ffmpeg`）。沒填時一律用 fake，`uv run pytest` 不需要任何金鑰或 ffmpeg。

這三個資料夾在 AGENTS.md 第 3 節沒有擁有者，**要先在組內決定**（建議與其他 `integrations/` 相同由瑋鋐擁有，或由永傑擁有），並由組員更新 AGENTS.md。

**D6 合成在背景執行。**
合成可能要一分鐘以上，不能卡住 HTTP 請求。`PATCH status=rendering` 驗證後立即把狀態改為 `rendering`、回 202，用 FastAPI 的 `BackgroundTasks` 執行合成；背景工作自己開資料庫 session，結束時寫回 `ready` 或 `failed`。
- 伺服器重啟會讓背景工作消失、狀態卡在 `rendering`。查詢時若 `rendering_started_at` 超過 30 分鐘，service 把它當成 `failed`（spec「合成卡住」）。
- 替代方案：獨立的任務佇列（例如 Azure Queue＋worker）。被否決：本專案規模不需要，之後真的有需要再另開 change。

**D7 合成內容。**
- 每段：旁白 → TTS 音檔；畫面為該段素材照片，平均分配旁白長度；字幕為旁白依句號切開、依長度分配時間。
- 開頭加上 3 秒標題畫面（遊戲名稱＋「規則教學」），用主題色當背景；這一張由後端產生圖片，不需要店員拍。
- 輸出 1280×720、H.264＋AAC 的 mp4。
- 中文字幕需要中文字型：ffmpeg 使用執行環境中的 Noto Sans TC，字型檔路徑寫在設定（`VIDEO_FONT_PATH`）。

**D8 權限。**
`require_role(user, "shop_staff", "admin")`；修改類操作（修改腳本、確認、上傳、合成、發布）另外檢查 `project.created_by == user.id`，`admin` 不受限。查詢對所有店家人員開放，方便同店的人接手查看。

**D9 前端。**
- `state/`：`RulesVideoProjectsNotifier`（清單）、`RulesVideoProjectNotifier`（單一專案，family by id：腳本編輯、確認、上傳、合成、輪詢、發布）。輪詢用 `Timer`，在 `ref.onDispose` 取消。
- 拍照：沿用 `rules_ingest` 已新增的 `core/platform/image_picker.dart`（`feature/ocr` 分支，使用 `file_picker`），不另外加套件。
- 影片播放：組內自製影片在 YouTube（`add-rules-qa` D9，`youtube_player_iframe`）；本 change 產生的是 mp4（`source=file`），在 `add-rules-qa` 的 `LessonVideoPlayer` 介面加上 mp4 實作，新增官方的 `video_player` 套件（需組內同意）。預覽與教學頁共用這個介面，依 `source` 自動切換。
- 參考畫面 `/proto/rules_video`；正式頁面 `/rules-videos`、`/rules-videos/{video_id}`，入口只對店家人員與管理員顯示。

**D10 測試。**
- service 單元測試：`FakeLLMProvider`、`FakeTTSProvider`、`FakeFileStorage`、`FakeVideoRenderer`、手寫 `FakeRulesVideoRepository`、`FakeManualPagesSource`；背景合成在測試中直接同步呼叫合成函式。
- API 測試連 `_test` 資料庫，使用 `as_player`、`as_shop_staff`、`as_admin`；第二位店家人員用測試內建立的另一個 `CurrentUser`。
- `integrations/` 的雲端與 ffmpeg 實作測試加 `@pytest.mark.external`，本機手動執行（7.6）。
- 測試圖片用程式產生的小 PNG，不提交實際配件照片。

**D11 拆成四個 MR。**
1. MR 1：`integrations/tts`、`storage`、`video`（介面、fake、雲端與 ffmpeg 實作、external 測試）。
2. MR 2：後端影片製作 API、資料表、背景合成。需要 `add-rules-qa` MR 1 與 MR 1 先合併。
3. MR 3：前端 `data/`、`state/`、參考畫面、交接說明。
4. MR 4：正式頁面。

## Risks / Trade-offs

- **[規則書太長]** 整本規則書一次交給 LLM 可能超過長度上限或很貴。→ 設定字數上限；超過時只取前面的頁面，並在腳本草稿中提示店員檢查。之後可改成先分段摘要再產生腳本。
- **[靜態畫面]** 只有照片＋旁白，比不上真人拍攝的影片。→ 這是使用者選擇的做法（自動合成）；店員可以隨時重做或改用自製影片。
- **[ffmpeg 部署]** 容器映像要安裝 ffmpeg 與中文字型，映像會變大。→ 在部署設定中加入，`FfmpegVideoRenderer` 找不到 ffmpeg 時給清楚的錯誤。
- **[背景工作遺失]** 伺服器重啟時合成會中斷。→ 30 分鐘逾時視為失敗，店員可以重新合成。
- **[檔案權限]** 雲端儲存的影片網址若公開，任何人拿到網址都能看。→ 教學影片本來就是給玩家看的，可以公開；素材照片使用不公開的 key，只透過後端讀取。
- **[費用]** LLM、TTS、雲端儲存都會產生費用。→ 測試用 fake；腳本與素材清單只在店員操作時產生一次。

## Open Questions

1. `integrations/tts`、`storage`、`video` 的擁有者（AGENTS.md 第 3 節需要組員更新）。
2. 雲端儲存與 TTS 用哪個服務（建議 Azure Blob Storage 與 Azure AI Speech，與其他服務同在 Azure）？新增 `azure-storage-blob` 套件需要組內同意。
3. 旁白的聲音（男聲／女聲、語速）。
4. ~~組內自製影片放在哪裡~~：已決定放 YouTube（2026-11-17）；本 change 的 mp4 存在雲端儲存，兩種來源都支援。
5. 新表名 `rules_qa_video_projects`、`rules_qa_video_sections`、`rules_qa_video_materials` 需要在群組告知（4.4）。
