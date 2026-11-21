# Proposal

## Why

規則教學（`add-rules-qa`）讓有教學影片的遊戲先看影片再發問，但目前只有 3 款遊戲有組內自製的影片。要讓更多遊戲有影片，得由店家自己做；而店家沒有時間寫腳本、配音、剪片。

規則影片生產器的完整規格與決策在根目錄的 `影片生產器規格.md`（由 `CLAUDE.md` 引用）。產品流程是：店員上傳規則書照片 → AI 決定放哪些規則並列出最小素材清單 → 店員拍素材 → AI 用版型組裝影片並自動檢查 → 店員看完提修改、只重做受影響的段。

規格分四個開發階段，每階段結束要能實際看到結果、確認後才進下一階段。**本 change 只做第 1 階段的 1a 與 1b**：用手寫的段資料，以單一版型 `main_with_sidebar` 輸出《血與刃》「步驟三」的完整影片（畫面、旁白、背景音樂），與手做版本比較，證明「宣告式段資料 → 影片」的骨架能跑通。

> 《血與刃》是版型的來源，這一步只能證明流程能跑通，不能證明通用性（規格檔「開發階段」）。

## What Changes

- **段資料格式**（宣告式，不逐款遊戲寫程式）：一支影片＝專案層的素材清單＋依序排列的段；每段有 `template`、具名 `slots`（可放單一素材、一排物件或文字）、`highlights`、`labels`、逐句的 `beats`（旁白＋字幕＋句內動作 `cues`，動作只有 show、hide、flip、shuffle、move 五種）、時間規則、出處頁碼（旁白只能依據規則書）、獨立狀態與修改紀錄。「一段一張照片加字幕」是只填 `main` 槽位、只有一句的最簡單情況。
- **版型引擎**（`backend/app/integrations/video/`）：`main_with_sidebar` 版型與內建的標題字卡；用相對比例與文字墨水框排版，不用絕對座標；風格依《血與刃》製作紀錄。
- **先音後畫的時間軸**：先取得每句旁白的實際長度（靜態圖用 fake 估計），句長取旁白與句內動作較長者，再算出每句、每段、每章的絕對時間；段資料裡不存絕對秒數。
- **輸出**：逐格渲染 → ffmpeg 每段一個 mp4 → 串接 → 程式合成背景音樂 → 旁白＋音樂 `sidechaincompress` 混音，輸出 1920×1080、30 fps 的 mp4；另輸出每段靜態圖與時間報表。
- **文字轉語音**（`backend/app/integrations/tts/`）：介面、fake、Azure AI Speech（REST，用既有的 `httpx`）。
- **本機指令**（`backend/app/domains/rules_qa/video_commands.py`）：讀本機的段資料與素材，輸出靜態圖或完整影片。
- `.gitignore` 加上本機工作資料夾：規則書照片、素材、手做影片、《血與刃》的段資料只放本機（規格決定 A2）。
- `GLOSSARY.md` 新增本功能的提案術語（段、句、版型、槽位等）。

**不做（留給之後的 change）**：AI 產生段資料與素材清單（1c）、後端 API、資料表與前端精靈（1d）、修改流程（第 2 階段）、其他版型與完整自動檢查（第 3 階段）、拍攝偵測（第 4 階段）、4K、AI 放大（Real-ESRGAN）。

## Capabilities

### New Capabilities
- `rules-video-maker`：段資料格式與驗證、`main_with_sidebar` 版型、時間軸、句內動作與畫面狀態、靜態圖與整章影片輸出、背景音樂與混音、本機指令。
- `media-integrations`：`tts`、`storage`、`video` 轉接層的介面與 fake 行為（`storage` 已於 #42 合併）。

### Modified Capabilities
- 無。發布為教學影片（寫入 `rules_qa_videos`）移到 1d。

## Impact

- **受影響 domain**：`rules_qa`（主責永傑），只新增本機指令，不改既有行為。
- **共用區**：`integrations/tts/`、`integrations/video/`（擁有者永傑，AGENTS.md 1.11）；`backend/app/core/config.py`、`.env.example`（立倫）新增設定，MR 要 @ 立倫。
- **新增套件**（組內已同意，MR 說明仍要寫理由）：`Pillow`（畫面）、`numpy`、`scipy`（背景音樂合成）。
- **系統元件**：本機需要 ffmpeg；字型本階段用 Windows 內建的微軟正黑體（`msjh.ttc`、`msjhbd.ttc`），之後可換成 Noto Sans／Serif CJK TC；部署設定留到 1d。
- **契約**：無（不新增 API）。
- **migration**：無。
- **資料**：《血與刃》的規則書、素材、手做影片與段資料只放本機並列入 `.gitignore`；測試只用程式產生的假圖片與自行編寫的假遊戲段資料。
- **金鑰**：Azure Speech 金鑰只放 `.env` 與 Azure 伺服器設定（規格決定 A1），不寫進程式碼、不貼進對話。
- **不修改** `AGENTS.md`、`CLAUDE.md`、`openspec/changes/archive/`。
