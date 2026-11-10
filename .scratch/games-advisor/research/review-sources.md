# 英文與繁中心得從哪裡取得：來源比較

> **更正（2026-11-06）**：本文關於 BGG「不得把資料用在 AI／LLM」的結論已過時。立倫用瀏覽器核對現行網站條款 6.B.iv，標題為「General-purpose AI use is permitted」：允許把網站內容交給 AI 系統（含 LLM）做摘要、翻譯、搜尋、回答問題等一般用途，只禁止大型 AI 公司拿來訓練或微調模型。本文讀到的是 2026-10-18 存檔的舊版。現況見 [核對 BGG 使用條款原文](../issues/15-verify-bgg-terms.md)。

- Ticket：[03 英文與繁中心得從哪裡取得](../issues/03-review-sources.md)
- 調查日：2026-11-06。沒有另外註明的來源，存取日都是這一天。內文用 `[B1]`、`[P1]` 這類代號引用，完整網址在文末來源清單。
- 用途前提：離線批次收集心得 → 存一份原文（不進 repo）→ 送 Azure OpenAI 分析 → 每款桌遊產生標籤。學生專題、非商業、公開 Demo。
- 本檔不含任何心得原文，也沒有貼文標題，只有來源、條款摘錄與統計數字。

## 證據等級

| 標記 | 意思 |
|---|---|
| 已確認 | 直接讀到官方原文，或自己實測 |
| 存檔 | 官方頁面擋非瀏覽器用戶端（Cloudflare 403），改讀 Internet Archive 的存檔。存檔日期寫在來源清單，原文是官方頁面，但不一定是今天的版本 |
| 二手 | 第三方整理，只當佐證 |
| 未確認 | 查不到，或無法實測 |

## 結論

1. **沒有任何候選來源，在預設條款下同時允許「保存原文」和「交給 LLM 產生標籤」。** 差別只在限制多嚴格。
2. **英文：BGG 與 Reddit 目前都不能用。**
   - BGG 網站條款 6.B.iv 寫明不得把網站資料拿去訓練 AI／LLM，「or otherwise use as data for an AI … or LLM system」[B3]。BGG 主要開發者在 2026-10-13 公開說明，現行條款下把 BGG 資料當 AI／LLM 的輸入也不允許，即時查詢也算 [B7]（已確認）。
   - Reddit 從 2025 年底起，用 API 取得任何資料都要先申請、取得明確核准 [R5]。robots.txt 對所有爬蟲 `Disallow: /` [R1]。Data API 授權只涵蓋「為了在 App 裡顯示給使用者而複製與顯示」，也不得修改內容 [R3]。
3. **繁中：PTT BoardGame 板是唯一沒有明文禁止的平台，但屬於灰色地帶。**
   - PTT 使用者條款沒有規範第三方收集或 AI [P2]。robots.txt 對一般爬蟲 `Allow: /`，但宣告 `ai-train=no`、`use=reference`，`ai-input` 沒有表態 [P1]。依 Cloudflare 定義，`reference` 是「Index, excerpt, and link back」，比「Summarize and reproduce」（`full`）保守 [P4]。用 LLM 把心得彙整成標籤，算不算超出 `reference`，查不到官方解釋。
   - 巴哈姆特 [H2]、Dcard [D2]、方格子 [V2] 的條款都明文禁止未經同意，以程式重製、傳輸或收集其他使用者的內容。
4. **建議：**
   - **主要來源：取得作者書面同意的繁中部落格心得。** 條款最乾淨、品質高，但數量少。
   - **次要來源：PTT BoardGame 板的 `[心得]` 文。** 要先由組內決定是否接受上面的灰色地帶，並採用第 7 節的防護措施。
   - **英文：先向 BGG 申請非商業 application，並以書面詢問能否用於 LLM 產生標籤。** 回覆前不使用 BGG 心得。Reddit 不建議投入。
   - **後備：自己寫心得。** 由組員或合作店家人員替示範桌遊寫心得，或之後在平台內收集玩家同意授權的心得。這是唯一完全沒有授權問題的路，示範規模（8 大類各一款）也寫得完。

## 1. 總覽

| 來源 | 語言 | 取得方式 | 自動收集 | 保存原文 | 交給 LLM 產生標籤 | 熱門桌遊心得量 | 建議 |
|---|---|---|---|---|---|---|---|
| BGG 評分留言與 Reviews 論壇 | 英 | XML API2，要註冊並取得 token | API 可以，網頁不行 | API 授權內可以（非商業、不得修改） | **不行**（條款 6.B.iv） | 留言數千到兩萬多則 | 先申請、取得書面同意再說 |
| Reddit r/boardgames | 英 | Data API，要先申請核准 | **不行**（robots 全擋，未經同意禁止爬取） | 只限核准用途 | **不行**（授權只涵蓋顯示） | 未實測 | 不建議 |
| Shut Up & Sit Down（補充） | 英 | 只有網頁 | robots 允許 | **不行** | **不行** | 未實測，評論者是專業媒體，不是玩家 | 不建議 |
| PTT BoardGame 板 | 繁中 | 只有網頁，免登入 | robots 允許一般爬蟲，但擋 AI 代理 | 條款沒寫；訊號為 `use=reference` | **灰色**（`ai-input` 未表態） | 未實測，待組員用瀏覽器人工複查 | 組內同意後當次要來源 |
| 巴哈姆特 桌上遊戲板 | 繁中 | 只有網頁，免登入 | robots 允許 | **不行**（需書面授權） | **不行** | 每款 0–29 串 | 不建議 |
| Dcard（補充） | 繁中 | 網頁，Cloudflare 擋程式 | **不行**（條款禁止自動化收集） | — | — | 未實測 | 不建議 |
| 台灣桌遊部落格（例：方格子作者） | 繁中 | 網頁，方格子另提供 `.md` 與 RSS | 平台技術上歡迎 agent | 要作者同意 | 要作者同意 | 單一作者數十篇，一款遊戲通常一篇 | **取得作者同意後當主要來源** |

## 2. BoardGameGeek（英文）

### 2.1 取得方式

| 項目 | 內容 | 等級 | 來源 |
|---|---|---|---|
| 評分留言 | `GET /xmlapi2/thing?id=<id>&comments=1`（所有留言）或 `&ratingcomments=1`（所有評分，有留言就附上）。`page` 分頁，`pagesize` 介於 10 與 100 | 存檔 | [B5] |
| Reviews 論壇 | `/xmlapi2/forumlist?id=<id>&type=thing` 取得該遊戲的論壇清單（含 Reviews），`/xmlapi2/forum?id=<forum_id>` 每頁 50 串，`/xmlapi2/thread?id=<thread_id>` 取得內文 | 存檔 | [B5] |
| 要不要註冊 | 要。不帶 token 呼叫 `thing` 回 HTTP 401。官方說明除了「登入後下載自己的收藏」等少數例外，都要先在 `boardgamegeek.com/applications` 註冊 application，審核「may be a week or more」 | 401 為已確認；說明為存檔 | [B6][B1] |
| 驗證 | `Authorization: Bearer <token>`，網域不加 `www` | 存檔 | [B1] |
| 速率 | 官方說「still determining exact usage limits」，建議由伺服器端呼叫並快取結果。API2 文件寫請求太頻繁會回 500／503，「a 5-second wait between requests seems to suffice」 | 存檔 | [B1][B5] |
| 網頁 | 一般網頁、robots.txt、條款頁對 curl 與 WebFetch 都回 Cloudflare challenge 或 403；headless 瀏覽器也一樣 | 已確認 | — |
| 帳號年齡 | BGG 條款開頭寫未滿 18 歲不能註冊帳號 | 存檔 | [B3] |

### 2.2 條款與 robots.txt

| 問題 | 答案 | 等級 | 來源 |
|---|---|---|---|
| 能不能自動收集 | 透過 XML API 可以，但要遵守 API 條款。網站條款 6.B.i 禁止以超過人類瀏覽速度的機器人存取網站；6.B.ii 禁止收集帳號名稱等個資。robots.txt 對 `*` 設 `Crawl-delay: 5`，並 `Disallow: /xmlapi`（前綴比對也涵蓋 `/xmlapi2`）、`/forum/search`；GPTBot、ClaudeBot、CCBot 等 AI 爬蟲整站禁止 | 存檔 | [B3][B4] |
| 能不能保存原文 | XML API 授權「to reproduce and display the data … including User Submissions, solely for strictly non-commercial purposes」，而且「You may not modify the data, including User Submissions」。所有使用都要標示 BoardGameGeek，公開使用要放「Powered by BGG」logo。官方也建議快取結果，所以在非商業範圍內保存應該可以 | 存檔 | [B2][B1] |
| 能不能交給 LLM | **不行。** API 條款：「Use of the XML API--or any of the data on the site--to train an AI … or … LLM system is strictly prohibited」[B2]。網站條款 6.B.iv：「You agree not to use the Geek Websites to train or otherwise use as data for an AI … or … LLM system」[B3]。BGG 主要開發者 Daniel Karp 在 2026-10-13 說明，依現行條款，把 BGG 資料當 AI／LLM 的輸入不被允許（6.B.iv，API 條款有納入），即時查詢也算；條款「in flux」，可能改成「回答附 BGG 連結就允許」[B7] | 條款為存檔；開發者發言為已確認 | [B2][B3][B7] |
| 其他 | 網站另有私有 API（例如 `api.geekdo.com`），官方說「we are granting no license for use of those endpoints」 | 存檔 | [B1] |

### 2.3 數量與品質

5 款熱門桌遊的 BGG 遊戲頁存檔中，`numcomments`（留言數）與 `usersrated`（評分人數）：

| 桌遊 | BGG ID | 留言數 | 評分人數 | 存檔日 |
|---|---|---|---|---|
| Catan（卡坦島） | 13 | 24,246 | 144,916 | 2026-10-18 |
| Azul（花磚物語） | 230802 | 13,772 | 111,182 | 2026-10-03 |
| Splendor（璀璨寶石） | 148228 | 12,875 | 91,608 | 2026-09-20 |
| Ark Nova（方舟動物園） | 342942 | 8,431 | 63,752 | 2026-10-27 |
| The Resistance: Avalon（阿瓦隆） | 128882 | 5,450 | 37,088 | 2026-10-02 |

- Reviews 論壇：只找到 Catan 在 2023-06-09 的存檔，Reviews 論壇有 186 串、1,540 則貼文 [B9]。這是三年前的數字，而且是私有 API 的存檔，只當量級參考。
- Wingspan、Terraforming Mars、Codenames 沒有近期存檔，未取得數字。
- 品質：沒有 token，讀不到留言內文，留言長度與內容是否足以判斷特性**未實測**。`numcomments` 是否等於 `comments=1` 回傳的 `totalitems`，**未確認**。
- 量級足夠：熱門桌遊有數千則以上留言，加上 Reviews 論壇的長文，足以判斷特性。卡住的是條款，不是數量。

## 3. Reddit r/boardgames（英文）

### 3.1 取得方式

| 項目 | 內容 | 等級 | 來源 |
|---|---|---|---|
| API | Reddit Data API（OAuth）。Responsible Builder Policy（2026-06-05 更新）寫「You must request access and get explicit approval before accessing any Reddit data through our API」。非商業開發者被導向 Devvit；研究者要申請 Reddit for Researchers（RFR），並寫明「Any research that uses Reddit data collected outside of the RFR Program is in violation of this policy」 | 存檔 | [R5] |
| 速率 | 免費使用為每個 OAuth client id 100 QPM（10 分鐘平均） | 存檔 | [R7] |
| 網頁 | robots.txt 為 `User-agent: *`、`Disallow: /`，註解指向 Public Content Policy | 已確認 | [R1] |

### 3.2 條款

| 問題 | 答案 | 等級 | 來源 |
|---|---|---|---|
| 能不能自動收集 | **不行，除非取得核准。** User Agreement（2026-07-01 生效）：依 robots.txt 有條件允許爬取，「but scraping the Services without Reddit's prior written consent is prohibited」；而 robots.txt 擋全站 | 已確認 | [R2][R1] |
| 能不能保存原文 | 只限核准的用途。Data API Terms（2026-07-20 修訂）§3.2：不得超出核准用途使用或保留資料，用不到的要立即刪除。§6：終止時要刪除快取內容，「This includes any data or models that were derived from User Content」。Public Content Policy 也要求被授權方不得繼續使用已刪除的內容 | 已確認；PCP 為存檔 | [R3][R6] |
| 能不能交給 LLM | **授權沒有涵蓋。** Data API Terms §2.4 只授權「copy and display the User Content using the Data API solely as necessary to … run your App to your App Users」，「You may not modify the User Content except to format it for such display」，其他用途（例如訓練 ML／AI）都沒有授權。Developer Terms（2026-03-24 修訂）禁止未經同意用來訓練 LLM／AI，並要求顯示時附原文連結與作者帳號。Responsible Builder Policy 寫非商業的「mining, scraping, or using data … to train machine learning or AI models」也要書面核准 | 已確認；RBP 為存檔 | [R3][R4][R5] |

只用推論、不訓練（Azure OpenAI 不拿提示訓練模型 [A1]）的分析與標籤產生，條款沒有明文提到。但 §2.4 只授權「顯示」，產生標籤已經超出這個範圍。

### 3.3 數量與品質

**未實測。** robots.txt 擋全站，API 要先核准，所以這次沒有抓取任何 Reddit 資料，也沒有估計每款桌遊的討論數。

## 4. 其他英文候選（補充）

| 來源 | 結果 | 等級 | 來源 |
|---|---|---|---|
| Shut Up & Sit Down | robots.txt 只擋後台與購物車。Terms of Service §2 只允許「temporarily download one copy … for personal, non-commercial transitory viewing only」，不得「modify or copy the materials」。不能保存，也不能交給 LLM。而且內容是專業媒體評論，不是玩家心得 | 已確認 | [S1][S2] |
| Wikipedia（不是心得，列為替代） | 文字採 CC BY-SA 4.0，以連結標示來源即可；條款只禁止「abusive or disruptive」的自動化使用，沒有 AI 條款。熱門桌遊條目常有 Gameplay、Reception 段落，可以當標籤的補充證據；但內容是百科摘要，不是玩家心得。標籤算不算需要 ShareAlike 的改作，**未確認** | 已確認 | [W1] |

## 5. PTT BoardGame 板（繁中）

### 5.1 取得方式

| 項目 | 內容 | 等級 | 來源 |
|---|---|---|---|
| API／RSS | 沒有官方 API，也沒找到官方 RSS。網頁版 `https://www.ptt.cc/bbs/BoardGame/index.html` | API 為已確認；RSS 為未確認 | [P3] |
| 登入 | 不用。BoardGame 板沒有年齡確認頁，直接就能讀 | 已確認 | [P3] |
| 搜尋 | `/bbs/BoardGame/search?q=<關鍵字>`，只比對**標題**，每頁 20 筆 | 已確認 | [P3] |

### 5.2 條款與 robots.txt

| 問題 | 答案 | 等級 | 來源 |
|---|---|---|---|
| 使用者條款 | 使用者條款 2.0.1 §1-2：資料上傳到 PTT（私人信件、水球除外），即同意 PTT「為非營利無償使用、修改、重製…，並得轉授權為非營利使用」。條款只規範使用者與 PTT 之間的授權，**沒有提到第三方收集、爬蟲或 AI**。著作權仍屬作者 | 已確認 | [P2] |
| robots.txt | 由 Cloudflare 代管。`User-agent: *`：`Content-Signal: search=yes,ai-train=no,use=reference`、`Allow: /`。GPTBot、ClaudeBot、CCBot、Google-Extended 等訓練爬蟲，以及 ChatGPT-User、Claude-User、Perplexity-User 等 AI 代理，都是 `Disallow: /`。檔案開頭聲明這些訊號是依歐盟 DSM 指令第 4 條所做的權利保留 | 已確認 | [P1] |
| 訊號定義 | robots.txt 內文：`ai-input` 是「inputting content into one or more AI models (e.g., retrieval augmented generation, grounding…)」，沒列出的訊號「neither grants nor restricts permission」。Cloudflare 文件（2026-11-02 更新）：`use=immediate` 為「Interact, but store and reuse nothing」，`use=reference` 為「Index, excerpt, and link back」，`use=full` 為「Summarize and reproduce」 | 已確認 | [P1][P4] |
| 能不能自動收集 | 以一般爬蟲身分（`*`）可以。但 AI 代理被明確擋下，所以收集程式不該由 AI 助理代跑 | 已確認 | [P1] |
| 能不能保存原文 | 條款沒寫。`use=reference` 允許「index」，可以理解為能保存供索引；但這只是偏好訊號，不是授權 | 灰色 | [P1][P4] |
| 能不能交給 LLM | **灰色。** `ai-train=no` 不影響我們（只做推論，Azure OpenAI 不拿提示訓練模型 [A1]）。`ai-input` 沒表態，等於不允許也不禁止。但產生標籤本質上是彙整心得，比較接近 `full` 的「Summarize」，不在 `reference` 的「Index, excerpt, and link back」範圍內。訊號在台灣的法律效力，**未確認** | 灰色 | [P1][P4][A1] |
| 板規 | 置底有「板規（104.4.23 修訂）」，**這次沒有讀取**，有沒有轉載限制未確認 | 未確認 | [P3] |

### 5.3 數量與品質

**未實測。** 原本的篇數統計是用不符合 PTT robots.txt 的方式取得，已刪除（見下方揭露）。需要數字時，請組員用瀏覽器人工複查。

- 品質：這次沒有讀任何內文，心得長度與內容是否足以判斷特性**未實測**。依板上分類，`[心得]` 通常是長文，搭配推文可以看到不同玩家的意見。

**揭露：** 原本的篇數統計是 Claude（AI 助理）在調查時用 curl 抓的，User-Agent 為 `tabletop-hub-tw-research/0.1`，約 90 次請求，間隔 1.2–1.5 秒，只讀看板列表與搜尋結果頁，沒有讀內文，也沒有存檔。PTT 的 robots.txt 明確擋了 `Claude-User`，這次抓取不符合它的意思，之後不應再由 AI 助理代抓 PTT；如果需要正式數字，請組員用瀏覽器人工複查。這些數字已在 2026-11-06 從本文與 ticket 03 刪除。

## 6. 巴哈姆特 桌上遊戲（BoardGame）綜合討論板（繁中）

### 6.1 取得方式

| 項目 | 內容 | 等級 | 來源 |
|---|---|---|---|
| 板面 | `https://forum.gamer.com.tw/B.php?bsn=60537`，只有網頁，沒找到公開 API | 網頁為已確認；API 為未確認 | [H4] |
| 登入 | 讀文不用登入 | 已確認 | [H4] |
| robots.txt | `User-agent: *` 只擋 `/Bo.php`、`/embed.php`，附 sitemap | 已確認 | [H3] |

### 6.2 條款

| 問題 | 答案 | 等級 | 來源 |
|---|---|---|---|
| 著作權 | 著作權聲明：「使用者於巴哈姆特電玩資訊站所發表之內容，其著作權為原作者所有，未經原作者同意，任何人不得以任何形式轉貼部份或全部之內容」；「本站使用者在非營利用途下，得以下載或列印圖文內容」 | 已確認 | [H1] |
| 能不能保存、交給 LLM | **不行，要書面授權。** 會員規範第 14 條：「非經本公司書面授權同意，不得以任何形式轉載、傳輸、傳播、散布、展示、出版、再製或利用巴哈姆特內容的局部、全部的內容」。保存原文是再製，送 LLM 是傳輸與利用。條款沒有 AI 專條 | 已確認 | [H2] |
| 能不能自動收集 | robots.txt 允許，條款也沒有寫爬蟲；但收集下來之後的保存與利用，都撞到第 14 條 | 已確認 | [H2][H3] |

### 6.3 數量與品質

- 全板 61 頁，每頁約 30 串，約 1,800 串，最舊的在 2010-04。第一頁的最後回覆時間，從 2026-05 到 2026-11 只有約 25 串，活躍度低 [H4]。
- 依標題搜尋：阿瓦隆 29 串（`【心得】` 4 串）、卡坦 12 串（3 串）、璀璨寶石 4 串（1 串）、花磚物語 2 串（1 串）；殖民火星、展翅翱翔、方舟動物園都是 0 串 [H4]。
- 量太少，就算取得授權也不夠判斷大部分桌遊的特性。

## 7. 其他繁中候選

### 7.1 Dcard

| 項目 | 內容 | 等級 | 來源 |
|---|---|---|---|
| 取得方式 | 網頁對 curl 與 WebFetch 都回 Cloudflare 403。robots.txt 只擋 `/emails/activate`。公開 API 未確認 | 已確認（403）；API 未確認 | [D1] |
| 條款 | 用戶行為限制：「您同意不得為下列行為：以自動化登入及操作方式蒐集 Dcard 其他用戶的用戶內容」；未經事前書面同意不得做商業用途 | 存檔（2025-05-12） | [D2] |
| 數量 | 未實測。桌遊板網址 `/f/boardgame` 也未確認 | 未確認 | — |

結論：條款禁止自動化收集，不建議。

### 7.2 台灣桌遊部落格（以方格子 vocus 為例）

| 項目 | 內容 | 等級 | 來源 |
|---|---|---|---|
| 取得方式 | 方格子提供 `llms.txt`，文章可用 `https://vocus.cc/article/<id>.md` 或 `Accept: text/markdown` 取得 markdown；robots.txt 允許 `/article`、`/user`，也允許 `/api/rss/article`（RSS 格式未確認） | 已確認 | [V1] |
| 條款 | 會員服務條款（2025-12-15 更新）第四條（一）：著作權屬作者，「除本網站明示同意授權外，您不得自行或以程式、外掛或其他任何方式，擅自使用、重製、傳輸、散布、發行本網站其他會員之作品或以之從事營利行為」。技術上平台歡迎 agent 讀取，但保存與送 LLM 仍要作者或平台同意 | 已確認 | [V2] |
| 數量 | 以搜尋到的桌遊評測作者「嵐嵐桌遊筆記」為例，個人頁顯示共 36 篇文章 [V3]。部落格通常是一款遊戲寫一篇長評，涵蓋範圍取決於作者玩過哪些遊戲 | 已確認 | [V3] |
| 其他平台 | 痞客邦、Medium、個人網站等沒有逐一查條款。不論哪個平台，著作權都屬作者，最穩的做法是直接取得作者同意 | 未確認 | — |

Facebook 社團要登入，沒有查證條款，這次不列入。

## 8. 建議與防護措施

### 8.1 建議順序

1. **繁中部落格作者的書面同意（主要）。** 挑 2–3 位常寫心得的台灣作者，寫信說明：非商業學生專題、原文只存在私有資料庫不公開、只用 Azure OpenAI 推論不訓練 [A1]、產出只有標籤、推薦時附原文連結、可隨時要求刪除。取得同意後，用方格子的 `.md` 端點或 RSS 讀取最省事。
2. **PTT BoardGame 板 `[心得]` 文（次要，要組內同意）。** 這是繁中唯一沒有明文禁止的平台，但屬於第 5.2 節的灰色地帶。決定要用的話，至少做到：
   - 收集程式由組員執行，User-Agent 寫明專案名稱與聯絡方式，不讓 AI 助理代抓。
   - 每次請求間隔數秒，只抓標題含 `[心得]` 且含目標遊戲名的文章。
   - 原文只存在私有資料庫，設保留期限，不進 repo，不在畫面上顯示原文或摘要。
   - 標籤旁保留來源文章連結（`reference` 的「link back」），作者要求就刪除。
3. **BGG（英文，先申請）。** 以非商業 application 註冊，申請時寫明「LLM 產生標籤，推薦時附 BGG 連結」，取得書面同意後才使用。BGG 開發者說條款可能改成附連結就允許 [B7]，但目前沒有正式條文。
4. **自己寫心得（後備，任何時候都可以用）。** 示範範圍是 8 大類各一款，由組員或合作店家人員替每款寫 2–3 段心得，就能跑通整條管線，也不會有授權問題。之後平台若要收集玩家心得，在服務條款中寫明會用 LLM 分析。

不建議投入：Reddit（要核准，而且授權只涵蓋顯示）、巴哈姆特（要書面授權，量又少）、Dcard（條款禁止自動化收集）、Shut Up & Sit Down（只能個人瀏覽）。

### 8.2 對其他 ticket 的影響

- **09 心得怎麼變成標籤**：每則心得要記錄來源網址、平台、語言、發文日期與取得授權的方式，才能做到連回原文與依要求刪除。Reddit、BGG 這類條款要求刪除原文時，連帶刪除衍生資料。
- **02 桌遊基本資料**：BGG 條款 6.B.iv 也適用於 BGG 的基本資料，不只心得 [B3][B7]。這點在 `game-data-sources.md` 已有結論。
- **11 推薦理由**：如果使用 PTT 或取得 BGG 同意，推薦理由要能附上來源連結。

## 9. 未確認事項

1. **BGG 條款的現行版本**：BGG 網頁擋非瀏覽器用戶端，條款與 robots.txt 讀的是 2026-05 到 2026-10 的存檔。BGG 說 API 條款「in flux」，上線前要有人用瀏覽器打開原頁核對。
2. **BGG 留言的品質與 `numcomments` 的意義**：沒有 token，讀不到留言內文，也無法對照 API 的 `totalitems`。
3. **Reddit 的數量**：完全沒有實測。
4. **PTT 的灰色地帶**：產生標籤算不算超出 `use=reference`、Content Signals 在台灣的法律效力、BoardGame 板規有沒有轉載限制，都沒有確認。
5. **台灣著作權法**：私下保存公開貼文並交給 LLM 分析，能不能主張合理使用（著作權法第 65 條），這次沒有研究，需要請教老師或法律意見。
6. **心得品質**：所有來源都沒有讀內文，只有數量；心得長度與內容是否足以判斷特性，要等取得授權後抽樣檢查。
7. **其他繁中平台**：痞客邦、Facebook 社團、巴哈姆特有沒有公開 API，都沒有查證。

## 來源清單

沒有另外註明的，存取日都是 2026-11-06。「存檔」表示讀的是 Internet Archive 存檔，網址格式為 `https://web.archive.org/web/<存檔時間>/<原網址>`。

| 代號 | 來源 | URL | 取得方式 | 等級 |
|---|---|---|---|---|
| B1 | BGG：Using the XML API（Version date 2025-07-02） | https://boardgamegeek.com/using_the_xml_api | 存檔 20260924202844 | 存檔 |
| B2 | BGG：XML API Terms of Use | https://boardgamegeek.com/wiki/page/XML_API_Terms_of_Use | 存檔 20261021002430 | 存檔 |
| B3 | BGG：Terms of Service（§6.B.i、6.B.ii、6.B.iv、6.E） | https://boardgamegeek.com/terms | 存檔 20261018153626 | 存檔 |
| B4 | BGG：robots.txt | https://boardgamegeek.com/robots.txt | 存檔 20260501013249（今天直接讀取回 Cloudflare challenge） | 存檔 |
| B5 | BGG：BGG XML API2 文件 | https://boardgamegeek.com/wiki/page/BGG_XML_API2 | 存檔 20261008233231 | 存檔 |
| B6 | BGG XML API2 實測（不帶 token） | https://boardgamegeek.com/xmlapi2/thing?id=13&ratingcomments=1&pagesize=10 | curl，回 HTTP 401 | 已確認 |
| B7 | BGG 主要開發者 Daniel Karp（GitHub `karptonite`，個人檔案寫「Primary developer at BoardGameGeek」）於 2026-10-13 開的 issue | https://github.com/kkjdaniel/bgg-mcp/issues/12 | GitHub API 直接讀取 | 已確認 |
| B8 | BGG 遊戲頁（`numcomments`、`usersrated`） | https://boardgamegeek.com/boardgame/13/catan 、 /boardgame/230802/azul 、 /boardgame/148228/splendor 、 /boardgame/342942/ark-nova 、 /boardgame/128882/the-resistance-avalon | 存檔，日期見 2.3 節表格 | 存檔 |
| B9 | BGG 私有 API：Catan 論壇清單 | https://api.geekdo.com/api/forums?objectid=13&objecttype=thing | 存檔 20230609115002 | 存檔（舊資料） |
| R1 | Reddit：robots.txt | https://www.reddit.com/robots.txt | 直接讀取 | 已確認 |
| R2 | Reddit：User Agreement（Effective 2026-07-01） | https://redditinc.com/policies/user-agreement | 直接讀取 | 已確認 |
| R3 | Reddit：Data API Terms（Last Revised 2026-07-20，§2.4、§3.1、§3.2、§6） | https://redditinc.com/policies/data-api-terms | 直接讀取 | 已確認 |
| R4 | Reddit：Developer Terms（Last Revised 2026-03-24） | https://redditinc.com/policies/developer-terms | 直接讀取 | 已確認 |
| R5 | Reddit：Responsible Builder Policy（Updated 2026-06-05） | https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy | 存檔 20260828024612（直接讀取回 403） | 存檔 |
| R6 | Reddit：Public Content Policy（Updated 2026-10-06） | https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy | 存檔 20261024052831 | 存檔 |
| R7 | Reddit：Data API Wiki（Updated 2026-05-11） | https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki | 存檔 20260914203744 | 存檔 |
| S1 | Shut Up & Sit Down：Terms of Service | https://www.shutupandsitdown.com/tos | 直接讀取 | 已確認 |
| S2 | Shut Up & Sit Down：robots.txt | https://www.shutupandsitdown.com/robots.txt | 直接讀取 | 已確認 |
| W1 | Wikimedia Foundation：Terms of Use（2023-06-07 生效） | https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use | WebFetch | 已確認 |
| P1 | PTT：robots.txt（Cloudflare 代管，含 Content-Signal） | https://www.ptt.cc/robots.txt | 直接讀取 | 已確認 |
| P2 | PTT：使用者條款 2.0.1 | https://www.ptt.cc/index.ua.html | 直接讀取 | 已確認 |
| P3 | PTT BoardGame 板列表與標題搜尋 | https://www.ptt.cc/bbs/BoardGame/index.html 、 https://www.ptt.cc/bbs/BoardGame/search?q= | curl 計數，數字已刪除（見 5.3 節揭露） | 已刪除 |
| P4 | Cloudflare：Managed robots.txt 文件（Last updated 2026-11-02，含 Content Signals 與 `use` 定義） | https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/ | WebFetch | 已確認 |
| H1 | 巴哈姆特：著作權聲明 | https://user.gamer.com.tw/help/detail.php?sn=280&top=1 | 直接讀取 | 已確認 |
| H2 | 巴哈姆特：會員規範（第 14 條） | https://user.gamer.com.tw/help/detail.php?sn=294 | 直接讀取 | 已確認 |
| H3 | 巴哈姆特哈啦區：robots.txt | https://forum.gamer.com.tw/robots.txt | 直接讀取 | 已確認 |
| H4 | 巴哈姆特 桌上遊戲板列表與標題搜尋 | https://forum.gamer.com.tw/B.php?bsn=60537 | curl 計數（約 10 次請求） | 已確認 |
| D1 | Dcard：robots.txt | https://www.dcard.tw/robots.txt | 直接讀取（網頁本身回 403） | 已確認 |
| D2 | Dcard：用戶使用協議 | https://www.dcard.tw/terms | 存檔 20250512152247（直接讀取回 403） | 存檔 |
| V1 | 方格子：robots.txt、llms.txt | https://vocus.cc/robots.txt 、 https://vocus.cc/llms.txt | 直接讀取 | 已確認 |
| V2 | 方格子：會員服務條款（更新日期 2025-12-15） | https://vocus.cc/terms/member | 直接讀取 | 已確認 |
| V3 | 方格子：嵐嵐桌遊筆記個人頁（`articleCount`） | https://vocus.cc/user/@lanlanBG | 直接讀取 | 已確認 |
| A1 | Microsoft Learn：Data, privacy, and security for Foundry Models sold by Azure（ms.date 2026-05-18） | https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/openai/data-privacy | WebFetch | 已確認 |
