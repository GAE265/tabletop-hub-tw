# Spec Delta

## Purpose

給店家使用的規則影片生產器（`rules_qa` domain）。一個「影片製作專案」對應一款遊戲，依序經過以下狀態：

| `status` | 意思 | 下一步 |
|---|---|---|
| `script_draft` | 腳本草稿，店員可以修改 | 確認腳本 → `collecting_materials` |
| `collecting_materials` | 腳本已確認，等店員上傳素材照片 | 開始合成 → `rendering` |
| `rendering` | 正在合成影片 | 成功 → `ready`；失敗 → `failed` |
| `ready` | 影片完成，可以預覽 | 發布 → `published` |
| `failed` | 合成失敗，附錯誤訊息 | 重新合成 → `rendering` |
| `published` | 已發布為這款遊戲的教學影片 | — |

只有 `shop_staff` 與 `admin` 可以使用。專案只有建立者與 `admin` 可以修改；其他店家人員可以查看。腳本、旁白與素材說明的遊戲用語依 AGENTS.md 第 10.2 節，不使用「次」。

## ADDED Requirements

### Requirement: 建立專案與腳本草稿
`POST /api/v1/rules-videos` SHALL 接收 `game_id`，透過 `rules_ingest` 的 service 讀取這款遊戲的規則書頁面，交給 LLM 產生腳本草稿，建立 `status=script_draft` 的專案並回 201。腳本為 4–8 段，每段有 `section_number`（從 1 開始）、`title`、`narration`（旁白，每段 30–400 字）；預設依序涵蓋遊戲目標、準備、一個回合怎麼進行、遊戲結束與計分。

#### Scenario: 已有規則書
- **WHEN** 店員對已入庫規則書的遊戲建立專案
- **THEN** 回 201，`status=script_draft`，回傳依規則書產生的分段腳本，不需要重新拍說明書

#### Scenario: 還沒有規則書
- **WHEN** 遊戲存在，但沒有任何規則書頁面
- **THEN** 回 409，`RULES_VIDEO_NO_RULEBOOK`，訊息提示先拍攝並匯入說明書；不建立專案、不呼叫 LLM

#### Scenario: 遊戲不存在
- **WHEN** `game_id` 在 `games` 找不到
- **THEN** 回 404，`GAME_NOT_FOUND`

#### Scenario: 玩家沒有權限
- **WHEN** `player` 建立專案
- **THEN** 回 403

#### Scenario: 腳本用語
- **WHEN** LLM 產生的腳本使用了「次」
- **THEN** 要求 LLM 改寫一次；仍有「次」時回 503，`RULES_VIDEO_OUTPUT_REJECTED`，不建立專案

#### Scenario: LLM 無法使用
- **WHEN** LLM 服務無法連線
- **THEN** 回 503，`RULES_VIDEO_UNAVAILABLE`，不建立專案

### Requirement: 查詢專案
`GET /api/v1/rules-videos` SHALL 依建立時間由新到舊列出專案（可用 `game_id` 篩選，分頁），`GET /api/v1/rules-videos/{video_id}` SHALL 回傳專案的狀態、腳本、素材清單（含每項是否已上傳）、完成的影片網址（`ready` 以後）與失敗訊息（`failed` 時）。

#### Scenario: 查看專案
- **WHEN** 店員查詢自己的專案
- **THEN** 回 200，包含 `status`、`sections`、`materials`

#### Scenario: 其他店家人員查看
- **WHEN** 另一位店家人員查詢這個專案
- **THEN** 回 200，可以查看

#### Scenario: 專案不存在
- **WHEN** `video_id` 不存在
- **THEN** 回 404，`RULES_VIDEO_NOT_FOUND`

### Requirement: 修改腳本
`PUT /api/v1/rules-videos/{video_id}/script` SHALL 以送出的段落整份取代腳本，只能在 `script_draft` 時修改。

#### Scenario: 修改旁白
- **WHEN** 建立者修改第 2 段的旁白並送出
- **THEN** 回 200，腳本更新

#### Scenario: 段落格式錯誤
- **WHEN** 段落數不在 1–8 之間、`section_number` 不連續，或某段旁白為空
- **THEN** 回 422，腳本不變

#### Scenario: 已確認後不能修改
- **WHEN** 專案狀態不是 `script_draft`
- **THEN** 回 409，`RULES_VIDEO_INVALID_STATUS`

#### Scenario: 不是建立者
- **WHEN** 另一位店家人員修改腳本
- **THEN** 回 403；`admin` 可以修改

### Requirement: 確認腳本並產生素材清單
`PATCH /api/v1/rules-videos/{video_id}` 帶 `{"status": "collecting_materials"}` SHALL 確認腳本，交給 LLM 依腳本產生素材清單，狀態改為 `collecting_materials`。素材清單最多 15 項，每項有 `material_number`（從 1 開始）、所屬的 `section_number`、`description`（要拍什麼、怎麼拍，例如「從正上方拍攝整個遊戲盤面，配件擺成開局的樣子」）。每一段至少有一項素材。

#### Scenario: 確認腳本
- **WHEN** 建立者確認腳本
- **THEN** 回 200，`status=collecting_materials`，`materials` 不為空，每段都有素材，全部標示為未上傳

#### Scenario: LLM 漏掉某一段的素材
- **WHEN** LLM 產生的清單中，有一段沒有任何素材
- **THEN** 後端替該段補上一項「拍攝與『段落標題』相關的配件」，不讓任何一段沒有畫面

#### Scenario: 狀態不對
- **WHEN** 專案不是 `script_draft`
- **THEN** 回 409，`RULES_VIDEO_INVALID_STATUS`

#### Scenario: LLM 無法使用
- **WHEN** LLM 服務無法連線
- **THEN** 回 503，`RULES_VIDEO_UNAVAILABLE`，狀態維持 `script_draft`

### Requirement: 上傳素材照片
`PUT /api/v1/rules-videos/{video_id}/materials/{material_number}/photo` SHALL 接收一張 JPEG 或 PNG（不超過 10 MB），存進檔案儲存，取代該項素材之前的照片。只能在 `collecting_materials` 或 `failed` 時上傳。

#### Scenario: 上傳照片
- **WHEN** 建立者上傳第 1 項素材的照片
- **THEN** 回 200，該項標示為已上傳

#### Scenario: 重拍
- **WHEN** 已上傳過的素材再上傳一張
- **THEN** 回 200，以新照片取代，舊檔案從儲存中刪除

#### Scenario: 圖片格式錯誤
- **WHEN** 上傳的不是 JPEG 或 PNG，或是空檔案
- **THEN** 回 400，`INVALID_IMAGE`（與 `rules_ingest` 相同）

#### Scenario: 圖片太大
- **WHEN** 圖片超過 10 MB
- **THEN** 回 400，`IMAGE_TOO_LARGE`

#### Scenario: 素材不存在
- **WHEN** `material_number` 不在清單中
- **THEN** 回 404，`RULES_VIDEO_MATERIAL_NOT_FOUND`

#### Scenario: 狀態不對
- **WHEN** 專案是 `script_draft`、`rendering`、`ready` 或 `published`
- **THEN** 回 409，`RULES_VIDEO_INVALID_STATUS`

#### Scenario: 儲存服務無法使用
- **WHEN** 檔案儲存無法連線
- **THEN** 回 503，`RULES_VIDEO_UNAVAILABLE`，素材維持原狀

### Requirement: 合成影片
`PATCH /api/v1/rules-videos/{video_id}` 帶 `{"status": "rendering"}` SHALL 在所有素材都已上傳時開始合成，立即回 202 並把狀態改為 `rendering`，在背景依序：用 TTS 產生每段旁白的音檔 → 每段的畫面平均分配該段素材照片，長度等於旁白長度 → 加上旁白字幕 → 合成 1280×720 的 mp4 → 存進檔案儲存。成功時狀態改為 `ready` 並記錄影片網址；任何一步失敗時改為 `failed` 並記錄錯誤訊息。

#### Scenario: 開始合成
- **WHEN** 所有素材都已上傳，建立者開始合成
- **THEN** 回 202，`status=rendering`

#### Scenario: 合成成功
- **WHEN** 背景合成完成
- **THEN** `status=ready`，`video_url` 指向儲存中的 mp4；影片的段落順序與腳本相同，每段長度等於該段旁白音檔長度

#### Scenario: 素材還沒上傳完
- **WHEN** 還有素材未上傳
- **THEN** 回 409，`RULES_VIDEO_MATERIALS_MISSING`，`details` 列出未上傳的 `material_number`

#### Scenario: 合成失敗
- **WHEN** TTS 或合成步驟失敗
- **THEN** `status=failed`，`error_message` 說明失敗原因（不含金鑰或外部服務的原始回應）

#### Scenario: 重新合成
- **WHEN** 專案是 `failed`，建立者再次開始合成
- **THEN** 回 202，重新合成

#### Scenario: 合成卡住
- **WHEN** 專案停在 `rendering` 超過 30 分鐘（例如伺服器重啟）
- **THEN** 查詢時視為 `failed`，`error_message` 為「合成逾時，請重新合成」

#### Scenario: 狀態不對
- **WHEN** 專案不是 `collecting_materials` 或 `failed`
- **THEN** 回 409，`RULES_VIDEO_INVALID_STATUS`

### Requirement: 發布
`PATCH /api/v1/rules-videos/{video_id}` 帶 `{"status": "published"}` SHALL 把完成的影片設為這款遊戲的教學影片：寫入 `rules_qa_videos`（取代既有影片，標題為「《遊戲名稱》規則教學」），狀態改為 `published`。

#### Scenario: 發布影片
- **WHEN** 建立者發布 `ready` 的影片
- **THEN** 回 200，`status=published`；之後 `GET /api/v1/rules-lessons/{game_id}` 的 `video` 為這支影片

#### Scenario: 取代既有影片
- **WHEN** 這款遊戲原本就有教學影片
- **THEN** 原本的影片被取代（回應中的 `replaced_video_url` 為舊網址，前端在發布前提醒）

#### Scenario: 還沒完成
- **WHEN** 專案不是 `ready`
- **THEN** 回 409，`RULES_VIDEO_INVALID_STATUS`

#### Scenario: 不允許的狀態值
- **WHEN** `PATCH` 帶的 `status` 不是 `collecting_materials`、`rendering`、`published`
- **THEN** 回 422
