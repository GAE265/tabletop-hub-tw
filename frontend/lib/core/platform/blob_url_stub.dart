import 'dart:typed_data';

/// 非網頁平台：還不支援（見 blob_url.dart）。
String createBlobUrl(Uint8List bytes, String mimeType) =>
    throw UnsupportedError('只有網頁版可以把檔案內容轉成 blob 網址');

void revokeBlobUrl(String url) {}
