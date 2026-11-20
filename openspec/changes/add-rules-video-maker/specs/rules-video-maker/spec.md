# Spec Delta

## Purpose

規則影片生產器第 1 階段（1a＋1b）：用宣告式的段資料描述一支影片，以 `main_with_sidebar` 版型輸出靜態圖與含旁白、背景音樂的完整影片。段資料格式、版型、時間軸都不依賴特定遊戲；《血與刃》的資料只放在本機，測試使用假遊戲。句內動作本階段只有 `show`、`hide`、`flip`、`shuffle`、`move` 五種。

## ADDED Requirements

### Requirement: 段資料格式與驗證
系統 SHALL 從 `video.json` 載入一支影片：`chapters`、專案層的 `assets`、依序排列的 `segments`。每段 SHALL 有 `segment_key`、`chapter_key`、`slots`、至少一句 `beats`（`title_card` 沒有槽位也沒有句）；`template` 預設 `main_with_sidebar`。`flat_photo` 素材的檔案 SHALL 存在於 `assets/`。素材 SHALL 標記 `kind`（`flat_photo`｜`drawn`）、`priority`（`must`｜`optional`）、`usable`（`null`｜`true`｜`false`），可以宣告具名 `regions`。有旁白的段 SHALL 有 `source_pages`。格式錯誤時 SHALL 在渲染前失敗，訊息指出哪一段、哪一句、哪個欄位。

#### Scenario: 一段一張照片加字幕
- **WHEN** 某段只填 `main` 槽位（一個 `asset`）、一句、`source_pages`
- **THEN** 載入成功，`template` 為 `main_with_sidebar`，其他欄位使用預設值

#### Scenario: 缺少頂層欄位
- **WHEN** `video.json` 沒有 `game_key` 或 `title`，或它們是空白，或 `voice` 不是非空字串
- **THEN** 載入失敗，說明是哪個欄位；沒寫 `voice` 時使用 `zh-TW-YunJheNeural`

#### Scenario: 引用不存在的素材
- **WHEN** 槽位或項的 `asset_key` 不在 `assets` 中
- **THEN** 載入失敗，訊息包含 `segment_key`、槽位名稱與找不到的 `asset_key`

#### Scenario: 缺少必填槽位
- **WHEN** `main_with_sidebar` 的段沒有 `main` 槽位
- **THEN** 載入失敗，說明缺少 `main`

#### Scenario: 槽位不在版型定義中
- **WHEN** 段使用了版型沒有的槽位名稱
- **THEN** 載入失敗，列出這個版型可用的槽位

#### Scenario: 槽位內容種類不符
- **WHEN** `sidebar` 放 `items`，或 `main` 放 `bullets`
- **THEN** 載入失敗，列出該槽位可放的種類

#### Scenario: 重複的 key
- **WHEN** 段、句、素材、項、highlight、label 任一 key 重複
- **THEN** 載入失敗，指出重複的 key

#### Scenario: target 找不到
- **WHEN** cue、highlight 或 label 的 `target`，或 `move` 的 `to`，指向不存在的槽位、項、區域或 key
- **THEN** 載入失敗，指出段、句與找不到的 target

#### Scenario: 翻沒有背面的項
- **WHEN** 對沒有 `back_asset_key` 的項 `flip`
- **THEN** 載入失敗

#### Scenario: move 的目的地不是區域
- **WHEN** `move` 的 `to` 不是 `<槽位>@<區域>` 的形式
- **THEN** 載入失敗

#### Scenario: 區域超出範圍
- **WHEN** 素材 `regions` 的框超出 0–1
- **THEN** 載入失敗

#### Scenario: 使用不可用的素材
- **WHEN** 段引用 `usable=false` 的素材
- **THEN** 載入失敗，說明該素材已標記為不可用

#### Scenario: 缺少出處頁碼
- **WHEN** 有旁白的段沒有 `source_pages`
- **THEN** 載入失敗，說明旁白必須依據規則書並標示頁碼；`title_card` 不受此限

#### Scenario: 尚未支援的內容
- **WHEN** 段的 `template` 不是 `main_with_sidebar` 或 `title_card`，或槽位 `kind` 為 `player_ring`，或素材 `kind` 為 `drawn`，或 cue 的 `do` 不是五種動作之一
- **THEN** 載入失敗，訊息說明「本版尚未支援」與名稱，不靜默略過

#### Scenario: 素材檔案不存在
- **WHEN** `flat_photo` 素材的 `file` 在 `assets/` 中找不到
- **THEN** 載入失敗，訊息包含檔名

#### Scenario: 素材路徑跳出 assets/
- **WHEN** 素材的 `file` 用 `..` 或絕對路徑指到 `assets/` 以外（即使檔案存在）
- **THEN** 載入失敗，說明素材必須在 `assets/` 內

#### Scenario: crop 太小
- **WHEN** 槽位 `crop` 的寬或高小於 0.01（原圖的 1%）
- **THEN** 載入失敗，說明 crop 太小

#### Scenario: template 型別錯誤
- **WHEN** 段的 `template` 不是字串（例如數字、陣列）
- **THEN** 載入失敗並指出 template，不拋 `TypeError`

#### Scenario: 區域不在 crop 範圍內
- **WHEN** highlight、label 或 cue 用到的區域，不完全在該槽位 `crop` 的範圍內
- **THEN** 載入失敗，說明這個區域在畫面上看不到

#### Scenario: 寫了絕對時間
- **WHEN** 段或句帶有 `start_sec` 之類的絕對時間欄位，或 cue 的 `at` 小於 0
- **THEN** 載入失敗，說明時間由旁白與動作長度自動計算

### Requirement: main_with_sidebar 版型
`main_with_sidebar` SHALL 有 `main_title`（選填，`text`）、`main`（必填，`asset` 或 `items`）、`sidebar`（選填，`asset`、`text` 或 `bullets`）三個槽位。所有區塊 SHALL 位於內容區內，不壓到章節標籤與字幕列。側欄沒有內容時，`main` SHALL 放大成整個內容區。區域、highlight、label、`move` 的目的地 SHALL 依圖片實際貼上的位置換算。

#### Scenario: 有側欄
- **WHEN** 段有 `main` 與 `sidebar`（`asset`）
- **THEN** 主體區與側欄不重疊，兩者都在內容區內

#### Scenario: 沒有側欄
- **WHEN** 段只有 `main`
- **THEN** `main` 的可用範圍等於整個內容區

#### Scenario: 側欄放文字
- **WHEN** `sidebar` 為 `bullets`
- **THEN** 文字畫在側欄內，不超出側欄

#### Scenario: 一排物件
- **WHEN** `main` 為 2 項或 3 項的 `items`
- **THEN** 各項等高、等距，整排在主體區內置中

#### Scenario: 主體標題
- **WHEN** 段有 `main_title`
- **THEN** 標題位於主體上方，不與各項重疊

#### Scenario: 區域跟著圖片位置
- **WHEN** 同一個素材在不同段被縮放成不同大小
- **THEN** 同一個區域框都落在圖片上同一個相對位置（誤差 2 px 以內）

#### Scenario: 標籤位置
- **WHEN** label 的 `target` 為某一項、`position` 為 `below`
- **THEN** 標籤在該項正下方，不超出內容區；`target` 為 `items` 槽位時，以整排物件的範圍為準

#### Scenario: 文字放不下
- **WHEN** 文字換行並縮到最小字級後仍超出槽位
- **THEN** 渲染失敗，指出 `segment_key` 與槽位，不讓文字超出槽位或壓到字幕列

#### Scenario: 素材方向
- **WHEN** 素材的 `orientation` 為 90
- **THEN** 渲染前先旋轉擺正再排版

#### Scenario: 素材解析度不足
- **WHEN** 素材實際貼上的大小超過原圖尺寸的 2 倍
- **THEN** 照常渲染（一般放大，不使用 AI 放大），並在報告中列出警告

#### Scenario: 有 crop 時的區域
- **WHEN** 槽位有 `crop`，素材的 `regions` 以原圖為準記錄
- **THEN** 區域換算成裁切後圖片上的位置；框與 `move` 的目的地仍對準原圖上的同一處（誤差 2 px 以內）

#### Scenario: 字幕最多兩行
- **WHEN** 字幕斷成一行或兩行
- **THEN** 字幕框的上緣不高於內容區的下緣，下緣不低於進度條；字幕斷行後超過兩行時，排版失敗並指出段與句

#### Scenario: 標題字卡
- **WHEN** 段的 `template` 為 `title_card`
- **THEN** 不需要素材，畫面顯示影片標題與章名，長度固定 3 秒

### Requirement: 先音後畫的時間軸
系統 SHALL 先取得每句旁白的長度（MR 1 用 fake 估計，MR 3 用 TTS 實際合成），計算每句長度 `max(min_beat_sec, pad_before + 旁白長度 + pad_after, 最後一個 cue 結束 + cue_hold)`、每段長度（各句相加）與每句、每個 cue 的絕對秒數，並輸出 `timing.csv`。時間結果 SHALL NOT 回寫段資料。

#### Scenario: 一般的句子
- **WHEN** 旁白長度 3.0 秒、沒有 cue、使用預設時間規則
- **THEN** 這句長度為 3.55 秒（0.15＋3.0＋0.4）

#### Scenario: 很短的句子
- **WHEN** 旁白長度 1.0 秒、沒有 cue
- **THEN** 這句長度為 `min_beat_sec`（預設 2.6 秒）

#### Scenario: 動作比旁白長
- **WHEN** 旁白長度 3.0 秒，最後一個 cue 在第 4.0 秒開始、需要 0.8 秒
- **THEN** 這句長度為 5.1 秒（4.0＋0.8＋0.3）

#### Scenario: 改一句旁白
- **WHEN** 第 2 段某句的旁白變長 1 秒後重新計算
- **THEN** 該句以前每句的開始秒數不變，之後每句都往後移 1 秒；不需要手動修改任何時間

#### Scenario: 旁白快取
- **WHEN** 重新輸出時，某句的旁白文字與聲音都沒變
- **THEN** 不重新呼叫 TTS，使用快取的音檔

#### Scenario: 換 TTS 種類
- **WHEN** 先在 TTS 未設定（fake，靜音）時輸出，再換成 Azure 重新輸出
- **THEN** 重新合成每一句旁白，不沿用快取裡的靜音檔（快取檔名包含 TTS 種類，#75 審核）

### Requirement: 句內動作與畫面狀態
系統 SHALL 依 cue 計算第 t 秒每個槽位、項、highlight、label 的狀態，再交給版型畫出畫面。動作只有 `show`、`hide`、`flip`、`shuffle`、`move`。highlight、label 與 `hidden` 槽位預設隱藏。狀態 SHALL 以段為範圍，每段開始時重置。

#### Scenario: 顯示前隱藏
- **WHEN** 查詢某個 highlight、label 或 `hidden` 槽位在 `show` 之前與之後的狀態
- **THEN** 之前不可見，之後可見

#### Scenario: 隱藏的文字不會畫出來
- **WHEN** 輸出 `hidden` 的主體標題在 `show` 之前與之後的畫面
- **THEN** 之前標題範圍內沒有標題顏色的像素，之後有（文字的透明度確實套用到畫面）

#### Scenario: 翻牌
- **WHEN** 查詢 `flip` 之前、之中、之後的狀態
- **THEN** 之前是背面，之中寬度壓縮，之後是正面

#### Scenario: 洗牌
- **WHEN** 查詢 `shuffle` 之中與之後的狀態
- **THEN** 之中各項離開原位，之後回到原位且仍是背面

#### Scenario: 移除
- **WHEN** `hide` 一排中的某一項之後
- **THEN** 該項不可見，其他項位置不變

#### Scenario: 移進區域
- **WHEN** `move` 某一項到 `sidebar@death_zone` 結束後
- **THEN** 該項縮小並完整落在該區域內，直到段結束都留在那裡

#### Scenario: 狀態不跨段
- **WHEN** 下一段開始
- **THEN** 前一段移進區域的項、顯示的 highlight 與 label 都不出現

### Requirement: 本機指令與靜態圖
`check` 指令 SHALL 只驗證段資料。`stills` 指令 SHALL 在不使用 ffmpeg、不需要金鑰的情況下，於每句開始後 0.8 秒與每個 cue 完成時各輸出一張 1920×1080 PNG（標題字卡輸出一張；同一時間點只輸出一張），並拼成一張對照圖，另輸出時間報表 `timing.csv`（旁白長度為估計值）。

#### Scenario: 驗證通過
- **WHEN** 對正確的段資料執行 `check`
- **THEN** 結束代碼為 0，印出段數、句數與素材數

#### Scenario: 輸出靜態圖
- **WHEN** 對 2 段、3 句、4 個 cue 的假遊戲資料執行 `stills`
- **THEN** 輸出 7 張 1920×1080 PNG 與 1 張對照圖

#### Scenario: 指定字型集合檔（external）
- **WHEN** 在有微軟正黑體的電腦上，`VIDEO_FONT_REGULAR`、`VIDEO_FONT_BOLD` 指向 `msjh.ttc`、`msjhbd.ttc`，`VIDEO_FONT_INDEX` 為 0
- **THEN** 以集合中第 0 個字型輸出，不印出字型警告

#### Scenario: 沒有設定字型
- **WHEN** 沒有設定 `VIDEO_FONT_REGULAR`、`VIDEO_FONT_BOLD` 就執行 `stills`
- **THEN** 使用 Pillow 內建字型照常輸出，並印出「未設定中文字型」的警告

#### Scenario: 字型檔不存在
- **WHEN** `VIDEO_FONT_REGULAR` 指向不存在的檔案
- **THEN** 不輸出任何圖片，結束代碼不為 0，訊息指出是哪一個設定

#### Scenario: 字型集合 index 超出範圍（external）
- **WHEN** 在有微軟正黑體的電腦上，`VIDEO_FONT_INDEX` 超出 `.ttc` 的字型數量
- **THEN** 不輸出任何圖片，結束代碼不為 0，訊息指出 `VIDEO_FONT_INDEX`

#### Scenario: key 含檔名不允許的字元
- **WHEN** 段或句的 key 含 `/`、`\`、`:` 等字元
- **THEN** 靜態圖檔名把這些字元換成 `-`，全部輸出在 `stills/` 同一層

#### Scenario: 輸出到一半失敗
- **WHEN** 輸出靜態圖途中發生錯誤
- **THEN** 先前輸出的靜態圖保持原樣（新圖先寫到暫存資料夾，全部成功才取代）

#### Scenario: 段資料錯誤
- **WHEN** 對驗證失敗的段資料執行 `check` 或 `stills`
- **THEN** 不輸出任何圖片，結束代碼不為 0，印出驗證錯誤

### Requirement: 完整影片輸出
`render` 指令 SHALL 用 TTS 合成每句旁白、計算時間軸、逐格渲染每段（30 fps），以 ffmpeg 每段編碼一個 mp4 後串接，產生與影片等長的背景音樂，把旁白依時間軸放上並以 `sidechaincompress` 在旁白出現時壓低音樂，輸出 1920×1080、30 fps、H.264＋AAC 的 mp4，以及 `timing.csv` 與報告。

#### Scenario: 輸出整章影片（external）
- **WHEN** 在裝有 ffmpeg 的電腦上對假遊戲資料執行 `render`
- **THEN** 產生可播放的 mp4：1920×1080、30 fps、有音軌，長度與 `timing.csv` 的總長相差 0.1 秒以內

#### Scenario: 只重做有變的段
- **WHEN** 輸出過一次後，只改第 2 段的 `sidebar` 文字再執行 `render`
- **THEN** 只有第 2 段重新逐格渲染，其他段沿用快取的段影片；串接與混音重新執行

#### Scenario: 音軌與畫面一樣長
- **WHEN** 最後一句旁白之後還有畫面（句的後留白，或片尾的標題字卡）
- **THEN** 背景音樂一直播到片尾，音軌長度與畫面相差 0.05 秒內（#75 審核）

#### Scenario: 背景音樂長度
- **WHEN** 影片總長為 N 秒
- **THEN** 背景音樂長度為 N 秒；同樣的 N 產生相同的音樂

#### Scenario: 旁白長度改變
- **WHEN** 某句旁白變長後再執行 `render`
- **THEN** 時間有變的段重新編碼；因為每段都畫了全片進度條，同一章的段都會重做（第 1 階段的限制，報告中註明）

#### Scenario: TTS 未設定
- **WHEN** `TTS_PROVIDER` 未填或為 `fake` 時執行 `render`
- **THEN** 旁白為靜音、照常輸出；警告與報告都註明「時間為估計值」

#### Scenario: 找不到 ffmpeg
- **WHEN** 執行環境沒有 ffmpeg
- **THEN** `render` 在開始渲染前失敗，說明需要安裝 ffmpeg 或設定 `FFMPEG_PATH`

#### Scenario: TTS 無法使用
- **WHEN** TTS 服務連不上
- **THEN** `render` 失敗並說明原因（不含金鑰），已合成的旁白保留在快取，下次只補缺的
