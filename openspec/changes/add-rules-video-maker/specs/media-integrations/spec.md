# Spec Delta

## Purpose

影片生產器需要的外部能力，依 AGENTS.md 4.2 包在 `backend/app/integrations/` 的介面後面，任何 domain 都不直接呼叫廠商 SDK 或執行 ffmpeg。每個介面都有 fake 實作供測試使用；實際連到外部服務或需要 ffmpeg 的測試加上 `@pytest.mark.external`（7.6）。

`storage/` 已於 #42 合併；`tts/` 與 `video/` 由本 change 新增。版型、時間軸等影片組裝行為見 `rules-video-maker`。

## ADDED Requirements

### Requirement: 文字轉語音（`integrations/tts`）
`TTSProvider.synthesize(text, voice) -> AudioClip` SHALL 回傳 wav 音檔內容（48 kHz、16-bit、mono）與長度（秒）。實作由 `TTS_PROVIDER`（`fake`｜`azure`）切換，沒有設定時使用 fake。

#### Scenario: fake 產生固定長度的音檔
- **WHEN** 用 `FakeTTSProvider` 轉換一段文字
- **THEN** 回傳有效的靜音 wav，長度依字數計算（每 4 個字 1 秒，至少 1 秒），結果可以預測

#### Scenario: 空白文字
- **WHEN** 文字是空字串或只有空白
- **THEN** 拋 `ValueError`，不發請求

#### Scenario: 請求內容
- **WHEN** 用 Azure 實作合成一句
- **THEN** 請求送到 `https://{TTS_REGION}.tts.speech.microsoft.com/cognitiveservices/v1`，標頭帶金鑰與輸出格式 `riff-48khz-16bit-mono-pcm`，SSML 的語言為 `zh-TW`、聲音為指定的 `voice`

#### Scenario: 特殊字元
- **WHEN** 文字含 `&`、`<`、`>`
- **THEN** SSML 中正確跳脫，請求是合法的 XML

#### Scenario: 雲端服務無法使用
- **WHEN** Azure TTS 連不上、逾時或回 5xx
- **THEN** 拋 `TTSUnavailable`，訊息不含金鑰

#### Scenario: 金鑰錯誤
- **WHEN** Azure TTS 回 401 或 403
- **THEN** 拋 `TTSError`（不是 `TTSUnavailable`，重試也不會成功），訊息不含金鑰

#### Scenario: 請求太頻繁
- **WHEN** Azure TTS 先回 429 再回 200
- **THEN** 等待後重試，回傳音檔

#### Scenario: 一直請求太頻繁
- **WHEN** Azure TTS 一直回 429，超過重試上限
- **THEN** 拋 `TTSUnavailable`

#### Scenario: 缺少設定
- **WHEN** `TTS_PROVIDER=azure` 但沒有設定 `TTS_REGION` 或 `TTS_API_KEY`
- **THEN** 建立 provider 時拋 `TTSNotConfigured` 並說明缺哪個設定

#### Scenario: 沒有設定 provider
- **WHEN** 沒有設定 `TTS_PROVIDER`
- **THEN** 使用 `FakeTTSProvider`

#### Scenario: 未知的 provider
- **WHEN** `TTS_PROVIDER` 不是 `fake` 或 `azure`
- **THEN** 建立 provider 時拋錯並說明可用的值

#### Scenario: 實際合成（external）
- **WHEN** 設好金鑰後合成一句中文
- **THEN** 回傳可播放的 wav，`seconds` 與音檔實際長度相差 0.05 秒以內

### Requirement: 檔案儲存（`integrations/storage`）
`FileStorage` SHALL 提供 `put(key, data, content_type) -> url`、`get(key) -> bytes`、`delete(key)`。實作由 `STORAGE_PROVIDER`（`fake`｜`local`｜`cloud`）切換。本階段的本機指令直接讀寫本機資料夾，不使用檔案儲存；這裡保留已合併的行為。

#### Scenario: 存取與刪除
- **WHEN** `put` 一個檔案後 `get` 同一個 key
- **THEN** 取回相同內容；`delete` 後 `get` 拋 `FileNotFound`

#### Scenario: 刪除不存在的檔案
- **WHEN** `delete` 一個不存在的 key
- **THEN** 不拋錯（可以重複執行）

#### Scenario: 雲端服務無法使用
- **WHEN** 雲端儲存連不上
- **THEN** 拋 `StorageUnavailable`

### Requirement: ffmpeg 呼叫（`integrations/video`）
影片編碼、串接與混音 SHALL 只在 `integrations/video/` 以 `subprocess` 呼叫 ffmpeg，路徑由 `FFMPEG_PATH` 設定（預設 `ffmpeg`）。ffmpeg 失敗時 SHALL 拋 `VideoRenderError`，訊息包含 ffmpeg 錯誤輸出的最後幾行；中斷時不留下不完整的輸出檔。

#### Scenario: 找不到 ffmpeg
- **WHEN** 執行環境沒有安裝 ffmpeg
- **THEN** 拋 `VideoRenderError`，訊息說明需要安裝 ffmpeg 或設定 `FFMPEG_PATH`

#### Scenario: 編碼中斷
- **WHEN** ffmpeg 在編碼某段時失敗
- **THEN** 該段的 `.tmp.mp4` 被刪除，不產生同名的正式檔案

#### Scenario: 實際編碼與混音（external）
- **WHEN** 在裝有 ffmpeg 的電腦上，把 2 段畫面、2 句 3 秒的旁白與背景音樂組成影片
- **THEN** 產生可播放的 mp4：1920×1080、30 fps、AAC 音軌，長度約 6 秒
