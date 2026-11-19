# 聲音怎麼從瀏覽器連到模型

Type: grilling
Status: open
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
