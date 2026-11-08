# 桌遊基本資料從哪裡取得：資料來源比較

> **更正（2026-11-06）**：本文關於 BGG「不得把資料用在 AI／LLM」的結論已過時。立倫用瀏覽器核對現行網站條款 6.B.iv，標題為「General-purpose AI use is permitted」：允許把網站內容交給 AI 系統（含 LLM）做摘要、翻譯、搜尋、回答問題等一般用途，只禁止大型 AI 公司拿來訓練或微調模型。本文讀到的是 2026-10-18 存檔的舊版。現況見 [核對 BGG 使用條款原文](../issues/15-verify-bgg-terms.md)。

- Ticket：[02 桌遊基本資料從哪裡取得](../issues/02-game-data-sources.md)
- 調查日：2026-11-06。下文所有來源的存取日都是這一天，來源清單在文末，內文用 `[B1]`、`[W1]` 這類代號引用。
- 範圍：只看桌遊基本資料，包括條件欄位（人數、時長、年齡）、偏好欄位（主題、機制、難度），以及說明文字、圖片、繁中名稱。心得來源屬於 ticket 03，這裡不談。
- 本檔不含任何下載的桌遊資料，只有條款摘錄、欄位說明與彙總數字。

## 證據等級

| 標記 | 意思 |
|---|---|
| 已確認 | 直接讀到原文，或自己呼叫 API 實測 |
| 間接 | BGG 網站對非瀏覽器用戶端（WebFetch、curl）一律回 Cloudflare 403，這次無法直接打開。內容來自搜尋引擎索引到的 BGG 官方頁面原句，或 BGG 員工的公開發言。可以拿來判斷方向，上線前要有人用瀏覽器打開原頁核對 |
| 二手 | 第三方開發者的整理，只當佐證 |
| 未確認 | 查不到，或無法實測 |

## 結論

1. **BGG 的資料最完整，但目前不能用在我們的 LLM 推薦 Agent。** BGG 網站條款寫明不得把網站資料「拿去訓練 AI 或 LLM，或以其他方式當成 AI／LLM 系統的資料」[B4]，XML API 條款也納入這條 [B2]。BGG 主要開發者 Daniel Karp 在 2026-10-13 公開說明：依現行條款，把 BGG 資料當成 AI 或 LLM 的輸入不被允許，即時查詢也算在內；條款正在調整，方向可能是「回答附上 BGG 連結就允許」[B5]（已確認）。
2. **繁中名稱沒有可以自動匯入的可靠來源。** BGG 別名沒有語言標記 [B9]；Wikidata 的 `zh-tw` 標籤在 4,757 款有 BGG ID 的桌遊中只有 29 款 [W5]。具公信力的繁中名稱來源是台灣代理商的官方商品頁 [T1][T2]，但沒有 API，版權全部保留，只能人工查核。
3. **建議組合：** Wikidata（CC0）當條件欄位的基底，加上人工對照台灣代理商官方商品頁補齊與校正繁中名稱和條件欄位。難度、最佳人數等偏好欄位由我們自己定義（人工標註，或交給 ticket 09 的心得管線）。BGG 只做外連：Wikidata 已收 BGG ID（`P2339`），可以直接組出 BGG 頁面網址，不呼叫 BGG API，也不儲存 BGG 資料。
4. **另一條路：** 用非商業用途向 BGG 申請 application，申請時寫清楚「LLM 推薦 Agent，回答附 BGG 連結」。取得 BGG 書面同意後，再加入 BGG 的難度（`averageweight`）、建議／最佳人數、類別與機制。

## 1. BoardGameGeek XML API2（含 `bg_ranks` CSV）

### 1.1 取得方式

| 項目 | 內容 | 等級 | 來源 |
|---|---|---|---|
| 要不要註冊 | 要。不帶 token 呼叫 `https://boardgamegeek.com/xmlapi2/thing?id=13` 會回 HTTP 401，內容為 `Unauthorized. See https://boardgamegeek.com/using_the_xml_api`。BGG 官方論壇也公告除少數例外，使用 XML API 都要先註冊 | 401 實測為已確認；公告為間接 | [B6][B13] |
| 註冊流程 | 在 `boardgamegeek.com/applications` 登記 application，選商業或非商業。官方寫審核「may be a week or more」。核准後在同一頁建立 token | 間接 | [B1] |
| 驗證方式 | 請求標頭 `Authorization: Bearer <token>`。網域不加 `www`，`Bearer` 後面接空格、不加冒號 | 間接 | [B1] |
| 例外 | 只有「登入後下載自己的收藏」不需要註冊 | 間接 | [B1] |
| 速率限制 | 官方說「still determining exact usage limits」，用量可在 applications 頁查看；沒有公布數字 | 間接 | [B1] |
| 節流行為 | 舊版 wiki 寫請求太頻繁會回 500 或 503；搬到雲端後，使用者回報會回 429，而且不帶 `Retry-After` | 間接 | [B8][B12] |
| 每次請求上限 | `thing` 每次最多 20 個 ID | 間接 | [B7] |
| 搜尋能力 | `search` 只能用名稱查詢，沒有依人數、難度或排名篩選整個目錄的端點，所以要篩選條件就得先匯入自己的資料庫 | 二手 | [X2] |
| 批次下載 | `bg_ranks` CSV 含所有已排名桌遊的 ID、名稱、排名與平均評分。授權上「視為 XML API 的一部分」，套用同一份條款 | 間接 | [B8] |
| `bg_ranks` 需不需要登入 | 第三方整理說「開放給已核准的 application」 | 未確認（二手 [X2]） | |

### 1.2 使用條款

| 問題 | 答案 | 等級 | 來源 |
|---|---|---|---|
| 授權範圍 | 全球、非專屬、免權利金，授權重製與展示 XML API 提供的資料（含使用者上傳內容），**限嚴格的非商業用途** | 間接 | [B2][B11] |
| 要不要標示來源 | 要。所有用途都要寫出 BoardGameGeek 是資料來源；公開的應用程式要放「Powered by BGG」logo、連回 BGG，尺寸要讓文字清楚可讀 | 間接 | [B1][B2] |
| AI／LLM | 網站條款：不得把網站資料拿去訓練 AI／LLM，或以其他方式當成 AI／LLM 系統的資料 [B4]。XML API 條款：嚴格禁止用 XML API 或網站資料訓練 AI／LLM [B2]。BGG 開發者說明現行條款（網站條款 6.B.iv，XML API 條款有納入）不允許把 BGG 資料當 LLM 輸入，即時查詢也算 [B5] | 條款為間接；開發者發言為已確認 | [B2][B4][B5] |
| 商業用途 | 需要另外申請商業授權。官方舉的例子包括：把 API 資料放在桌遊店的頁面上；支援其他商業活動，例如桌遊展，**即使是非營利**也算 | 間接 | [B3] |
| 非商業授權費用 | 「generally provided at no cost」，並註明之後可能改變 | 間接 | [B3] |
| 能不能存進自己的資料庫 | 條款原文未能確認。第三方整理寫「server-side requests with caching」，也就是允許在伺服器端快取，但未寫最長能存多久；同一份整理還列出「不得修改資料」「不得把 BGG 資料轉給其他應用程式」 | 未確認（二手 [X2]） | |
| 能不能用在公開 Demo | 非商業、標示來源、放 logo 的條件下可以展示。但我們是 LLM Agent，會撞到上面的 AI／LLM 條款。平台另有「桌遊店訂位」功能，依 [B3] 的例子，若有真實店家使用，可能被 BGG 認定為商業用途 | 間接 | [B2][B3][B5] |
| 能不能放進公開 repo | 不放。授權只寫「重製與展示」，有沒有允許以資料集形式再散布，未能確認；團隊規則也規定抓取的資料不進 repo（`map.md` 固定偏好） | 未確認 | [B2] |
| 圖片 | 圖片是使用者上傳，預設授權為「All Rights Reserved」；上傳者要自己擁有版權或取得授權 [B11]。能不能直接引用 `cf.geekdo-images` 的圖片網址，查不到明文 | 間接；引用網址為未確認 | [B4][B11] |

### 1.3 可取得的欄位

`thing?id=...&stats=1` 的回應結構。BGG 文件頁打不開，下表依第三方開發者 2026-10-01 用核准 token 實測後的整理 [X2]，加上 API2 文件頁的索引片段 [B7]。我們沒有 token，無法自己實測，因此整張表標為二手。

| 欄位 | BGG 元素 | 用途 |
|---|---|---|
| 人數 | `minplayers`、`maxplayers` | 條件 |
| 建議／最佳人數 | 投票 `poll name="suggested_numplayers"`（每個人數的 Best／Recommended／Not Recommended 票數），以及 `poll-summary` 的 `bestwith`、`recommmendedwith`（BGG 拼字就是三個 m） | 條件、偏好 |
| 遊戲時長 | `playingtime`、`minplaytime`、`maxplaytime` | 條件 |
| 年齡 | `minage`，以及投票 `suggested_playerage` | 條件 |
| 難度 | `statistics` 裡的 `averageweight`（1 到 5）、`numweights` | 偏好 |
| 類別、機制 | `link type="boardgamecategory"`、`link type="boardgamemechanic"`，另有 family、designer、expansion | 偏好 |
| 語言依賴度 | 投票 `language_dependence` | 可用來判斷「看不懂英文能不能玩」 |
| 說明文字 | `description`（英文） | |
| 圖片 | `image`、`thumbnail`（版權見 1.2） | |
| 排名與評分 | `ranks`、`average`、`bayesaverage`、`usersrated` | |
| 名稱 | `name type="primary"`、`name type="alternate"` | 繁中名稱見 1.4 |

### 1.4 BGG 別名能不能當繁中名稱來源

**不可靠，不建議自動採用。**

- `name` 元素沒有語言屬性。有人在 BGG 論壇要求加上語言代碼，得到的回覆是名稱本來就沒有連到語言，所以 API 給不出這項資訊；有些別名甚至沒有對應任何版本 [B9]（間接）。
- 版本（`boardgameversion`）的語言欄位只有「Chinese」，不分繁簡。繁中版只能從自由填寫的版本暱稱看出來，例如「Traditional Chinese edition」[B10]（間接）。
- 因此要從別名挑出台灣繁中名稱，只能靠字形判斷，例如用 OpenCC 轉換比對。但繁簡字形相同的名稱分不出來，港版與台版譯名也可能不同，日文漢字名稱也可能被誤判。
- 我們沒有 token，**別名對熱門桌遊的繁中覆蓋率無法實測**（未確認）。
- 就算覆蓋率夠，別名仍是 BGG 資料，同樣受 1.2 的 AI／LLM 條款限制。

## 2. Wikidata（含中文維基百科、Wikimedia Commons）

### 2.1 取得方式

| 項目 | 內容 | 等級 | 來源 |
|---|---|---|---|
| 方式 | SPARQL 端點 `https://query.wikidata.org/sparql`，或 Action API `wbgetentities`。不需要註冊或 token（本次實測不帶任何憑證即可查詢） | 已確認 | [W2][W5] |
| 速率限制 | 每個查詢最多跑 60 秒；每個用戶端（User-Agent 加 IP）每 60 秒最多用 60 秒的處理時間；每分鐘最多 30 個出錯的查詢；同一個 IP 最多 5 個查詢同時進行。超過限制回 429，依 `Retry-After` 等待；持續無視可能被暫時封鎖。限制可能隨用量調整 | 已確認 | [W2] |
| User-Agent | 必須送出可辨識的 User-Agent，含聯絡方式，格式如 `名稱/版本 (聯絡方式) 函式庫/版本`。不可冒用瀏覽器的 User-Agent，否則可能被封鎖 | 已確認 | [W2][W3] |

### 2.2 使用條款

| 問題 | 答案 | 等級 | 來源 |
|---|---|---|---|
| 結構化資料授權 | main、Property、Lexeme、EntitySchema 命名空間的資料以 CC0 釋出到公有領域 | 已確認 | [W1] |
| 存進自己的資料庫、公開 Demo、交給 LLM | CC0 沒有限制，都可以 | 已確認 | [W1] |
| 要不要標示來源 | CC0 不要求標示。仍建議在頁尾寫「部分資料來源：Wikidata」 | 已確認 | [W1] |
| 能不能放進公開 repo | 授權上可以。但團隊規則規定抓取的資料不進 repo（`map.md` 固定偏好），所以只提交匯入指令稿，測試資料自己編寫 | 已確認 | [W1] |
| 中文維基百科文字 | CC BY-SA 4.0。重用時要以超連結標示原條目、註明授權，修改過的內容也要用相同授權釋出 | 已確認 | [W6] |
| 圖片（`P18` 指向 Commons） | Commons 只收自由授權的檔案，授權寫在各檔案的說明頁。重用時要依各檔案的授權標示作者與授權 | 已確認 | [W6][W7] |

### 2.3 欄位與覆蓋率（2026-11-06 實測）

對「有 BGG ID（`P2339`）的 Wikidata 項目」跑一次彙總查詢 [W5]，只取數量，不下載資料：

| 欄位 | Wikidata 屬性 | 有值的項目數（共 4,757） | 用途 |
|---|---|---|---|
| BGG ID | `P2339` | 4,757 | 外連 BGG、和其他來源對照 |
| 最少人數 | `P1872`（另有最多人數 `P1873`） | 2,246 | 條件 |
| 時長 | `P2047` duration | 813 | 條件 |
| 最低年齡 | `P2899` | 1,018 | 條件 |
| 類型 | `P136` genre | 720 | 偏好（主題） |
| 機制 | `P4151` game mechanics | 217 | 偏好 |
| 難度 | `P7252` degree of difficulty | 1 | 實際上沒有 |
| 建議／最佳人數 | 沒有對應屬性 | 0 | |
| 圖片 | `P18` | 668 | |
| 中文標籤 `zh` | 標籤 | 464 | |
| 繁中標籤 `zh-hant` | 標籤 | 125 | |
| 台灣標籤 `zh-tw` | 標籤 | 29 | |
| 中文維基百科條目 | sitelink | 366 | 說明文字（CC BY-SA） |

再抽 12 款熱門桌遊檢查（BGG ID：13、822、9209、30549、148228、230802、68448、39856、178900、266192、162886、167791）[W5]：

- 人數 12/12 款都有，時長 8/12，年齡 9/12，機制 4/12，圖片 12/12（多半是 Commons 上的實際遊玩照片，不是盒繪）。
- 中文標籤 7/12，`zh-hant` 1/12，`zh-tw` 0/12。中文標籤繁簡混用，例如 `车票之旅`、`卡坦岛` 是簡體，`璀璨寶石`、`卡卡頌` 是繁體。
- 有多值問題。例如 9209 的時長同時有 30 與 60；266192 的最多人數同時有 2、5、7。匯入時要訂規則，例如取最小值與最大值當範圍，或只取沒有限定詞的值。

### 2.4 繁中名稱

- `zh-tw`、`zh-hant` 標籤太少，不能當主要來源。
- 中文維基百科有字詞轉換，但只轉換字形，不會換成台灣代理版的譯名。實測 `车票之旅` 用 `zh-tw` 顯示為 `車票之旅`，`妙不可言 (遊戲)` 維持原樣 [W8]。
- 對照例子：Ark Nova（BGG 342942）在 Wikidata 的中文標籤是 `方舟动物园` [W5]，台灣零售商標示的繁中品名是 `方舟動物園` [T3]。Brass: Birmingham（224517）與 Pandemic Legacy: Season 1（161936）在 Wikidata 沒有任何中文標籤 [W5]。

## 3. 台灣代理商官方商品頁（例：新天鵝堡、2Plus 灣加遊戲）

| 項目 | 內容 | 等級 | 來源 |
|---|---|---|---|
| 取得方式 | 網站商品頁，沒有 API。新天鵝堡另有 Google Drive 上的 PDF 型錄。沒有可下載的資料檔 | 已確認 | [T1][T2] |
| 條款 | 新天鵝堡頁尾與商品圖片標示「© Swan Panasia Co., Ltd. All Rights Reserved.」；2Plus 頁尾標示「2017 © Copyright 2 Plus All Rights Reserved.」。兩站都沒有找到另外的使用條款頁 | 已確認 | [T1][T2] |
| 欄位（以新天鵝堡《神獸天團 13 Animals》為例） | 繁中名稱、原文名稱、人數（2-5人）、時間（30分鐘）、年齡（8歲以上）、作者、插畫、說明文字、圖片、價格。**沒有 BGG ID、難度、機制** | 已確認 | [T1] |
| 能不能存、能不能 Demo、要不要標示 | 名稱、人數、時間、年齡這類事實資料，一般認為本身不受著作權保護（Wikidata 的授權說明也這樣看 [W1]）。所以人工逐款查核、自己輸入這些欄位，風險低。**說明文字與圖片不可複製**。這是一般看法，不是法律意見 | 事實欄位：未確認（推論）；文字與圖片：已確認 | [T1][T2][W1] |
| 能不能放進公開 repo | 不放 | | |

這是繁中名稱最有公信力的來源：盒子上印的就是這個名稱。缺點是每家代理商的網站格式不同，只能人工查。

## 4. 看過但不建議的來源

| 來源 | 狀況 | 等級 | 來源 |
|---|---|---|---|
| Board Game Atlas API | 2026-11-06 時 `www.boardgameatlas.com` 已無法解析網域，服務不可用 | 已確認 | [X1] |
| 卡牌屋 BGHut 的 BGG 排行對照頁 | 台灣零售商把 BGG 前 100 名對照店內的繁中品名與庫存（快照日 2026/09/06），附 BGG 連結。沒有 API、沒有條款頁，也不是代理商。適合人工查譯名時當線索，再回代理商頁確認 | 已確認 | [T3] |
| 簡體中文整理站（例：桌遊庫 zhuoyouku.com） | 簡體中文，內容整理自 BGG，屬二手資料。本次沒有打開查看 | 未確認 | |
| Kaggle、GitHub 上的 BGG 資料集 | 資料來自 BGG，依 [B8]「CSV 視為 XML API 一部分」的邏輯，推論仍受 BGG 條款約束，包括 AI／LLM 條款 | 未確認（推論） | [B8] |
| BGG 網站的非公開 JSON 端點（geekdo） | 第三方整理指出不在 XML API 授權範圍內 | 二手 | [X2] |

## 5. 欄位對照總表

| 欄位 | 用途 | BGG XML API2 | Wikidata | 台灣代理商頁 |
|---|---|---|---|---|
| 人數（最少／最多） | 條件 | 有 | 有（約 47%，熱門款 12/12） | 有 |
| 建議／最佳人數 | 條件、偏好 | 有（投票） | 無 | 無 |
| 遊戲時長 | 條件 | 有 | 部分（約 17%，熱門款 8/12） | 有 |
| 年齡 | 條件 | 有 | 部分（約 21%，熱門款 9/12） | 有 |
| 難度 | 偏好 | 有（`averageweight`） | 無 | 無 |
| 類別／主題 | 偏好 | 有 | 部分（約 15%） | 無（網站有標籤分類，未逐款確認） |
| 機制 | 偏好 | 有 | 很少（約 5%） | 無 |
| 說明文字 | | 英文 | 中文維基約 366 款（CC BY-SA） | 有，但版權全部保留 |
| 圖片 | | 有，使用者上傳，預設全部保留 | 約 14%，Commons 自由授權 | 有，版權全部保留 |
| 繁中名稱 | | 別名混雜，無語言標記 | `zh-tw` 29 款、`zh-hant` 125 款 | 有，最可靠 |
| 授權 | | 非商業、要標示、限制 LLM | CC0 | 全部保留 |
| 存取 | | 要 token，審核制 | 免註冊 | 人工 |

## 6. 建議

**採用：Wikidata 加上人工查核，BGG 只做外連。**

1. **收錄名單**：由 ticket 06 決定。名單內每款桌遊用 Wikidata 的 `P2339` 對上 BGG ID，作為內部對照鍵。BGG ID 是 Wikidata 的 CC0 資料，不必呼叫 BGG API。
2. **條件欄位**（人數、時長、年齡）：先從 Wikidata 匯入，再對照台灣代理商商品頁（盒子上的標示）逐款補齊與校正。多值欄位依 2.3 的規則處理。
3. **繁中名稱**：以台灣代理商商品頁為準，人工輸入。找不到代理版的桌遊，依序退回 `zh-tw`、`zh-hant` 標籤，再退回原文名稱。實際規則在 ticket 06 定案。
4. **偏好欄位**（主題、機制、難度）：開放資料裡沒有可用的難度，機制的覆蓋率也太低。改由我們自己定義詞彙（ticket 08），用人工標註或心得管線（ticket 09）產生。
5. **說明文字**：自己寫繁中簡介，或先讓 LLM 依 CC0 事實欄位起草、再由人工審稿。不複製代理商的文字。不建議用中文維基百科文字（CC BY-SA 會連帶要求衍生內容使用相同授權，覆蓋率也只有 366 款）。
6. **圖片**：先不放封面圖。要放的話只用 Wikidata `P18` 指向的 Commons 圖片，並依各檔授權標示作者。
7. **BGG 外連**：推薦結果附上 `https://boardgamegeek.com/boardgame/{bgg_id}` 連結，讓玩家自己查看 BGG 的難度與最佳人數。只放連結，不在我們的系統裡使用 BGG 資料。
8. **進 repo 的東西**：只有匯入指令稿，以及自己編寫的少量測試假資料（AGENTS.md §2 規則 2）。匯入結果只存在 PostgreSQL。

**同時進行（由組員決定要不要做）：** 以非商業用途向 BGG 申請 application，在申請說明中寫清楚三件事：LLM 推薦 Agent、每則回答都附 BGG 連結、平台的桌遊店訂位只是學生 Demo。取得書面同意後，再把 `averageweight`、`suggested_numplayers` 和類別、機制加進來，並依 1.2 放上「Powered by BGG」logo、標示來源。沒有書面同意前，不要把 BGG 的任何資料存進資料庫或交給 LLM。

## 7. 對後續 ticket 的影響

- **06 收錄哪些桌遊、存哪些欄位**：沒有 BGG API，就不能用「BGG 前 N 名」自動產生名單，名單要人工挑。條件欄位要逐款查核，收錄數量要配合人力。每款桌遊要另外記錄每個欄位的資料來源（Wikidata、代理商、人工）。
- **08 標籤詞彙、09 心得轉標籤**：難度與最佳人數沒有開放來源，要由這兩張 ticket 補上。
- **11 推薦理由**：如果之後取得 BGG 同意，條件很可能是「回答要附 BGG 連結」[B5]，推薦理由的格式要預留連結位置。

## 8. 未確認事項

1. **BGG 條款原文**：`using_the_xml_api`、`wiki/page/XML_API_Terms_of_Use`、`terms`（6.B.iv）這三頁對自動存取一律回 403，本次只能間接確認。資料庫儲存與快取期限、再散布、修改資料、轉給其他應用程式（例如把資料送進雲端 LLM API 算不算）、圖片網址引用，都需要組員用瀏覽器打開原文核對。
2. **BGG 會不會同意 LLM Agent 使用**：BGG 說條款「in flux」，可能改成附連結就允許 [B5]，但目前沒有正式條文。
3. **我們算不算商業用途**：平台服務桌遊店，依 [B3] 的例子可能被認定為商業用途，要在申請時問 BGG。
4. **BGG 別名的繁中覆蓋率**：沒有 token，無法實測。
5. **`bg_ranks` CSV**：需不需要登入、有哪些欄位，只有二手資訊。
6. **BGG 的實際速率限制**：官方沒有公布數字。
7. **Wikidata 對我們名單的覆蓋率**：本檔只量了 4,757 款的整體數字與 12 款樣本，名單定案後要再量一次。
8. **代理商頁事實欄位的法律定性**：「事實不受著作權保護」是一般看法，不是法律意見；大量、系統化複製整份目錄仍有爭議空間。

## 附錄：本次使用的彙總查詢

只回傳數量，不下載個別資料。送出時帶自訂 User-Agent，符合 [W3]。

```sparql
SELECT (COUNT(DISTINCT ?item) AS ?withBggId)
       (COUNT(DISTINCT ?zhtw) AS ?zhTwLabel)
       (COUNT(DISTINCT ?minp) AS ?minPlayers)
WHERE {
  ?item wdt:P2339 ?bgg .
  OPTIONAL { ?item rdfs:label ?l FILTER(LANG(?l) = "zh-tw") BIND(?item AS ?zhtw) }
  OPTIONAL { ?item wdt:P1872 ?x BIND(?item AS ?minp) }
}
```

其他欄位（`P2047`、`P2899`、`P136`、`P4151`、`P7252`、`P18`、`zh`、`zh-hant`、中文維基 sitelink）用同樣寫法計數。

## 來源清單

存取日一律為 2026-11-06。

| 代號 | 來源 | URL | 取得方式 | 等級 |
|---|---|---|---|---|
| B1 | BGG：Using the XML API | https://boardgamegeek.com/using_the_xml_api | 搜尋引擎索引（直接存取回 403） | 間接 |
| B2 | BGG：XML API Terms of Use | https://boardgamegeek.com/wiki/page/XML_API_Terms_of_Use | 搜尋引擎索引 | 間接 |
| B3 | BGG：BGG XML API Commercial Use | https://boardgamegeek.com/wiki/page/BGG_XML_API_Commercial_Use | 搜尋引擎索引 | 間接 |
| B4 | BGG：Terms of Service | https://boardgamegeek.com/terms | 搜尋引擎索引 | 間接 |
| B5 | BGG 主要開發者 Daniel Karp（GitHub `karptonite`，個人檔案寫「Primary developer at BoardGameGeek」）於 2026-10-13 的 issue | https://github.com/kkjdaniel/bgg-mcp/issues/12 | GitHub API 直接讀取 | 已確認 |
| B6 | BGG XML API2 實測（不帶 token） | https://boardgamegeek.com/xmlapi2/thing?id=13 | curl，回 HTTP 401 | 已確認 |
| B7 | BGG：BGG XML API2 文件 | https://boardgamegeek.com/wiki/page/BGG_XML_API2 | 搜尋引擎索引 | 間接 |
| B8 | BGG：BGG XML API（舊版文件，含 `bg_ranks` 說明） | https://boardgamegeek.com/wiki/page/BGG_XML_API | 搜尋引擎索引 | 間接 |
| B9 | BGG 論壇：XML API 2 名稱與語言 | https://boardgamegeek.com/thread/3087426/bgg-xml-api-2-boardgame-version-providing-the-game | 搜尋引擎索引 | 間接 |
| B10 | BGG 版本頁（例） | https://boardgamegeek.com/boardgameversion/107613 | 搜尋引擎索引 | 間接 |
| B11 | BGG：Licenses、Image Guidelines | https://boardgamegeek.com/licenses 、 https://boardgamegeek.com/wiki/page/Image_Guidelines | 搜尋引擎索引 | 間接 |
| B12 | BGG 論壇：搬到雲端後回 429 | https://boardgamegeek.com/thread/2065587/wbggs-move-to-cloud-xmlapi-may-now-return-status-4 | 搜尋引擎索引 | 間接 |
| B13 | BGG 論壇：XML API 開始要求註冊的公告 | https://boardgamegeek.com/thread/3539581/xml-api-read-this-for-uninterrupted-access | 搜尋引擎索引 | 間接 |
| W1 | Wikidata:Licensing | https://www.wikidata.org/wiki/Wikidata:Licensing | 直接讀取原始 wikitext | 已確認 |
| W2 | Wikidata Query Service User Manual：Query limits | https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual#Query_limits | 直接讀取 | 已確認 |
| W3 | Wikimedia Foundation User-Agent Policy | https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy | 直接讀取 | 已確認 |
| W4 | Wikidata 屬性 P2339、P1872、P1873、P2047、P2899、P4151、P136、P7252、P18 | https://www.wikidata.org/wiki/Property:P2339 （其餘同格式） | Action API 直接讀取 | 已確認 |
| W5 | Wikidata SPARQL 彙總查詢與 12 款抽樣 | https://query.wikidata.org/sparql | 自行查詢 | 已確認 |
| W6 | Wikimedia Foundation Terms of Use §7 | https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use | 直接讀取 | 已確認 |
| W7 | Commons:Licensing | https://commons.wikimedia.org/wiki/Commons:Licensing | 直接讀取 | 已確認 |
| W8 | 中文維基百科字詞轉換（`variant=zh-tw`） | https://zh.wikipedia.org/w/api.php | 自行查詢 | 已確認 |
| T1 | 新天鵝堡：桌遊目錄與商品頁 | https://www.swanpanasia.com/catalog/all-product 、 https://www.swanpanasia.com/products/13-animals | 直接讀取 | 已確認 |
| T2 | 2Plus 灣加遊戲首頁 | https://www.2plus.com.tw/ | 直接讀取 | 已確認 |
| T3 | 卡牌屋：BGG 排行與台灣在售對照 | https://bghut.com/bgg_top.php | 直接讀取 | 已確認 |
| X1 | Board Game Atlas | https://www.boardgameatlas.com/ | curl，網域無法解析 | 已確認 |
| X2 | 第三方開發者以核准 token 實測後的整理（2026-10-01） | https://github.com/JacobStephens2/keeplore/issues/88 | GitHub API 直接讀取 | 二手 |
