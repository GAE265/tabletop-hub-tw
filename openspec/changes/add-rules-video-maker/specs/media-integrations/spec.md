# Spec Delta

## Purpose

影片生產器需要的三種外部能力，依 AGENTS.md 4.2 包在 `backend/app/integrations/` 的介面後面，任何 domain 都不直接呼叫廠商 SDK 或執行 ffmpeg。每個介面都有 fake 實作供 domain 測試使用；雲端實作的測試加上 `@pytest.mark.external`（7.6）。

## ADDED Requirements

### Requirement: 文字轉語音（`integrations/tts`）
`TTSProvider.synthesize(text) -> AudioClip` SHALL 回傳音檔內容（mp3）與長度（秒）。實作由 `TTS_PROVIDER`（`fake`｜`cloud`）切換。

#### Scenario: fake 產生固定長度的音檔
- **WHEN** 用 `FakeTTSProvider` 轉換一段文字
- **THEN** 回傳有效的靜音音檔，長度依字數計算（每 4 個字 1 秒，至少 1 秒），結果可以預測

#### Scenario: 空白文字
- **WHEN** 文字是空字串或只有空白
- **THEN** 拋 `ValueError`，不發請求

#### Scenario: 雲端服務無法使用
- **WHEN** 雲端 TTS 連不上或回錯誤
- **THEN** 拋 `TTSUnavailable`，訊息不含金鑰

#### Scenario: 缺少設定
- **WHEN** `TTS_PROVIDER=cloud` 但沒有設定端點或金鑰
- **THEN** 建立 provider 時拋錯並說明缺哪個設定

### Requirement: 檔案儲存（`integrations/storage`）
`FileStorage` SHALL 提供 `put(key, data, content_type) -> url`、`get(key) -> bytes`、`delete(key)`。實作由 `STORAGE_PROVIDER`（`fake`｜`local`｜`cloud`）切換：`fake` 存在記憶體；`local` 存在本機資料夾並由後端提供下載網址（開發用）；`cloud` 存在雲端物件儲存。

#### Scenario: 存取與刪除
- **WHEN** `put` 一個檔案後 `get` 同一個 key
- **THEN** 取回相同內容；`delete` 後 `get` 拋 `FileNotFound`

#### Scenario: 刪除不存在的檔案
- **WHEN** `delete` 一個不存在的 key
- **THEN** 不拋錯（可以重複執行）

#### Scenario: 雲端服務無法使用
- **WHEN** 雲端儲存連不上
- **THEN** 拋 `StorageUnavailable`

### Requirement: 影片合成（`integrations/video`）
`VideoRenderer.render(segments, width, height) -> bytes` SHALL 依序把每個片段（一組圖片、一個音檔、字幕文字）合成 mp4：片段長度等於音檔長度，片段內的圖片平均分配時間，圖片等比例縮放並補邊到指定尺寸，字幕燒在畫面下方。`FfmpegVideoRenderer` 以 ffmpeg 實作；`FakeVideoRenderer` 不執行 ffmpeg，回傳固定內容並記錄收到的片段。

#### Scenario: fake 記錄片段
- **WHEN** 用 `FakeVideoRenderer` 合成 3 個片段
- **THEN** 回傳非空內容，`calls` 記錄 3 個片段的圖片數、音檔長度與字幕

#### Scenario: 沒有片段或片段沒有圖片
- **WHEN** 片段清單為空，或某個片段沒有圖片
- **THEN** 拋 `ValueError`

#### Scenario: 找不到 ffmpeg
- **WHEN** 執行環境沒有安裝 ffmpeg
- **THEN** `FfmpegVideoRenderer` 拋 `VideoRenderError`，訊息說明需要安裝 ffmpeg

#### Scenario: 實際合成（external）
- **WHEN** 在裝有 ffmpeg 的電腦上，用 2 張測試圖片與 3 秒音檔合成
- **THEN** 產生可播放的 mp4，長度約 3 秒，解析度 1280×720
