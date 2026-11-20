# Spec Delta

## Purpose

規則影片生產器第 1 階段 1c：AI 從規則書頁面產生一章的段資料草稿與最小素材清單，並和手寫版本逐項比對。規則書頁面文字與用語對照表放在本機；測試用自行編寫的假規則書頁面與 `FakeLLMProvider`。

## ADDED Requirements

### Requirement: 草稿模式
`load_video(folder, draft=True)` SHALL 允許三種還沒準備好的內容：`flat_photo` 素材的 `file` 為 `null`（待拍）、區域座標為 `null`（待量測）、`drawn` 素材。其他驗證規則與正式模式相同。正式模式（`stills`、`render`）遇到這三種內容時，SHALL 在載入時失敗並列出缺什麼。

#### Scenario: 草稿可以待拍、待量測
- **WHEN** 用草稿模式載入一份有 `file: null` 的素材與座標為 `null` 的區域的段資料
- **THEN** 載入成功；素材標示為待拍，區域標示為待量測

#### Scenario: 草稿可以列繪製素材
- **WHEN** 草稿的素材清單有 `kind: drawn` 的素材
- **THEN** 草稿模式載入成功

#### Scenario: 正式模式拒絕未完成的草稿
- **WHEN** 用正式模式載入同一份草稿（例如執行 `stills`）
- **THEN** 載入失敗，列出待拍的素材、待量測的區域與尚未支援的繪製素材

#### Scenario: 草稿的其他錯誤照樣擋下
- **WHEN** 草稿引用不存在的素材，或使用五種以外的動作
- **THEN** 草稿模式也載入失敗

### Requirement: AI 產生段資料草稿
`draft` 指令 SHALL 讀取指定的規則書頁面文字（檔名 `<語言>-<頁碼>.txt`）與用語對照表（`terms.json`），交給 LLM 產生一章的段資料草稿，寫到 `<資料夾>/draft/video.json`，不覆寫手寫的 `video.json`。草稿 SHALL 包含分段、旁白、字幕、槽位、句內動作、highlight 與 label、出處頁碼與最小素材清單；素材有 `kind`、`priority`、`reason`；照片檔與區域座標留空。

#### Scenario: 產生草稿
- **WHEN** 對一頁假規則書執行 `draft`，LLM 回傳合法的內容
- **THEN** 寫出 `draft/video.json`，草稿模式載入成功；句的 key 為「章節編號-序號」；手寫的 `video.json` 不變

#### Scenario: LLM 的輸入
- **WHEN** 執行 `draft`
- **THEN** 給 LLM 的輸入包含章節編號與名稱、每一頁的頁碼與文字、用語對照表；指示要求只根據輸入的頁面、只列觀眾必須讀到資訊的素材、不使用「次」

#### Scenario: 找不到頁面或對照表
- **WHEN** 指定的頁面檔或 `terms.json` 不存在，或頁面檔名不是 `<語言>-<頁碼>.txt`
- **THEN** 不呼叫 LLM，結束代碼不為 0，說明缺哪個檔案或檔名格式

#### Scenario: 借用手寫版的照片與座標
- **WHEN** 加上 `--assets-from video.json` 執行 `draft`
- **THEN** 草稿中 `asset_key` 與手寫版相同的素材，照片檔與區域座標從手寫版複製過來；沒對上的素材仍為待拍

#### Scenario: LLM 無法使用
- **WHEN** LLM 服務無法連線
- **THEN** 結束代碼不為 0，說明 LLM 暫時無法使用，不寫出草稿

### Requirement: 檢查與改寫一次
LLM 的輸出 SHALL 依序檢查：草稿模式的段資料驗證、旁白、字幕與畫面文字沒有「次」、沒有對照表列為 `avoid` 的詞、`source_pages` 只有輸入的頁碼。任一項不通過時，SHALL 把錯誤清單交給 LLM 改寫一次；改寫後仍不通過時失敗，並把兩次原始輸出存成 `draft/rejected-1.json`、`draft/rejected-2.json`。

#### Scenario: 改寫一次後通過
- **WHEN** 第一次輸出的旁白用了「次」，改寫後沒有
- **THEN** 寫出改寫後的草稿；LLM 被呼叫兩次，第二次的輸入包含第一次的錯誤清單

#### Scenario: 改寫後仍不通過
- **WHEN** 兩次輸出都不通過檢查
- **THEN** 結束代碼不為 0，列出錯誤；不寫出 `draft/video.json`，兩次原始輸出存成 `rejected-1.json`、`rejected-2.json`

#### Scenario: 段資料格式錯誤
- **WHEN** 輸出的 cue 指向不存在的對象
- **THEN** 視為不通過，進入改寫

#### Scenario: 不要用的譯法
- **WHEN** 字幕用了對照表 `avoid` 列出的詞
- **THEN** 視為不通過，錯誤訊息指出是哪個詞、應改用哪個詞

#### Scenario: 出處頁碼不在輸入中
- **WHEN** 某段的 `source_pages` 有輸入以外的頁碼
- **THEN** 視為不通過

### Requirement: 逐項比對
`compare` 指令 SHALL 用草稿模式載入兩份段資料，輸出 Markdown 報告 `compare.md`：分段、旁白與字幕（並列加相似度）、素材清單（依 `asset_key`）、槽位、句內動作（target 換算成素材後依順序對齊）、highlight 與 label、區域名稱、出處頁碼。每個項目標出相同、不同、缺少或多出，報告最上面是各項的數量摘要。報告不判定合格與否。

#### Scenario: 兩份相同
- **WHEN** 比對同一份段資料
- **THEN** 摘要中每一項都是「相同」，旁白相似度為 1

#### Scenario: 素材清單不同
- **WHEN** AI 版多一個素材、少一個素材、另一個素材的 `priority` 不同
- **THEN** 報告分別列為多出、缺少、不同

#### Scenario: 動作依素材對齊
- **WHEN** 兩邊的項目命名不同（`c2` 與 `card2`），但都是「hide 幽魂」
- **THEN** 視為同一個動作；`at` 不同時列出相差秒數

#### Scenario: 分段不同
- **WHEN** AI 版把兩句放在同一段，手寫版分成兩段
- **THEN** 報告列出兩邊的段數與每段句數，旁白仍依句的順序並列

#### Scenario: 比對的檔案有錯
- **WHEN** 其中一份段資料驗證失敗
- **THEN** 結束代碼不為 0，指出是哪一份、什麼錯誤，不輸出報告
