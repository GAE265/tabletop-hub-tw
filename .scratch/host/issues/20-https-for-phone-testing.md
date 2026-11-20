# 手機實測怎麼拿到 HTTPS

Type: grilling
Status: open
Blocked by: 12
Map: [AI 語音主持](../map.md)

## Question

手機瀏覽器要 HTTPS 才能用麥克風，連電腦的區網位址不算（「[Flutter Web 怎麼收音與即時播音](05-flutter-web-audio.md)」）。07 試聽只在 Mac 的 Chrome（localhost）做。「[聲音怎麼從瀏覽器連到模型](12-audio-connection-path.md)」定了手機要連後端的 WebSocket（`wss://`），頁面與後端都要 HTTPS。決定開發與驗收時怎麼讓桌上的手機或平板連得到：

1. 用哪種做法：臨時對外網址（例如通道服務）、本機自簽憑證並讓手機信任、或直接部署到 Azure 測。
2. 金鑰只在本機 `.env`，對外網址開著時誰連得到後端、要不要限制。
3. 誰的電腦與手機做實測（測試只用組員的聲音）。
4. 要不要寫進交接說明，讓組員也能照做。

## Comments
