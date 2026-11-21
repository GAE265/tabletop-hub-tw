# rules-video-script Specification

## Purpose

規則影片生產器第 1 階段 1c：AI 從規則書頁面產生一章的段資料草稿與最小素材清單，並和手寫版本逐項比對。規則書頁面文字與用語對照表放在本機；測試用自行編寫的假規則書頁面與 `FakeLLMProvider`。

## Requirements

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

#### Scenario: 泛稱的代表牌
- **WHEN** 規則寫的是一整類的牌（用語對照表 `category: generic`，例如花苞牌）
- **THEN** 指示要求素材用泛稱的 key，reason 寫明「代表牌：<泛稱>，店員可以替換成同類的任一張牌」；對照表標為單一種牌（`category: single`）的素材不可寫「代表牌」（2026-11-21 永傑決定，取代原本「選一張具體的牌」的做法）

#### Scenario: 對照表的分類
- **WHEN** `terms.json` 的某一筆有 `category`
- **THEN** 只能是 `generic`（泛稱）或 `single`（單一種牌），否則不呼叫 LLM、說明可用的值；LLM 的輸入在該詞後面標示「泛稱」或「單一種牌」

#### Scenario: 旁白不能省略字幕的條件
- **WHEN** 執行 `draft`
- **THEN** 指示要求旁白可以口語，但不能省略字幕裡的任何條件

#### Scenario: 找不到頁面或對照表
- **WHEN** 指定的頁面檔或 `terms.json` 不存在，或頁面檔名不是 `<語言>-<頁碼>.txt`
- **THEN** 不呼叫 LLM，結束代碼不為 0，說明缺哪個檔案或檔名格式

#### Scenario: 參考頁
- **WHEN** 加上 `--reference-pages rulebook/en-003.txt` 執行 `draft`
- **THEN** LLM 的輸入把參考頁標為「參考資料：只供查牌名與牌的分類，不可寫成旁白、字幕或畫面文字，也不可列在 source_pages」，本章的頁標為「本章內容」；只給 `--pages` 時行為不變

#### Scenario: 參考頁不存在
- **WHEN** `--reference-pages` 指定的檔案不存在或檔名格式不對
- **THEN** 不呼叫 LLM，結束代碼不為 0，說明是哪個檔案

#### Scenario: 借用手寫版的照片與座標
- **WHEN** 加上 `--assets-from video.json` 執行 `draft`
- **THEN** 草稿中 `asset_key` 與手寫版相同的素材，照片檔與區域座標從手寫版複製過來；沒對上的素材仍為待拍

#### Scenario: LLM 無法使用
- **WHEN** LLM 服務無法連線
- **THEN** 結束代碼不為 0，說明 LLM 暫時無法使用，不寫出草稿

### Requirement: 檢查與改寫一次
LLM 的輸出 SHALL 依序檢查：草稿模式的段資料驗證、旁白、字幕與畫面文字沒有「次」、沒有對照表列為 `avoid` 的詞、每個素材都有拍攝說明、泛稱素材有代表牌說明且單一種牌素材沒有、`source_pages` 只有本章的頁碼。任一項不通過時，SHALL 把錯誤清單交給 LLM 改寫一次；改寫後仍不通過時失敗，並把兩次原始輸出存成 `draft/rejected-1.json`、`draft/rejected-2.json`。

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

#### Scenario: 泛稱素材缺代表牌說明
- **WHEN** 對照表標為泛稱的素材，reason 沒有「代表牌」
- **THEN** 視為不通過，錯誤訊息說明要寫代表牌說明

#### Scenario: 單一種牌標了代表牌
- **WHEN** 對照表標為單一種牌的素材，reason 寫了「代表牌」
- **THEN** 視為不通過

#### Scenario: 素材缺拍攝說明
- **WHEN** 任何一個素材的 `shot` 是空的
- **THEN** 視為不通過，錯誤訊息指出是哪個素材

#### Scenario: 出處頁碼用了參考頁
- **WHEN** 某段的 `source_pages` 有參考頁的頁碼
- **THEN** 視為不通過，錯誤訊息說明參考頁只供查牌名與分類，source_pages 只能用本章的頁

#### Scenario: 出處頁碼不在輸入中
- **WHEN** 某段的 `source_pages` 有輸入以外的頁碼
- **THEN** 視為不通過

### Requirement: 格式小錯的自動清理
LLM 的每次輸出 SHALL 先自動清理四種格式小錯，清理後仍要通過所有檢查；其他錯誤照舊走改寫。四種是：C1「@」「.」前後的空白、C2 開頭與結尾的空白、C3 全形分隔符號（＠、．）、C4 cue target 的 `highlight:`／`label:` 前綴（去掉後必須是這一段的 highlight 或 label 的 key）。每次清了什麼 SHALL 記錄在 `draft/cleanup.json`、執行時印出，並在比對報告加上「自動清理」一節（2026-11-21 永傑同意）。

#### Scenario: C1 分隔符號前後的空白
- **WHEN** move 的 to 是 `sidebar@ zone_a`
- **THEN** 清成 `sidebar@zone_a` 並記錄 C1

#### Scenario: C2 開頭結尾的空白
- **WHEN** highlight 的 key 是 ` h1 `
- **THEN** 清成 `h1` 並記錄 C2

#### Scenario: C3 全形分隔符號
- **WHEN** to 是 `sidebar＠zone_a`
- **THEN** 清成 `sidebar@zone_a` 並記錄 C3

#### Scenario: C4 前綴
- **WHEN** cue 的 target 是 `highlight:h1`，而這一段有 highlight `h1`
- **THEN** 清成 `h1` 並記錄 C4；去掉前綴後不是這一段的 key 時不清

#### Scenario: 清理後照樣檢查
- **WHEN** 輸出有可以清的格式小錯，也有其他錯誤（例如指向不存在的項目）
- **THEN** 清掉格式小錯，其他錯誤照舊進入改寫

#### Scenario: 清理紀錄
- **WHEN** `draft` 清了格式小錯
- **THEN** 印出清了什麼、寫出 `draft/cleanup.json`；`compare` 的報告加上「自動清理」一節

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

### Requirement: 規則涵蓋檢查
`coverage` 指令 SHALL 用 LLM 把本章規則書頁面的每一條規則，分別與旁白、字幕對照，標出完整、不完整（缺了什麼）或未涵蓋，並列出說反或規則書沒有的句子。LLM 的輸入 SHALL 只有本章頁面的原文、編號的旁白與編號的字幕，不含參考頁與草稿的其他內容。旁白可以比字幕短，但字幕完整而旁白不完整時，SHALL 由程式標為「旁白比字幕少條件」。結果寫成 `coverage.json` 與 `coverage.md`；`compare` 的報告有 `coverage.json` 時加上「規則陳述檢查」一節，並註明是 AI 檢查、僅供參考。

#### Scenario: 旁白比字幕少條件
- **WHEN** LLM 判斷某條規則的字幕完整、旁白不完整
- **THEN** 標為「旁白比字幕少條件」，附上原文與缺少的部分

#### Scenario: 旁白與字幕都不完整
- **WHEN** 某條規則的旁白與字幕都不完整
- **THEN** 兩邊都標為不完整

#### Scenario: 規則未涵蓋
- **WHEN** 某條規則在旁白與字幕都沒出現
- **THEN** 標為未涵蓋

#### Scenario: 說反或規則書沒有的規則
- **WHEN** LLM 回報某一句與原文相反，或寫了原文沒有的規則
- **THEN** 列出是哪一句（旁白或字幕）與原因

#### Scenario: 規則分類
- **WHEN** 執行涵蓋檢查
- **THEN** 每條規則標為條件、動作或目的說明，報告的規則表列出分類

#### Scenario: 目的說明另列為提示
- **WHEN** 某條規則是目的說明（例如洗牌是為了讓人無法判斷誰打出哪張牌），旁白或字幕沒講到
- **THEN** 不算漏講、不標「旁白比字幕少條件」，但不隱藏：另列在「提示（目的說明，不算漏講）」（2026-11-21 永傑決定）

#### Scenario: 全部完整
- **WHEN** 每條規則的旁白與字幕都完整，也沒有問題句
- **THEN** 報告寫「共檢查 N 條規則」與「沒有發現問題」，並列出每一條規則與旁白、字幕的狀態，看得出 LLM 拆了幾條（#76 審核）

#### Scenario: 規則清單是空的
- **WHEN** LLM 一條規則都沒拆出來
- **THEN** 結束代碼不為 0；`coverage.md` 寫「檢查無效」，不寫「沒有發現問題」；刪掉舊的 `coverage.json`（#76 審核）

#### Scenario: 重新產生草稿
- **WHEN** `draft` 成功產生新草稿
- **THEN** 刪掉草稿資料夾裡舊的 `coverage.json` 與 `coverage.md`，`compare` 註明「未做規則涵蓋檢查」（#76 審核）

#### Scenario: 檢查結果過期
- **WHEN** `coverage` 之後草稿的 `video.json` 有變動（`coverage.json` 記下的雜湊對不上，或沒有記雜湊），再執行 `compare`
- **THEN** 「規則陳述檢查」一節開頭標示「已過期」，請重跑 coverage；雜湊相同時不標示（#76 審核）

#### Scenario: 只給原文、旁白與字幕
- **WHEN** 執行 `coverage`
- **THEN** LLM 的輸入只有本章頁面原文、編號的旁白與字幕，不含參考頁、素材、槽位、動作

#### Scenario: 無法對應的句子編號
- **WHEN** LLM 回報的句子編號不在草稿中
- **THEN** 那一筆標為「無法對應」，其他結果照常輸出

#### Scenario: LLM 無法使用
- **WHEN** LLM 服務無法連線
- **THEN** 結束代碼不為 0，不寫 `coverage.json`

#### Scenario: 草稿或頁面不存在
- **WHEN** 指定的資料夾沒有 `video.json`，或頁面檔不存在
- **THEN** 不呼叫 LLM，結束代碼不為 0，說明缺什麼

#### Scenario: 比對報告加上規則陳述檢查
- **WHEN** 執行 `compare` 時，左邊的資料夾有 `coverage.json`
- **THEN** 報告加上「規則陳述檢查」一節，註明是 AI 檢查、僅供參考；沒有 `coverage.json` 時註明「未做規則涵蓋檢查」
