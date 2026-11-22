# 聲音怎麼從瀏覽器連到模型

Type: grilling
Status: resolved
Blocked by: 01, 05
Map: [AI 語音主持](../map.md)

## Question

聲音要從桌上的 Flutter Web 頁面送到阿里雲的即時語音模型，再把主持人的聲音送回來。前端不能放金鑰（AGENTS.md §5.3）。依模型規格與 Flutter Web 的研究結果，決定：

1. 走哪條路。研究後有三條：
   - WebRTC 直連：瀏覽器把連線資料交給我們的後端，後端帶金鑰向阿里雲換回應，再交回瀏覽器。之後聲音直接在瀏覽器與阿里雲之間走，前端拿不到金鑰。官方有這個接法的文件，沒有實測過。
   - WebSocket 直連：後端發短效金鑰（預設 60 秒，最長 30 分鐘，不能提前作廢）給瀏覽器。問題是官方要求把金鑰放在連線的標頭，而瀏覽器的 WebSocket 不能自訂標頭，查不到官方的瀏覽器範例。走不走得通要先試。
   - 經後端轉送：瀏覽器連我們的後端，後端再連阿里雲。
   另外還有阿里雲自己的 AOQ SDK（官方說回音消除與弱網路表現較好），但授權條款查不到，Flutter Web 能不能用也沒查。
   比較這幾條在延遲、金鑰安全、後端能不能看到與攔截工具請求上的差別。
2. 模型要查資料時，工具請求在哪裡執行：一定要回到後端（權限檢查寫在 `service`，AGENTS.md §4.5）。直連時工具請求怎麼回到後端。
3. 後端目前一律同步寫法（AGENTS.md §4.4 規定資料庫存取用同步）。轉送即時音訊需要長時間連線，和現有寫法衝不衝突；衝突時怎麼隔開。
4. 金鑰與端點的設定放哪裡、叫什麼。
5. 連不上阿里雲時回什麼（AGENTS.md §4.3 的 503 是「外部服務暫時無法使用」）。
6. 要不要等「[用真的聲音試聽 Qwen 主持人](07-listen-to-qwen-host.md)」試過瀏覽器直連再決定。

## Comments

- 2026-11-19：「[Qwen 即時語音模型的官方規格](01-qwen-realtime-facts.md)」與「[Flutter Web 怎麼收音與即時播音](05-flutter-web-audio.md)」已結案。和這張有關的事實（細節在 [qwen-realtime-facts](../research/qwen-realtime-facts.md)、[flutter-web-audio](../research/flutter-web-audio.md)）：
  - WebSocket 的音訊格式：送出去是 16 kHz 單聲道 PCM，收回來是 24 kHz 單聲道 PCM。WebRTC 的格式官方沒寫。
  - 直連時，工具請求會出現在瀏覽器這一端（WebRTC 走資料通道）。要讓後端執行工具，前端得把請求轉給後端、再把結果送回模型。
  - 瀏覽器的 WebSocket 沒有自動的流量控制，處理不及時資料會一直堆在記憶體。
  - Flutter 這邊，WebSocket 用 `web_socket_channel`，WebRTC 用 `flutter_webrtc`，Web、Android、iOS 都支援。WebRTC 視網路狀況可能需要額外的中繼伺服器。
  - 現有的 Azure 文字介面是同步的單次呼叫，不能直接拿來當即時語音的介面。
  - 固定的最長連線時間查不到；官方只說閒置太久可能斷線。
- 2026-11-19：「[用真的聲音試聽 Qwen 主持人](07-listen-to-qwen-host.md)」已結案。和連線方式有關的事實：
  - 原型走「經後端轉送」：瀏覽器連本機 Python 轉接程式，轉接程式帶金鑰連阿里雲，也在轉接程式裡執行工具。這條路走得通，玩家講完 0.4 到 0.8 秒就聽到第一個聲音。瀏覽器直連（WebSocket、WebRTC）都沒有試，第 6 題要等的試驗沒有做。
  - **180 秒沒產生任何回答，阿里雲就會關掉連線**（code 1007，理由寫「no response was generated for 180 seconds」）。跟有沒有送聲音、有沒有 WebSocket ping 無關。
  - 單一則用戶端訊息太大，阿里雲會直接斷線（`1009 message too big`）。兩次回報的上限不同，一次 1,048,576 bytes，一次 262,144 bytes。聲音照官方建議每 20 到 100 毫秒送一小段就沒問題。
  - 工具結果送回去時，如果主持人正在產生回答（「another response is in progress」）或玩家正在講話（「user is speaking」），送出的「請回答」會被拒。不管哪條路，後端都要等到可以送的時候再送，或被拒後重送。

## Answer

2026-11-20 立倫決定：

1. **路線：經後端轉送**（手機 ⇄ 我們的後端 ⇄ 阿里雲），不等瀏覽器直連的試驗。
   - 理由：已定的事有很多要後端隨時插話或看得到主持人在做什麼：換階段時告訴主持人第幾回合哪個階段、頁面的「下一步」鍵、查規則與轉交思考模型、第 8 秒補話與 15 秒放棄、晚到的舊答案不唸、被拒後重送、每 2 分鐘送不出聲的訊息。直連的話，這些都要由手機網頁轉來轉去，前端 `state/` 要扛一半的主持邏輯。
   - 這是唯一實際走過的路（07 試聽，本機講完 0.4 到 0.8 秒出聲）。部署到 Azure 後多經過一站會慢多少，列進驗收要量的項目。
   - WebRTC 直連只在 spec 記一行備案。WebSocket 直連不採用（瀏覽器不能在連線標頭放金鑰）。AOQ SDK 不採用（授權條款查不到，Flutter Web 能不能用沒查）。
2. **工具請求在後端執行**：模型的工具請求先到後端，後端呼叫 `rules_qa` 的 `service` 與思考模型（`integrations/llm`），再把結果送回模型。權限檢查照 AGENTS.md §4.5 寫在 `service`。
3. **同步與非同步**：
   - 轉送用非同步寫（同時收手機的聲音、收阿里雲的聲音、等工具結果）。
   - 查規則、呼叫思考模型丟到另一條執行緒，跑現有的同步程式。
   - 主持本身不碰資料庫（狀態放記憶體，08 已定），只有查規則會碰，而它照 §4.4 用同步寫法，所以不衝突。
   - 連阿里雲用 `websockets` 套件。它已因 `uvicorn[standard]` 間接裝在專案裡（17.4 版），改成直接宣告，MR 說明寫理由（AGENTS.md §2 第 4 點）。
   - 轉送程式放 `integrations/` 的哪個資料夾、介面長怎樣，留在地圖的「整合層介面與 fake」。
4. **手機與後端之間用自己的格式**，不照搬阿里雲的：
   - 聲音送原始資料，上行 16 kHz、下行 24 kHz 單聲道 PCM（和阿里雲相同，後端不轉檔）；其他訊息用 JSON。
   - 阿里雲的事件（工具請求、內部事件）不轉給手機。手機只收主持人的聲音、目前回合與階段、正在查規則、錯誤這類訊息。以後換模型，前端不用改。
   - 每種訊息的欄位寫在 spec 的 API 契約。
5. **身分：先開一場主持，再用一次性通行碼連聲音**。瀏覽器的 WebSocket 不能自訂標頭，`X-Dev-User` 與登入 token 都帶不上去。
   1. `POST /api/v1/hosting-sessions`（一般請求，照常帶身分標頭，body 帶人數）→ 201，回傳這場主持的 id 與一次性通行碼。
   2. 手機把通行碼放在 WebSocket 網址上連線。通行碼 60 秒內有效、只能用一次；後端核對後才開始轉送。
   - 重整頁面或接著主持（08 的 30 分鐘內）時，再打一次 API 拿新通行碼。
   - 誰可以開主持，由「[主持人能查哪些資料、誰能開主持](13-host-tools-and-permissions.md)」決定。
6. **設定**（只放後端 `.env`，寫進 `.env.example`；照 `RULES_QA_EMBEDDING_*` 的前例）：

   | 欄位 | 必填 | 內容 |
   |---|---|---|
   | `HOST_REALTIME_PROVIDER` | 否 | `fake`（預設，不連阿里雲）或 `cloud`；`cloud` 缺欄位就啟動失敗 |
   | `HOST_REALTIME_API_KEY` | `cloud` 時 | 阿里雲金鑰（`sk-ws` 開頭） |
   | `HOST_REALTIME_API_HOST` | `cloud` 時 | 主控台的整段 API Host，區域包含在裡面 |
   | `HOST_REALTIME_MODEL` | 否 | 預設 `qwen-audio-3.1-realtime-flash` |

   原型的 `HOST_REALTIME_WORKSPACE_ID`、`HOST_REALTIME_REGION` 不保留。前端不知道任何阿里雲的設定。聲線不放設定，由「[主持人的人設與台詞](18-host-persona-and-script-lines.md)」決定。
7. **連不上時**：
   - 後端在手機連上 WebSocket 時才連阿里雲（提早連會開始算 180 秒）。連不上就送錯誤訊息 `{"error": {"code": "HOST_REALTIME_UNAVAILABLE", ...}}`（格式照 AGENTS.md §4.3），再關掉連線。WebSocket 沒有 HTTP 狀態碼，503 只體現在錯誤碼的意思上。
   - 金鑰錯誤也回 `HOST_REALTIME_UNAVAILABLE`，真正原因只記在後端紀錄。
   - 進行中斷線：自動重連、玩家聽到什麼、頁面顯示什麼，交給「[主持人怎麼撐完一局：記性上限與 180 秒斷線](17-keep-host-alive-through-a-match.md)」。
   - 思考模型出錯：照 09，改用查到的規則回答。
8. **部署：首版後端固定一台**。一場主持的狀態在那台的記憶體，重連若分到另一台就認不得。要多台時再決定狀態搬去哪。Azure 長時間連線的閒置逾時沒查，列進驗收要實測的項目。

影響：
- 地圖「整合層介面與 fake」：連線方式已定（後端轉送、非同步），只等「[選哪個 Agent 框架、它負責什麼](10-agent-framework-choice.md)」。「為什麼不直連」寫進那裡預定的同一份 ADR，不另開。
- 新開「[前端收音與播音用哪些套件](19-frontend-audio-packages.md)」、「[手機實測怎麼拿到 HTTPS](20-https-for-phone-testing.md)」。
- 沒有新增術語。
