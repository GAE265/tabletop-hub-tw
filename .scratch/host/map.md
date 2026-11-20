# AI 語音主持

## Destination

一份 `.scratch/host/spec.md`，清楚到能直接寫出 AGENTS.md §7 的「情境／操作／預期結果」表格，並拆成 TDD 實作 ticket（放 `.scratch/host-impl/issues/`）。
範圍：主持人在《血與刃的白薔薇》的一局裡帶流程、回答規則問題；即時語音模型與 Agent 框架的選擇（先用真的聲音小測過才寫進 spec）；後端 API 契約；參考畫面與交接說明。
2026-11-20 需求變更後，範圍補三項：語音指令（「等一下」「暫停」「下一步」「上一步」「結束了」「某一方贏了」）、整局記憶、白薔薇 demo 的主持規則增減。交付物不變。

## Notes

- Domain：`host`（#3 AI 遊戲主持，立倫主責，優先級「應做」）。後端會在 `backend/app/domains/host/`；前端只做 `data/`、`state/`、`prototypes/` 與交接說明（AGENTS.md §5.4）。2026-11-19 畫地圖時 repo 裡還沒有任何 host 的程式。
- 規則：遵守 `AGENTS.md`（AI 只讀，不得修改）。術語用 AGENTS.md §10 與 `GLOSSARY.md` 的提案區。不得修改 `openspec/`。
- Skills：`grilling` ticket 呼叫 grilling 與 domain-modeling；`research` ticket 呼叫 research；`prototype` ticket 呼叫 prototype。
- Ticket 的 `Status:` 用 `open`、`claimed`、`resolved`。另有 `closed`：整理地圖時關掉、沒有單獨決定的 ticket。它不擋其他 ticket，不列進 Decisions so far，題目的去向寫在它自己的 Answer。
- 分支：`feature/host`（2026-11-19 立倫決定，原名 `docs/host-wayfinder`）。地圖、決策 ticket、spec、實作 ticket 與之後的程式都放這一個分支，開同一支 PR。這和 games_advisor「先開文件 MR、再一張 ticket 一個 MR」的做法不同。
- 這張地圖只做決策，不寫 `backend/`、`frontend/`、`device/` 的程式。原型放 `.scratch/host/prototypes/`，research 結果放 `.scratch/host/research/<name>.md`。
- 附件（repo 外）：
  - 選型查核報告：`/Users/user/Desktop/團隊專題/02_選題研究/AI語音主持選型查核報告.html`。**它是輸入，不是定案**：沒做桌邊實測與中文盲聽，報告自己也寫只供選型討論。引用它的數字前要回查一手來源。
  - mattpocock 流程指南：`/Users/user/Desktop/團隊專題/99_其他/mattpocock-skills_開發指南.md`（§0、§1 是立倫的專案做法）。
- wayfinder 的流程（下一張做哪張、怎麼開每張 ticket 的 session、什麼時候 commit）在持有地圖的對話由立倫直接決定，不經總管，也不向總管回報進度（2026-11-19 立倫決定）。到達 Destination（`spec.md` 寫好、實作 ticket 拆好）才交給總管派實作 worker 與驗收。要改可改路徑以外的檔案、牽涉別的分支或 worktree，或立倫明說要通知時，才找總管。
- 2026-11-20 整理（立倫要求依專案實務需要刪減並更新 ticket）。開著的 ticket 從 7 張收成 5 張，Not yet specified 清空。剩下的路只有五步（已由同日的需求變更更正：現在是六步，順序見下面「2026-11-20 需求變更」那一條）：
  1. 「[主持人能查哪些資料、誰能開主持](issues/13-host-tools-and-permissions.md)」
  2. 「[玩家怎麼和主持人說話](issues/11-how-players-talk-to-host.md)」
  3. 「[選哪個 Agent 框架、它負責什麼](issues/10-agent-framework-choice.md)」（要等第 1 步）
  4. 「[寫 spec.md](issues/21-write-spec.md)」（要等前三步）
  5. 「[把 spec 拆成實作 ticket](issues/22-split-spec-into-impl-tickets.md)」

  整理時做了三件事：
  - 關掉四張、沒有單獨決定：「[主持人怎麼撐完一局：記性上限與 180 秒斷線](issues/17-keep-host-alive-through-a-match.md)」與「[前端收音與播音用哪些套件](issues/19-frontend-audio-packages.md)」改成預設做法，列在「寫 spec.md」等立倫確認；「[主持人的人設與台詞](issues/18-host-persona-and-script-lines.md)」移到實作階段；「[手機實測怎麼拿到 HTTPS](issues/20-https-for-phone-testing.md)」列為範圍外。
  - 前三步的題目都重寫過：拿掉已經被別張決定的題目，補上試聽與查證到的事實。拿掉了什麼、移到哪裡，寫在各自的 Comments。
  - 原本 Not yet specified 的項目（整合層介面與 fake、要不要存資料、API 契約與參考畫面、怎麼驗收、費用）都收進「寫 spec.md」；ADR 改由「選哪個 Agent 框架、它負責什麼」結案時寫。
- **每張 ticket 開工前，先核對它的前提還成不成立**（2026-11-20 立倫要求）。要對三處：題目開頭「已經定案」的那幾條、`Blocked by` 那幾張的 Answer、地圖 Decisions so far 裡標了「已由…更正」的行。有一條不成立，就先停下來告訴立倫，不照舊題目往下做。（要對哪三處是整理時定的做法，不是立倫的原話。）
- 2026-11-20 需求變更（立倫）。四項：
  1. 主持人要支援語音指令，用工具呼叫處理：「等一下」「暫停」（同一個動作）、「下一步」、「上一步」、「結束了」「某一方贏了」（兩種說法都可以結束）。
  2. 主持人照桌遊規則說話。語音模型記得的有限，所以要有辦法做到整局記憶。每個階段開始時，後端把那個階段的規則要點交給主持人，不再讓它自由說。
  3. 承上，LangGraph 當首選。做不到才回頭看另外兩個框架。
  4. 《血與刃的白薔薇》是這次 demo 的桌遊，要討論追加哪些、刻意忽略哪些主持規則。

  Destination 的交付物不變，範圍補了三項。Out of scope 不變。沒有 ticket 作廢。被推翻的前提與去向：
  - 「[主持人在一局裡怎麼帶流程](issues/08-host-flow-in-a-match.md)」有三處更正：階段開始自由說、開口退回的說法、結束的說法。Answer 不改，指向寫在它的 Comments。
  - 「[主持人怎麼撐完一局：記性上限與 180 秒斷線](issues/17-keep-host-alive-through-a-match.md)」關閉時的理由（記憶是工程細節、前情就是階段狀態）被推翻。記憶的題目改由「[選哪個 Agent 框架、它負責什麼](issues/10-agent-framework-choice.md)」決定。它維持關閉；180 秒斷線與重送仍是「[寫 spec.md](issues/21-write-spec.md)」的預設做法。
  - 還開著的三張題目改過，改了什麼寫在各自的 Comments：「選哪個 Agent 框架、它負責什麼」、「[玩家怎麼和主持人說話](issues/11-how-players-talk-to-host.md)」、「寫 spec.md」。「[主持人能查哪些資料、誰能開主持](issues/13-host-tools-and-permissions.md)」沒有改（立倫決定撤回）：工具清單加暫停與兩種結束說法、每個階段規則要點的來源，改在「寫 spec.md」寫 spec 時一起定。
  - 新開「[白薔薇 demo 的主持規則：追加哪些、忽略哪些](issues/23-white-rose-demo-host-rules.md)」。已定的忽略項（魔法之書不解釋、不判勝負、不讀戰績）沒有被推翻，是那張的起點。
  - `GLOSSARY.md` 提案區新增「語音指令」「整局記憶」。

  現在的路是六步：
  1. 「白薔薇 demo 的主持規則：追加哪些、忽略哪些」
  2. 「玩家怎麼和主持人說話」（不用等第 1 步）
  3. 「主持人能查哪些資料、誰能開主持」（不用等第 1 步；原樣沒改）
  4. 「選哪個 Agent 框架、它負責什麼」（要等第 1、3 步）
  5. 「寫 spec.md」（要等前四步）
  6. 「[把 spec 拆成實作 ticket](issues/22-split-spec-into-impl-tickets.md)」
- 和 wayfinder 原版不同的做法：
  - `research` ticket 不需要立倫在場。由持有地圖的 wayfinder session 自己用 Orca 派 research worker（`orca orchestration worker-start`），worker 回報給它，不回報給總管（2026-11-19 立倫決定）。它驗收後更新地圖：把結論寫進 Decisions so far，把變清楚的問題開成新 ticket。全部結案後，向總管回報一次摘要。不開 `research/<name>` 分支、不開 subagent、不 push。research worker 不得再往下派工。
  - 派 research 的規定：
    - 一個 worker 一張 ticket。
    - worker 只能改自己的 ticket 檔與自己的結果檔，不改 `map.md`，不 commit。
    - 只用一手來源，每項附連結與查核日期。查不到就寫「查不到」，不用模型的記憶補。
    - 規則書這類有著作權的內容，只能用自己的話摘要。
  - 派 research 用的模型：收集網路資料用 Codex（2026-11-19 時只有 `gpt-6.1-sol` 派得動）；要讀本機資料庫或程式的用 Claude `opus` 以上。不要用 Claude `sonnet` 派需要跑指令或改檔的工作，它每個動作都會跳權限提示給立倫。`--effort` 一定要和 `--model` 一起給。
  - 驗收 research（不合格就用 `orca orchestration send` 退回原 worker，不自己代修）：
    - 只動了那兩個檔。
    - 來源確實是一手的。
    - 沒有貼原文。規則書要用資料庫全文比對。
    - 「查不到」與「要問立倫」是讀完整份資料後才下的結論。
  - `grilling`、`prototype` ticket 要立倫在場，一次一張。
- 畫地圖時定下的範圍與方向（2026-11-19，立倫）：
  - 需求前提：反應快、感情豐富的中文、口音不限、能查資料。
  - 主持人以帶流程為主，也回答規則問題。規則問題用 `rules_qa`（永傑主責）已有的規則檢索，不另建規則庫。（2026-11-20：規則從哪裡查要重新確認，原因與選項在「主持人能查哪些資料、誰能開主持」第 1 題。）
  - 首版只做一款：《血與刃的白薔薇》（Blades & Rose，BGG 編號 400566）。`matches` 已有它的回合紀錄格式與陣營（`backend/app/domains/matches/game_definitions.py`），`rules_qa` 已有它的規則影片。
  - 聲音從桌上的手機或平板進出：開 Flutter Web 頁面，用它的麥克風與喇叭。
  - 首版主持人只讀資料，不幫忙記回合。回合照舊由玩家在戰績畫面輸入。（2026-11-20 已由「主持人在一局裡怎麼帶流程」更正：一場主持不掛戰績的局，主持人不讀 `matches`。）
  - 模型首選方向（不是定案）：阿里雲的 `Qwen-Audio-3.1-Realtime`。Flash 或 Plus、要不要把難題轉交後端的文字思考模型，由決策 ticket 決定。Azure 的 `gpt-realtime-2.1` 只當備案，不排實測。區域固定新加坡（2026-11-19 立倫決定）。（已定案：語音用 Flash，難題轉交思考模型，見 Decisions so far。）
  - 為了展示，一定要用 Agent 框架，三選一：LangChain、LangGraph、Microsoft Agent Framework。展示重點是「看得到主持人走到哪個階段、查了什麼資料」。三個都接不上時回來問立倫，不自行改成不用框架。（2026-11-20 已由需求變更更正：不再三選一，LangGraph 當首選，做不到才回頭看另外兩個。）
  - 阿里雲帳號由立倫自己開、用自己的額度，金鑰只放本機 `.env`。測試與 Demo 都只用組員自己的聲音（2026-11-19 立倫決定）。
- 會碰到的規則（決策時要對照）：
  - AGENTS.md §4.2：domain 不得直接 import 模型廠商的 SDK，外部服務一律包在 `integrations/` 後面；domain 之間只能呼叫對方的 `service`。
  - AGENTS.md §2 第 4 點：新增第三方套件要在 MR 說明寫理由。
  - AGENTS.md §3：`integrations/llm/` 由瑋鋐擁有，`integrations/tts/` 由永傑擁有（2026-11-19 時還不存在）。改共用區要 @ 擁有者。
  - AGENTS.md §5.3：前端不放任何秘密；只能在網頁上用的程式碼要包在 `core/platform/` 的介面後面。
  - AGENTS.md §7.5：domain 的測試一律用手寫 fake，不連真正的外部服務。
- 牽涉其他 domain 的事（2026-11-19 由「《血與刃的白薔薇》一局的流程」查出，2026-11-20 問到答案，細節在「向新善、永傑、瑋鋐確認戰績欄位與規則全文的問題」）：
  - `matches`（新善主責）會改：允許整桌都不出牌的空清單；司教算進 `faithful_count`；「本回合首家」是收到金幣、放水晶的人。2026-11-20 遠端還沒看到改動，寫 spec 前要再看一次 `dev`。同日「主持人在一局裡怎麼帶流程」決定一場主持不掛戰績的局、不讀回合紀錄，這三項不再直接影響主持。
  - `rules_ingest`（瑋鋐主責）、`rules_qa`（永傑主責）：規則全文的雜訊與圖上讀不到的字暫不修正，主持人這邊自己應對。
- 固定偏好：
  - 不問時程問題，推薦答案也不附日期或天數。
  - commit、PR、文件都不加 AI 署名。
  - 不 push、不建 GitHub issue、不開 research 分支。
  - 抓取的資料、規則書原文、錄音檔都不進 repo。規則流程只能用自己的話摘要。
  - 立倫和組員各用自己的 LLM、embedding 模型與 PostgreSQL；設定不要假設共用。
  - ticket 的張數要符合學生專題的規模。2026-11-20 立倫表示 ticket 一直增加，要求依專案實務需要刪減。之後新冒出來的題目，先放進現有的 ticket 或「寫 spec.md」的預設做法；真的需要立倫另外討論，才開新 ticket。（後半句是整理時定的做法，不是立倫的原話。）

## Decisions so far

<!-- the index: one line per closed ticket, enough to judge relevance, then zoom the link for the detail the ticket holds -->

- [Qwen 即時語音模型的官方規格](issues/01-qwen-realtime-facts.md)：Flash 與 Plus 都能用 WebSocket、WebRTC、AOQ，新加坡與北京可用；官方有不把長效金鑰交給瀏覽器的接法（後端交換 SDP、短效金鑰）；可按住說話、可呼叫工具，停播要應用程式自己清空待播內容；「300 秒」是歷史音訊容量（最多 50 輪），不是連線上限，固定的最長連線時間查不到；Flash 對 Plus 沒有官方比較數字，只有價格差（Plus 約 3.5 到 12.8 倍）；平台預設保留推論資料最多 30 天，零保留清單沒有這個模型
- [難題轉交後端思考模型的做法](issues/02-delegate-to-thinking-model.md)：做得到，官方有範例，語音模型用工具呼叫把問題交給後端再唸出答案；後端可用 Qwen 文字模型或專案現有的 Azure 文字介面（實際部署哪個模型要問立倫）；查不到 Plus 有可控制的「先想再答」；等待語講得快不代表裁決快，還要處理逾時、中斷、過期的舊答案；本遊戲要等幾秒查不到，只能實測
- [三個 Agent 框架怎麼接 Qwen、怎麼展示](issues/03-agent-frameworks-fit.md)：LangChain 1.5.2、LangGraph 1.2.22、Microsoft Agent Framework 1.26.0 都接得上 Qwen 文字模型，都查不到能直接接 Qwen 即時語音的官方轉接器，所以框架只能放在後端處理工具請求那一段；三個都能在本機畫流程圖、看每一步，不必另外付費；都沒試跑過；沒有替立倫選
- [《血與刃的白薔薇》一局的流程](issues/04-white-rose-match-flow.md)：5 至 10 人；開局準備、夜晚階段（只在開局）、若干回合，每個回合三個階段（傳金幣放水晶、依序決定出牌、翻牌結算）；規則書裡沒有主持人，開局口令是玩家自己喊；`matches` 的回合欄位要到階段 2、3 才知道；獲勝門檻的數字印在圖上讀不到，共 11 條要問立倫或其他 domain 的主責
- [Flutter Web 怎麼收音與即時播音](issues/05-flutter-web-audio.md)：能即時收音與邊收邊播，WebSocket 與 WebRTC 都可用；插話時的停播、清空待播內容、拒收舊回覆要前端自己做；手機要 HTTPS，並由玩家點一下才能出聲；鎖屏後持續雙向語音沒有保證；`record` 7.x 與 `web` 1.1.2 會提高 Flutter SDK 的門檻；網頁專用的部分要包在 `core/platform/`
- [註冊阿里雲並確認能呼叫 Qwen 即時語音](issues/06-alibaba-cloud-account.md)：國際站個人帳號、新加坡區；Flash 與 Plus 都實際叫得到並收到聲音（用文字輸入）；Flash 免費額度 100 萬 tokens 到 2027/02/18，Plus 在主控台看不到免費額度；新加坡 Flash 試 74 個聲線有 54 個能用，只在北京的 20 個不行；設定欄位提案 `HOST_REALTIME_API_KEY` 加整段 API Host；立倫選模型先看有感情、自訂工具、成本
- [用真的聲音試聽 Qwen 主持人](issues/07-listen-to-qwen-host.md)：聲線選 `xunanchuan_v3.1`、`longyuan_v3.1`，品質都很高，Flash 與 Plus 音色、速度聽不出差別；`smart_turn_v2` 講完 0.4 到 0.8 秒出聲，附和不停，但「等一下」也不停；`server_vad` 能打斷，但附和也會停；規則題會先查再答，等待中被追問會先猜答案（加指令後改成丟掉追問）；難題轉交裁判多約 2 秒，Plus 轉交 6 題全對；180 秒沒回答就斷線，歷史預設 20 輪就忘；一條連線不能換聲線；外放加瀏覽器回音消除沒有自己打斷自己。結案後補測：桌邊閒聊 `smart_turn_v2` 0／6 回應、`server_vad` 5／6；沒查規則就會編；每 2 分鐘插系統訊息可以不出聲避開 180 秒斷線
- [接不接受阿里雲保留玩家的聲音最多 30 天](issues/14-voice-data-retention.md)：接受，開發、組員、玩家都一樣，頁面與文件都不另外告知；測試與 Demo 只用組員的聲音；區域固定新加坡，不用北京
- [用 Flash 還是 Plus、要不要轉交思考模型](issues/09-model-lineup.md)：語音用 Flash；難題由模型自己決定轉交「思考模型」，預設 Azure `gpt-5.6-luna`（走 `integrations/llm`，可用 `HOST_THINKING_MODEL` 換成 Sol）；等待台詞「我翻一下規則」「讓我來好好的想一想～」，第 8 秒補一句，15 秒放棄改用查到的規則回答；等待中問新問題就取代舊題；即時語音偏離 §4.2，要寫 ADR，等連線方式與框架定案
- [向新善、永傑、瑋鋐確認戰績欄位與規則全文的問題](issues/16-ask-owners-about-matches-and-rules-text.md)：`matches` 會允許空的出牌清單、司教算進 `faithful_count`、首家是收到金幣放水晶的人（遠端尚未改）；規則全文的雜訊與圖上的字暫不修正，獲勝門檻、魔法之書、睜眼角色從檢索拿不到
- [對照實體遊戲，補齊白薔薇規則裡讀不到的地方](issues/15-white-rose-rule-gaps.md)：獲勝門檻各人數不同（白薔薇獻祭「人數減 1」張、血刃殺 3 到 6 張），圓版水晶格 4 到 7 格，放滿就結束；魔法之書效果不在主持範圍，玩家自己讀；暗刃即瞞刃；睜眼的四種角色分不出誰是誰；以規則書為準，不採用第三方文章
- [主持人在一局裡怎麼帶流程](issues/08-host-flow-in-a-match.md)：一場主持不掛戰績的局，只填人數；開場唸門檻與格數、帶開局準備與夜晚（敲桌子倒數 10 秒）；換階段用「下一步」鍵或開口，可退回；後端記第幾回合、哪個階段、放了幾顆水晶，主持人不知道翻牌結果、不判勝負；階段開始自由說，固定台詞只有開場、準備、夜晚、最後一個回合、結束、魔法之書；頁面關掉保留 30 分鐘；用規則書的「回合」。（2026-11-20 已由需求變更更正三處：階段開始不再自由說，改照後端交給的規則要點說；開口退回的說法是「上一步」，另加「等一下」「暫停」；結束可以說「結束了」或「某一方贏了」。細節在「白薔薇 demo 的主持規則：追加哪些、忽略哪些」「玩家怎麼和主持人說話」「主持人能查哪些資料、誰能開主持」「選哪個 Agent 框架、它負責什麼」決定。）
- [聲音怎麼從瀏覽器連到模型](issues/12-audio-connection-path.md)：經後端轉送（手機 ⇄ 後端 ⇄ 阿里雲），WebRTC 直連只記備案；工具請求在後端執行；轉送用非同步，查規則與思考模型丟到另一條執行緒跑同步程式；手機與後端用自己的格式（原始 PCM＋JSON）；先 `POST /api/v1/hosting-sessions` 再用一次性通行碼連 WebSocket；設定 `HOST_REALTIME_PROVIDER`（預設 `fake`）、`_API_KEY`、`_API_HOST`、`_MODEL`；連不上回 `HOST_REALTIME_UNAVAILABLE`；首版後端固定一台

## Not yet specified

<!-- in-scope fog you can't ticket yet; graduates as the frontier advances -->

（無。2026-11-20 整理時，原本列在這裡的項目都有了去處，見 Notes 的整理紀錄。之後如果決策的答案推翻了前提，再回來補。）

## Out of scope

<!-- work ruled beyond the destination; closed, never graduates -->

- 接發牌機與睜眼偵測（`dealer`，新善主責）：`device/` 目前只有攝影機與馬達的骨架，沒有連線。之後另開一張地圖。
- 正式頁面：由永傑依交接說明製作（AGENTS.md §5.4）。
- 第二款以上的遊戲。
- 從聲音認出是哪位玩家。
- 地端模型；要求台灣口音。
- 寫 `backend/`、`frontend/`、`device/` 的程式：Destination 只到寫好 spec 並拆成實作 ticket。
- 主持人的人設與固定台詞定稿（2026-11-20 移出，原「[主持人的人設與台詞](issues/18-host-persona-and-script-lines.md)」）：字句不影響架構與測試，移到實作階段，由立倫用真的後端試聽後定稿。spec 只放草稿。
- 手機實測用的 HTTPS 怎麼來（2026-11-20 移出，原「[手機實測怎麼拿到 HTTPS](issues/20-https-for-phone-testing.md)」）：開發與部署環境的事，不影響 spec。驗收只寫成一條前置條件。
