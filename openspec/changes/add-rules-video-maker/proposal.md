# Proposal

## Why

規則教學（`add-rules-qa`）讓有教學影片的遊戲先看影片再發問，但目前只有 3 款遊戲有組內自製的影片。要讓更多遊戲有影片，得由店家自己做；而店家沒有時間寫腳本、配音、剪片。

本 change 提供給店家使用的「規則影片生產器」：店家只要提供說明書與幾張實體配件的照片，系統就能做出教學影片。流程：

1. **說明書**：這款遊戲已經入庫過規則書就直接用；還沒有的話，請店員逐頁拍照，透過 `rules_ingest`（瑋鋐）入庫。
2. **用文字確認內容**：系統依規則書產生影片腳本（分段、每段的旁白），店員修改並確認。
3. **要求實體素材**：依確認後的腳本，列出需要拍的配件與畫面，例如「遊戲盤面俯拍」「每種卡牌各一張正面」，店員逐項拍照上傳。
4. **產生影片**：把照片、AI 旁白語音與字幕自動合成影片，店員預覽後發布，成為這款遊戲的教學影片。

## What Changes

- 新增 `rules_qa` domain 的影片製作 API（`/api/v1/rules-videos`），限店家人員與管理員：
  - `POST /api/v1/rules-videos`：為某款遊戲建立影片製作專案，依規則書產生腳本草稿。沒有規則書時回 409，引導先拍說明書。
  - `GET /api/v1/rules-videos`、`GET /api/v1/rules-videos/{video_id}`：專案清單與詳細資料（狀態、腳本、素材清單、完成的影片）。
  - `PUT /api/v1/rules-videos/{video_id}/script`：修改腳本。
  - `PATCH /api/v1/rules-videos/{video_id}`：以 `status` 推進流程：確認腳本（產生素材清單）、開始合成、發布。
  - `PUT /api/v1/rules-videos/{video_id}/materials/{material_number}/photo`：上傳某項素材的照片。
- 新增三種外部服務的轉接層（`integrations/`），各自有介面、fake 與雲端實作：
  - `tts/`：文字轉語音（旁白）。
  - `storage/`：檔案儲存（素材照片、旁白音檔、完成的影片）。
  - `video/`：把圖片、音檔、字幕合成 mp4（以 ffmpeg 實作）。
- 新增資料表 `rules_qa_video_projects`、`rules_qa_video_sections`、`rules_qa_video_materials`（一個 migration）。
- 新增前端 `domains/rules_qa/` 的影片製作精靈：`data/`、`state/`、參考畫面、正式頁面，只有店家人員與管理員看得到入口。
- **不做**：AI 生成動態影片畫面、影片剪輯與手動調整時間軸、背景音樂、多語言旁白、玩家使用影片生產器。

## Capabilities

### New Capabilities
- `rules-video-maker`：影片製作專案的後端行為（建立、腳本、確認、素材清單、上傳、合成、發布、權限、用語規則）。
- `media-integrations`：`tts`、`storage`、`video` 三個轉接層的介面與 fake 行為。
- `rules-video-maker-page`：前端影片製作精靈。

### Modified Capabilities
- `rules-qa`（`add-rules-qa`）：教學影片可以來自影片生產器；發布時寫入 `rules_qa_videos`，行為與 `PUT /api/v1/rules-lessons/{game_id}/video` 相同。

## Impact

- **受影響 domain**：`rules_qa`（主責永傑，協助新善、瑋鋐）。
- **依賴**：
  - `add-rules-qa` 的 MR 1（`rules_qa_videos` 資料表）要先合併。
  - `rules_ingest`（瑋鋐）：沿用逐頁匯入 API 拍說明書；讀取頁面用 `add-rules-qa` design.md D4 的 service 方法。程式在 `feature/ocr`，尚未合併。
- **共用區**：
  - 新增 `backend/app/integrations/tts/`、`storage/`、`video/`。AGENTS.md 第 3 節的共用區擁有者表**沒有這三個資料夾**，要先在組內決定擁有者，並由組員更新 AGENTS.md（AI 不能修改）。MR 要 @ 瑋鋐（其他 `integrations/` 的擁有者）。
  - `backend/app/core/config.py`、`.env.example`、`backend/app/main.py`（立倫）：新增設定與建立 provider，MR 要 @ 立倫。
- **新增套件與系統元件**（需要組內同意，MR 說明要寫理由）：
  - 後端執行環境需要 **ffmpeg**（系統程式，不是 Python 套件），部署的容器映像要安裝。
  - 雲端儲存可能需要 `azure-storage-blob`；文字轉語音用 Azure AI Speech 的 REST API，可用既有的 `httpx`，不新增套件。
- **費用**：產生腳本與素材清單呼叫 LLM，旁白呼叫 TTS，儲存照片與影片使用雲端儲存。測試一律用 fake。
- **契約**：有改動，新增上列 API（要 @ 立倫）。
- **migration**：一個（要 @ 瑋鋐）。建表前先在群組告知表名（4.4）。
- **資料**：測試只用自行編寫的假規則與假圖片，不提交規則書全文與實際配件照片。
- **不修改** `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。
