/// 把記憶體裡的檔案內容轉成瀏覽器可以播放的網址（blob:）。只有網頁版有；
/// 其他平台拋 [UnsupportedError]（之後轉 App 時改成暫存檔）。
library;

export 'blob_url_stub.dart' if (dart.library.js_interop) 'blob_url_web.dart';
