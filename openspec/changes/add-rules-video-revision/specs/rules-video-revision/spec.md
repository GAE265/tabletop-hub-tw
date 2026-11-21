# Spec Delta

## Purpose

規則影片生產器第 2 階段：店員看完整支影片後，用自然語言提修改，只重做受影響的段；超出版型能力時，提供替代做法讓店員選，並記錄需求。

## ADDED Requirements

### Requirement: 進度條最後才疊上去
段影片 SHALL 不包含進度條；串接成整支影片後，SHALL 再把進度條疊上去。段影片的快取 SHALL 只在這段自己的內容、用到的素材、風格、字型或句長改變時失效，不受全片長度與其他段影響。靜態圖照舊包含進度條。

#### Scenario: 旁白長度改變只重做那一段
- **WHEN** 第 1 段某句旁白變長後再輸出
- **THEN** 只有第 1 段重新編碼，其他段沿用快取（第 1 階段的限制已取消）

#### Scenario: 只改畫面
- **WHEN** 只改第 2 段的側欄文字
- **THEN** 只有第 2 段重新編碼

#### Scenario: 段影片不含進度條
- **WHEN** 編碼某一段
- **THEN** 畫面的進度條位置是背景色，沒有進度條

#### Scenario: 靜態圖仍有進度條
- **WHEN** 執行 `stills`
- **THEN** 靜態圖照舊畫出進度條

#### Scenario: 疊加進度條
- **WHEN** 輸出整支影片
- **THEN** 串接後另外呼叫一次 ffmpeg，把逐格畫出的進度條疊到影片上；這一步失敗時不留暫存檔、不產生成品

#### Scenario: 成品的進度條（external）
- **WHEN** 用真的 ffmpeg 輸出整章影片
- **THEN** 成品在第 t 秒的進度條填滿比例約為 t ÷ 總長（誤差 2% 以內），解析度、幀率、音軌與第 1 階段相同

#### Scenario: 二次編碼的畫質（external）
- **WHEN** 比較疊加前與成品（不含進度條那一條）
- **THEN** SSIM 不低於 0.98（2026-11-21 永傑要求檢查畫質）

### Requirement: 用自然語言修改
`revise` 指令 SHALL 把修改要求、目前每一段的內容與版型能做的事交給 LLM，取得受影響的段的完整新內容，只取代這些段。新段的 `segment_key` SHALL 與原本相同，不可新增或刪除段。修改後 SHALL 通過正式模式的段資料驗證與用語檢查（不用「次」、對照表 `avoid`）；不通過就要求 LLM 改寫一次，仍不通過就不寫入。寫入前 SHALL 把原本的 `video.json` 備份到 `revisions/<編號>-before.json`。

#### Scenario: 只改受影響的段
- **WHEN** 修改要求是「情況二的紅框改成金框」，LLM 回傳第 2 段的新內容
- **THEN** 只有第 2 段被取代，其他段的內容完全相同

#### Scenario: 不能改段的 key 或增刪段
- **WHEN** LLM 回傳的段 `segment_key` 不在原本的段中，或少了、多了段
- **THEN** 視為不通過，進入改寫

#### Scenario: 修改後不通過檢查
- **WHEN** 修改後的旁白用了「次」，改寫後仍然有
- **THEN** 不寫入 `video.json`，結束代碼不為 0，保留兩次原始輸出

#### Scenario: 備份
- **WHEN** 修改成功
- **THEN** 原本的 `video.json` 存在 `revisions/<編號>-before.json`，編號從 1 開始遞增

#### Scenario: 試算（dry run）
- **WHEN** 加上 `--dry-run`
- **THEN** 印出會改哪些段、哪些欄位，不寫入 `video.json`、不備份；提案存成 `revisions/pending.json`

#### Scenario: 套用試算的提案
- **WHEN** dry-run 之後執行 `revise <資料夾> --apply`
- **THEN** 不呼叫 LLM，直接套用 `pending.json` 的提案，照常備份與寫修改紀錄

#### Scenario: 試算後草稿被改過
- **WHEN** dry-run 之後 `video.json` 有變動，再執行 `--apply`
- **THEN** 拒絕套用，結束代碼不為 0，請店員重跑

#### Scenario: 沒被要求改的欄位
- **WHEN** 修改要求只提到 highlight，LLM 卻也改了旁白
- **THEN** 欄位差異把旁白標為「未被要求修改」，修改紀錄的 `unrequested` 記下 `narration`；指示有要求沒被點名的欄位原文不動

#### Scenario: 一次改超過 2 段
- **WHEN** LLM 回傳 3 段的新內容
- **THEN** 照常處理，輸出中提醒店員確認改了 3 段

#### Scenario: 目標不明確
- **WHEN** 多段都符合修改要求（例如「把紅框改成金框」，兩段都有紅框），LLM 回傳候選段
- **THEN** 不寫入，列出候選段與理由，提示用 `--segment <段>` 指定

#### Scenario: 指定段
- **WHEN** 加上 `--segment s2`，LLM 卻回傳 s1 的新內容
- **THEN** 視為不通過，進入改寫

#### Scenario: 寫入後的涵蓋檢查
- **WHEN** 加上 `--pages`，修改寫入後涵蓋檢查發現被改的段少了條件
- **THEN** 印出警告，`video.json` 照樣寫入，結束代碼為 0；和被改的段無關的結果不顯示

#### Scenario: 寫入後的涵蓋檢查失敗
- **WHEN** 涵蓋檢查的 LLM 無法使用或回空清單
- **THEN** 只印警告，修改照樣寫入

#### Scenario: LLM 無法使用
- **WHEN** LLM 服務無法連線
- **THEN** 結束代碼不為 0，`video.json` 不變

### Requirement: 修改紀錄
每一段被修改時，SHALL 在該段的 `revisions` 新增一筆：編號、時間（UTC）、`by`、`kind`、修改要求、`changed`（由程式比對新舊段算出）、`unrequested`（被改但沒被要求的欄位）、說明；並把 `state.status` 設為 `stale`。`render` 成功後，被重新編碼的段 SHALL 把 `state.status` 改為 `rendered`，並記下 `content_hash`。

#### Scenario: 修改紀錄
- **WHEN** 第 2 段只改了 highlight
- **THEN** 第 2 段的 `revisions` 多一筆，`changed` 為 `["highlights"]`，`state.status` 為 `stale`；其他段的 `revisions` 不變

#### Scenario: 輸出後更新狀態
- **WHEN** 修改後執行 `render`
- **THEN** 第 2 段的 `state.status` 改為 `rendered`，`state.content_hash` 為這次的雜湊

### Requirement: 超出版型能力時
LLM 判斷修改要求超出版型能力時，`revise` SHALL 不寫入 `video.json`，而是把 1 到 3 個替代做法存到 `revisions/pending.json` 並印出；把需求（要求、原因、時間）記到 `revisions/requests.json`。店員用 `--choose <編號>` 選擇替代做法後，SHALL 照「用自然語言修改」的規則套用，修改紀錄的 `kind` 為 `alternative`，並記下原本的要求。

#### Scenario: 超出能力
- **WHEN** 修改要求是「讓牌旋轉著飛進盤面」（沒有旋轉動作），LLM 回報超出能力
- **THEN** `video.json` 不變；印出替代做法；`requests.json` 多一筆需求

#### Scenario: 替代做法在產生時就檢查
- **WHEN** LLM 提出的替代做法不通過檢查（例如旁白用了「次」）
- **THEN** 照「改寫一次」的規則要求 LLM 重新提出；存進 `pending.json` 的替代做法一定能用 `--choose` 套用（3.3 本機驗收發現）

#### Scenario: segment_json 省略了 segment_key
- **WHEN** LLM 在 `segment_json` 裡沒寫 `segment_key`，外層有寫
- **THEN** 用外層的 `segment_key` 補上；兩邊都有但不一樣時才算錯（3.3 本機驗收發現）

#### Scenario: 用了五種以外的動作
- **WHEN** LLM 回「可以做」，但新內容的 `do` 是 `rotate`
- **THEN** 不走改寫，改為再呼叫一次 LLM 取得替代做法；`requests.json` 記下不支援的動作 `rotate`；`video.json` 不變

#### Scenario: 選替代做法
- **WHEN** 之後執行 `revise <資料夾> --choose 2`
- **THEN** 套用第 2 個替代做法，修改紀錄的 `kind` 為 `alternative`，`request` 是原本的要求；`pending.json` 清空

#### Scenario: 沒有待選的替代做法
- **WHEN** 沒有 `pending.json` 就執行 `--choose 1`，或編號超出範圍，或 `pending.json` 是 dry-run 的提案
- **THEN** 結束代碼不為 0，說明原因，`video.json` 不變
