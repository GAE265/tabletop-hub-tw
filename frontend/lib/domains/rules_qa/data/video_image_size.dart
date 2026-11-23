import 'dart:typed_data';
import 'dart:ui';

/// 從 PNG、JPEG 的檔頭讀出寬高（標區域時要先知道照片的比例）；讀不出來時回 null。
///
/// 後端存照片前已依 EXIF 轉正（MR 7），所以檔頭的寬高就是擺正後的大小。
Size? imageSizeOf(Uint8List bytes) => _png(bytes) ?? _jpeg(bytes);

/// 套用方向（順時針轉幾度）之後的大小：90、270 度時寬高對調。
Size displaySize(Size size, int orientation) =>
    orientation % 180 == 0 ? size : Size(size.height, size.width);

Size? _png(Uint8List b) {
  const signature = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];
  if (b.length < 24) return null;
  for (var i = 0; i < signature.length; i++) {
    if (b[i] != signature[i]) return null;
  }
  final data = ByteData.sublistView(b);
  return Size(data.getUint32(16).toDouble(), data.getUint32(20).toDouble());
}

Size? _jpeg(Uint8List b) {
  if (b.length < 4 || b[0] != 0xFF || b[1] != 0xD8) return null;
  final data = ByteData.sublistView(b);
  var i = 2;
  while (i + 9 < b.length) {
    if (b[i] != 0xFF) return null;
    final marker = b[i + 1];
    // SOF0–SOF15（不含 DHT C4、JPG C8、DAC CC）記著高與寬
    if (marker >= 0xC0 &&
        marker <= 0xCF &&
        marker != 0xC4 &&
        marker != 0xC8 &&
        marker != 0xCC) {
      final height = data.getUint16(i + 5);
      final width = data.getUint16(i + 7);
      return Size(width.toDouble(), height.toDouble());
    }
    i += 2 + data.getUint16(i + 2);
  }
  return null;
}

/// 選到 HEIC 時給店員的說明（2026-11-22 永傑決定：先不自動轉檔，請店員改相機設定）。
const heicUnsupportedMessage = '不支援 HEIC，請把相機格式改為最相容（JPEG）';

/// 是不是 HEIC／HEIF：看檔頭的 ftyp 品牌；檔頭看不出來時，副檔名是 .heic／.heif 且內容不是
/// JPEG、PNG 也算（iPhone 選圖時常會先轉成 JPEG，這種照片可以上傳）。
bool isHeicImage(String name, Uint8List bytes) {
  const brands = {
    'heic',
    'heix',
    'hevc',
    'hevx',
    'heim',
    'heis',
    'mif1',
    'msf1',
  };
  if (bytes.length >= 12 &&
      String.fromCharCodes(bytes.sublist(4, 8)) == 'ftyp' &&
      brands.contains(String.fromCharCodes(bytes.sublist(8, 12)))) {
    return true;
  }
  final lower = name.toLowerCase();
  final named = lower.endsWith('.heic') || lower.endsWith('.heif');
  return named && imageSizeOf(bytes) == null;
}
