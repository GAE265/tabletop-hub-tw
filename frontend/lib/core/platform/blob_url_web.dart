import 'dart:js_interop';
import 'dart:typed_data';

import 'package:web/web.dart' as web;

/// 網頁版：建立 blob 網址；用完要 [revokeBlobUrl] 釋放記憶體。
String createBlobUrl(Uint8List bytes, String mimeType) {
  final blob = web.Blob([bytes.toJS].toJS, web.BlobPropertyBag(type: mimeType));
  return web.URL.createObjectURL(blob);
}

void revokeBlobUrl(String url) => web.URL.revokeObjectURL(url);
