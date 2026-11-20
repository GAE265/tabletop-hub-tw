# Design

## Context

- 規格與決策：根目錄 `影片生產器規格.md`。版型依據：`版型分類_1.csv`（三支手做影片 163 個取樣畫面）。做法來源：`製作紀錄_血與刃.md`（風格、旁白、背景音樂、混音）；另兩份紀錄只取「踩過的坑」。
- 產品第一版鎖定素材需求少的遊戲，以《血與刃》為代表；《阿不思學院》《馬可波羅》不是第一版的目標類型。
- 組內決定（2026-11-20）：
  - A1 金鑰放 `.env` 與 Azure 伺服器設定；A2 規則書與影片只放本機並列入 `.gitignore`；A3 版型引擎放 `integrations/video/`、專案流程放 `rules_qa`；A4 同意新增 Pillow、numpy、scipy；A5 新術語寫進 `GLOSSARY.md`。
  - C1–C5 依規格檔修改；輸出 1920×1080、30 fps，加背景音樂。
- 第 1 階段的驗證對象（2026-11-20）：《血與刃》「步驟三」（手做版 138.15–170.15 秒，章節編號 11，4 句旁白），本機資料在 `backend/.local/rules_video/`：
  - `reference/`：手做版影片 `血與刃_步驟三_139-170s.mp4`、畫面總覽、`步驟三_旁白與字幕.csv`（旁白與字幕的文字來源；其中的 `start_sec`、`slot_sec` 只用於比對，不寫進段資料）。
  - `assets/`：從 4K 影片裁出的牌背、白薔薇、幽魂、信者、暗刃、巨刃與遊戲盤面。
  - 沒有背景圖，先用暗色漸層；旁白聲音 `zh-TW-YunJheNeural`；這一章不需要玩家環形。
- `integrations/storage/` 已於 #42 合併；`tts/`、`video/` 尚未建立。三者的擁有者為永傑（AGENTS.md 1.11）。

## Goals / Non-Goals

**Goals（第 1 階段 1a＋1b）：**
- 手寫一份《血與刃》步驟三的段資料，一個指令輸出整章影片（畫面＋旁白＋背景音樂），與手做版比較。
- 資料結構現在就預留 template、slots、assets、獨立狀態與修改紀錄，之後加版型、修改流程、偵測時不用改格式。
- 把三份紀錄「踩過的坑」中能在本階段處理的，做成結構上不會發生或自動報告的防呆（D9）。

**Non-Goals：** AI 產生段資料與素材清單（1c）、API／資料表／前端（1d）、修改流程（第 2 階段）、其他版型與完整自動檢查（第 3 階段）、拍攝偵測（第 4 階段）、4K 輸出、AI 放大、玩家環形的渲染、五種以外的動作。

## Decisions

**D1 程式放在哪裡。**

| 位置 | 內容 | 理由 |
|---|---|---|
| `integrations/video/` | 段資料模型與驗證、版型、風格、排版、時間軸、畫面狀態、逐格渲染、ffmpeg 編碼與串接、背景音樂合成、混音 | 版型必須通用、不能知道任何遊戲或 domain（4.2）；A3 |
| `integrations/tts/` | `TTSProvider` 介面、fake、Azure 實作 | 外部服務一律包在介面後面（4.2） |
| `domains/rules_qa/video_commands.py` | 本機指令：讀本機資料夾、呼叫 TTS 與 video、寫出結果 | 沿用 `rules_qa/commands.py` 的指令稿寫法；之後的專案流程也在 `rules_qa`（A3） |

本機工作資料夾：`backend/.local/rules_video/`（列入 `.gitignore`），內含 `video.json`（段資料）、`assets/`、`reference/`、`out/`（輸出）、`cache/`（旁白與段影片快取）。

**D2 段資料格式。**

一個 `video.json` 描述一支影片（本階段＝一章）：

```jsonc
{
  "format_version": 1,
  "game_key": "blades_and_rose",
  "title": "血與刃的白薔薇 規則教學",
  "voice": "zh-TW-YunJheNeural",
  "chapters": [ { "chapter_key": "c11", "number": 11, "title": "步驟三" } ],
  "assets": [ /* 素材 */ ],
  "segments": [ /* 段 */ ]
}
```

段（segment）：

| 欄位 | 必填 | 說明 |
|---|---|---|
| `segment_key` | 是 | 穩定 id，建立後不改；插段時不用重新編號 |
| `chapter_key` | 是 | 屬於哪一章，用於章節標籤與進度條 |
| `template` | 否 | 預設 `main_with_sidebar`；本階段另有內建的 `title_card` |
| `slots` | 是 | 具名槽位 → 槽位內容；哪些槽位必填、可放哪些內容由版型定義（D3） |
| `highlights` | 否 | 框選或打叉：`key`、`target`、`shape`（`box`｜`cross`）、`style`（`gold`｜`red`）；預設隱藏，由 cue 顯示 |
| `labels` | 否 | 標籤：`key`、`text`、`target`、`position`（`below`｜`above`｜`center`）、`style`（`plain`｜`gold`｜`red`）；預設隱藏，由 cue 顯示 |
| `beats` | 是 | 至少一句；每句 `beat_key`、`narration`（口語旁白）、`subtitle`（書面字幕）、`keywords`（字幕上色，選填）、`cues`（句內動作，選填） |
| `timing` | 否 | `min_beat_sec`（預設 2.6）、`pad_before`（0.15）、`pad_after`（0.4）、`cue_hold`（0.3）；只存規則，不存絕對秒數 |
| `transition_in` | 否 | `cut`（預設）或 `fade`；轉場是段的屬性，不是一段 |
| `source_pages` | 有旁白的段必填 | 旁白依據的規則書頁碼，例如 `[{"lang": "zh", "page": 7}]`；旁白只能依據規則書，這個欄位讓店員核對。`title_card` 免填 |
| `state` | 否 | 預留：`status`（`draft`／`approved`／`rendered`／`stale`）、`content_hash`、`render`、`checks`；本階段只寫入 `content_hash` 與 `render`，不回寫 `video.json` |
| `revisions` | 否 | 預留：修改紀錄（`number`、`at`、`by`、`kind`、`request`、`changed`）；本階段不寫入 |

槽位內容（`kind`）：

| kind | 內容 |
|---|---|
| `asset` | `asset_key`，選填 `crop`（相對比例） |
| `items` | 一排物件：`items: [{item_key, asset_key, back_asset_key?}]`；有 `back_asset_key` 的項從背面開始 |
| `text` | `text`、選填 `title`、`emphasis` |
| `bullets` | `items`、選填 `title`、`emphasis` |
| `player_ring` | 只保留名稱，本階段載入時回「尚未支援」 |

任何槽位都可以加 `"hidden": true`，由 cue 顯示。

`target` 的寫法：`main`、`main.c2`（`items` 中的某一項）、`sidebar`、`sidebar@death_zone`（該槽位素材上的具名區域）、`main_title`，以及 highlight／label 的 `key`。

句內動作（cue），**本階段只有五種，不再新增**：

| `do` | 對象 | 效果 |
|---|---|---|
| `show` | 隱藏的槽位、項、highlight、label | 彈出或淡入（`anim`: `pop`｜`fade`，預設 `pop`） |
| `hide` | 項、highlight、label | 淡出；同一排的其他項位置不變 |
| `flip` | 有背面的項，或整個 `items` 槽位 | 寬度壓縮再展開，背面換成正面 |
| `shuffle` | `items` 槽位 | 幾張牌交換位置後回到原位（`duration` 秒） |
| `move` | 項，`to` 為某個區域 | 飛進區域並縮小到區域內，留到段結束 |

每個 cue 有 `at`：從該句開始算的秒數（相對時間，≥ 0）。畫面狀態以段為範圍：每段開始時全部重置，移進區域的物件不會帶到下一段。

素材（asset，專案層，可跨段共用；只列觀眾必須讀到資訊的素材）：

| 欄位 | 說明 |
|---|---|
| `asset_key` | 唯一名稱 |
| `kind` | `flat_photo`（實拍平面素材）或 `drawn`（程式繪製的立體素材；本階段只保留名稱，使用時回「尚未支援」） |
| `priority` | `must`（必拍）或 `optional`（選拍） |
| `reason` | 觀眾必須從這個素材讀到什麼資訊 |
| `shot` | 要拍什麼、怎麼拍（選填） |
| `file` | 檔案（相對 `assets/`） |
| `regions` | 選填，具名區域 → `[x, y, w, h]`（相對圖片的 0–1 比例）；每個素材量一次 |
| `orientation` | 0／90／180／270，渲染前旋轉擺正 |
| `usable` | `null`（還沒確認）／`true`／`false`；`false` 的素材不能被使用 |
| `quality` | 預留給第 4 階段 |

「一段一張照片加字幕」：

```jsonc
{ "segment_key": "s01", "chapter_key": "c11", "source_pages": [{"lang": "zh", "page": 7}],
  "slots": { "main": { "kind": "asset", "asset_key": "board" } },
  "beats": [ { "beat_key": "b1", "narration": "…", "subtitle": "…" } ] }
```

只填必填的 `main`、只有一句、沒有 cue，其餘用預設值；沒有另外寫死的路徑。

**《血與刃》步驟三的分段**（只放本機，不提交）：

| 段 | 句 | 內容 |
|---|---|---|
| s1 | 11-0、11-1 | 三張背面 → shuffle → flip（白薔薇、幽魂、信者）→ show「情況一」→ 幽魂下 show「移除」→ hide 幽魂 → show 白薔薇區、犧牲區金框 → move 白薔薇、信者進對應的區 |
| s2 | 11-2 | 三張背面 → shuffle → flip（信者、暗刃、幽魂）→ show「情況二」→ 移除幽魂 → show 死亡區紅框 → move 信者進死亡區 → move 暗刃進血刃區（`sidebar@blade_zone`，2026-11-20 永傑更正，與手做版相同） |
| s3 | 11-3 | 兩張背面（手做版的飛入改成彈出）→ flip（白薔薇、巨刃）→ show「情況三」→ 白薔薇 show 紅色打叉（highlight `cross`）→ show 紅色標籤「血刃陣營立刻獲勝！」 |

驗證（載入時就失敗，訊息指出哪一段、哪一句、哪個欄位）：任何 key 重複；引用不存在的素材、章、項、區域、highlight、label；版型缺必填槽位、槽位名稱不在版型中、槽位內容種類不符；對沒有背面的項 `flip`；`move` 的 `to` 不是區域；區域超出 0–1；cue 的 `at` 小於 0；使用 `usable=false` 的素材；有旁白的段沒有 `source_pages`；尚未支援的版型、`kind`、`do`；出現 `start_sec` 等絕對時間欄位；`format_version` 不認得。

**D3 `main_with_sidebar` 版型。**

| 槽位 | 必填 | 可放 | 位置 |
|---|---|---|---|
| `main_title` | 否 | `text` | 主體區上方，金色襯線字 |
| `main` | 是 | `asset`、`items` | 主體區 |
| `sidebar` | 否 | `asset`、`text`、`bullets` | 右側；本章放固定的遊戲盤面 |

- 畫面分區（相對 1920×1080）：左上章節標籤、中間內容區、下方字幕列與進度條；內容區不會壓到標籤與字幕列。
- 側欄沒有內容時，`main` 放大成整個內容區。主體與側欄比例、邊距、字級放在風格設定（D4），第一版對照手做版截圖調整。
- 圖片等比例縮放到槽位內並置中；`items` 等高、等距、整排置中。區域、highlight、label、`move` 的目的地都依圖片實際貼上的位置換算，所以不會因縮放而漂移。
- 文字用墨水框（`textbbox`）量測與置中；放不下時先換行、再縮字級到下限，仍放不下就報錯，不讓文字超出槽位。
- 內建 `title_card`：影片標題＋章名，不需要素材，固定 3 秒。

**D4 風格（依《血與刃》製作紀錄 4.2）。**
- 背景：暗色漸層加暗角（之後可換背景圖，每段稍微位移）。
- 字幕列：圓角深色底，一行或兩行（超過 1500 px 換行），出現時淡入並上移 14 px；`keywords` 上色。
- 章節標籤：左上角「編號 章名」（本章「11 步驟三」）。進度條：底部分段，每章一段、目前這一章依時間填滿；本階段只有一章，只有一段（與手做版的差異，比對時排除）。
- highlight：`gold` 金框、`red` 紅框；`cross` 為紅色叉。label：`red` 為紅底白字圓角標籤，`plain` 為小字。
- 動畫時間：彈出 0.4 秒（`e_back`）、淡入淡出 0.3 秒、翻牌 0.5 秒、移動 0.8 秒；這些數值放在風格設定。
- 字型（2026-11-20 決定）：用 Windows 內建的微軟正黑體，一般字重（字幕、標籤）用 `msjh.ttc`，粗體（標題）用 `msjhbd.ttc`。設定直接指定檔案：`VIDEO_FONT_REGULAR`、`VIDEO_FONT_BOLD`（MR 1 加入），`.ttc` 是字型集合檔，用 `VIDEO_FONT_INDEX`（預設 0）選字型，`.ttf`／`.otf` 忽略此值。之後要換成 Noto Sans／Serif CJK TC 時，只改設定，不改程式。
  - 沒有設定時退回 Pillow 內建字型，並印出「未設定中文字型」的警告。CI 沒有中文字型，單元測試用退回字型與英數文字。
  - 有設定但檔案不存在、或 index 超出集合範圍時，在渲染前失敗並說明是哪一個設定，不靜默退回。
  - 與手做版比對時，字型不同（手做版是 Noto，標題是襯線字）列為已知差異，不算不合格。
- 風格是一份資料，不寫在版型裡；之後換遊戲風格只換這份資料。

**D5 時間軸（先音後畫）。**
1. 取得每句旁白的長度：MR 1 用 `FakeTTSProvider` 估計（`stills` 不需要金鑰）；MR 3 用 TTS 實際合成並量長度，以 `voice＋文字` 的雜湊快取。
2. 每句長度 = `max(min_beat_sec, pad_before + 旁白長度 + pad_after, 最後一個 cue 結束 + cue_hold)`；每段＝各句相加（`title_card` 固定 3 秒）；每章＝各段相加。
3. 依段的順序算出每句、每個 cue 的絕對秒數，寫進時間報表，不回寫段資料。
- 時間由實際旁白長度與動作長度算出，**旁白不可能超出時段、動作不會被下一句切掉**；改了某一句，後面的時間自動重算。
- 時間報表（`out/timing.csv`，UTF-8 BOM）：`segment_key, beat_key, start_sec, beat_sec, audio_sec, chars, subtitle`；比對時與 `reference/步驟三_旁白與字幕.csv` 並列。

**D6 畫面狀態與靜態圖（MR 1）。**
- `frame_at(video, timeline, t)`：先算出第 t 秒每個槽位、項、highlight、label 的狀態（是否可見、正反面、位置、動畫進度），再交給版型畫出 1920×1080 的畫面。狀態計算與畫圖分開，狀態可以不畫圖就測試。
- `stills`：每句開始後 0.8 秒一張、每個 cue 完成時一張 PNG，另拼成一張對照圖（`out/stills/`、`out/sheet.png`），不需要 ffmpeg。

**D7 編碼（MR 3）。**
- 逐格產生 rgb24 → 管線送 ffmpeg（`libx264 -crf 18 -preset veryfast -pix_fmt yuv420p`、1920×1080、30 fps），每段一個 mp4，先寫 `.tmp.mp4` 再改名；以 concat demuxer `-c copy` 串接。沒有動畫的時間重複同一格，不重畫。
- 每段影片以 `content_hash`（段內容＋用到的素材檔＋風格＋各句長度）快取；沒變的段不重新渲染。這是第 2 階段「只重做一段」的基礎。
- 不使用 AI 放大；素材貼上大小超過原圖 2 倍時，在報告中警告。

**D8 背景音樂與混音（MR 3，依《血與刃》製作紀錄 7、8）。**
- 背景音樂：和弦鋪墊、持續低音、鈴聲、風聲、低沉重擊（只放在章的開頭）、殘響與淡入淡出，長度等於影片總長；固定亂數種子，同樣長度得到同樣的音樂。
- 混音：每句旁白依開始秒數 `adelay` → `amix`（`normalize=0`）→ `loudnorm`（I=-20, TP=-2, LRA=7）→ `asplit` 一份當 sidechain；音樂 × `VIDEO_MUSIC_VOLUME`（預設 0.25）→ `sidechaincompress`（threshold 0.03、ratio 6、attack 40、release 900）→ 與旁白 `amix` → `loudnorm`（I=-16, TP=-1.5, LRA=11）→ 48 kHz、AAC 192k；`-shortest`、`+faststart`。
- 產出：`out/<game_key>.mp4`、`out/silent.mp4`、`out/bgm.wav`、`out/timing.csv`、`out/report.txt`。

**D9 本階段內建的防呆（規格檔「踩過的坑」）。**

| 坑 | 本階段的做法 |
|---|---|
| 改場景長度導致後面時間位移 | 段資料不存絕對秒數，時間軸每次重算（D5） |
| 旁白超出時段 | 時段由旁白實際長度決定（D5） |
| 素材方向 | `orientation` 欄位在渲染前擺正；自動偵測方向留到第 3 階段 |
| Real-ESRGAN 破壞小字 | 不做 AI 放大，解析度不足只警告（D7） |
| 絕對座標因自動縮放而漂移 | 只用相對比例；區域、標籤、移動目的地依圖片實際位置換算（D3） |
| 文字壓到字幕列、超出畫面 | 內容區與字幕列分開；文字放不下就報錯（D3）。重疊、對比等完整檢查留到第 3 階段 |
| 規則憑記憶 | 有旁白的段必須有 `source_pages`（D2） |

**D10 文字轉語音（`integrations/tts/`，MR 2）。**
- `TTSProvider.synthesize(text, voice) -> AudioClip(data: bytes, seconds: float)`，輸出 wav（48 kHz、16-bit、mono）。
- Azure 實作：REST `https://{region}.tts.speech.microsoft.com/cognitiveservices/v1`，SSML `xml:lang='zh-TW'`，用既有的 `httpx`；429 時等待後重試；指令依序合成並間隔約 3.3 秒（免費層每分鐘約 20 次）。
- fake：依字數產生靜音 wav（每 4 個字 1 秒，至少 1 秒）。
- 設定：`TTS_PROVIDER`（`fake`｜`azure`）、`TTS_REGION`、`TTS_API_KEY`、`TTS_VOICE`（預設 `zh-TW-YunJheNeural`，段資料的 `voice` 優先）。沒填時用 fake。

**D11 本機指令。**
```
uv run python -m app.domains.rules_qa.video_commands check  <資料夾>   # 只驗證段資料（MR 1）
uv run python -m app.domains.rules_qa.video_commands stills <資料夾>   # 靜態圖與對照圖（MR 1，不需要 ffmpeg）
uv run python -m app.domains.rules_qa.video_commands render <資料夾>   # 完整影片（MR 3，需要 ffmpeg 與 TTS）
```
其他設定：`VIDEO_FONT_REGULAR`、`VIDEO_FONT_BOLD`、`VIDEO_FONT_INDEX`（MR 1）；`FFMPEG_PATH`（預設 `ffmpeg`）、`VIDEO_MUSIC_VOLUME`（MR 3）。

**D12 測試。**
- 單元測試（不需要 ffmpeg、金鑰）：段資料驗證、版型排版、時間軸、畫面狀態、`content_hash`、背景音樂、`FakeTTSProvider`、靜態圖輸出。
- 外部服務測試（`@pytest.mark.external`，本機手動）：Azure TTS 實際合成；ffmpeg 實際編碼、串接、混音；微軟正黑體 `.ttc` 的載入與 index 檢查。缺少 ffmpeg、字型或金鑰時直接失敗並說明。
- 測試資料：程式產生的小 PNG＋自行編寫的假遊戲段資料，放在 `backend/tests/integrations/video/`；不使用《血與刃》的任何素材。
- Draft MR 的情境表格依類別分組（資料格式、版型排版、時間軸、畫面狀態、指令），每一行標示對應的測試。

**D13 拆成三個 MR。**
1. MR 1（1a，分支 `feature/integrations-video-segments`）：段資料、版型、風格、時間軸（用 fake 估計旁白長度）、畫面狀態、靜態圖；`video_commands check／stills`；設定 `VIDEO_FONT_REGULAR`、`VIDEO_FONT_BOLD`、`VIDEO_FONT_INDEX`；`.gitignore`；`GLOSSARY.md`；新增 Pillow、numpy。
2. MR 2：`integrations/tts/`（介面、fake、Azure、external 測試）。
3. MR 3（1b）：TTS 接上時間軸、逐格渲染與編碼、背景音樂、混音；`video_commands render`；新增 scipy。

MR 1 與 MR 2 可以平行；MR 3 需要兩者先合併。

## Risks / Trade-offs

- **[只能證明流程跑得通]** 《血與刃》是版型來源。→ 規格已註明；通用性等第二款低素材遊戲再驗證。
- **[排版數值對照截圖調整]** 第一版的比例與字級來自手做版截圖，可能只適合《血與刃》。→ 數值放在風格資料，不寫進版型。
- **[動作只有五種]** 其他遊戲可能需要更多動作。→ 本階段鎖定五種；需要新動作時記錄下來，到第 2、3 階段再評估。
- **[逐格渲染速度]** 1920×1080、30 fps 用 Pillow 逐格畫。→ 沒有動畫的時間重複同一格；每段快取。
- **[TTS 費用與速率]** → 以文字雜湊快取；`stills` 用 fake。
- **[字型與 ffmpeg 不在 CI]** → ffmpeg 相關測試歸 external；字型退回 Pillow 內建字型，其他測試不依賴它們。
- **[微軟正黑體只在 Windows]** 部署到 Linux 容器時沒有這個字型。→ 本階段只在本機執行；部署時（1d）改用可隨映像安裝的 Noto，只改設定。
- **[本機資料遺失]** 規則書與素材不進 git。→ 由永傑自行備份本機資料夾。

## Open Questions

無。已結案：
1. 情況二的暗刃移進盤面右上的血刃區，與手做版相同（2026-11-20 永傑更正；原先決定不移動）。
2. 步驟三的 `source_pages` 為英文版規則書 RC1 PDF 第 5 頁（`lang=en, page=5`）（2026-11-20）。
