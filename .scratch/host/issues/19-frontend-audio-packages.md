# 前端收音與播音用哪些套件

Type: grilling
Status: open
Blocked by: 11, 12
Map: [AI 語音主持](../map.md)

## Question

「[聲音怎麼從瀏覽器連到模型](12-audio-connection-path.md)」定了手機只連我們的後端，走 WebSocket：聲音送原始 PCM（上行 16 kHz、下行 24 kHz 單聲道），其他訊息用 JSON。依「[Flutter Web 怎麼收音與即時播音](05-flutter-web-audio.md)」的研究，決定前端用什麼：

1. 收音：`record`、`flutter_sound`，或直接用瀏覽器的 API（包在 `core/platform/` 後面，AGENTS.md §5.3）。
2. 播音：邊收邊播、插話時立刻停播並清空待播內容、拒收舊回覆，用哪個套件或瀏覽器的 API 做得到。
3. 連線：`web_socket_channel`（目前只是間接相依，要改成直接宣告）。
4. `record` 7.x 與 `web` 1.1.2 會提高 Flutter SDK 的版本門檻：本機與組員的 Flutter 版本夠不夠、要不要升。動到前端共用區或 SDK 門檻要和永傑談（AGENTS.md §3）。
5. 新增套件的理由怎麼寫（AGENTS.md §2 第 4 點）。

## Comments
