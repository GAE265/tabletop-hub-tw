import 'package:file_picker/file_picker.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';

import '../../support/fakes.dart';

void main() {
  // 選圖設定不列 HEIC：iPhone Safari 看到網頁只收 JPEG、PNG 時，會在上傳前自動把 HEIC 轉成 JPEG
  // （暫行方案，待 iPhone 實測）。萬一沒有轉，選到的 HEIC 仍由 state 擋下並說明。
  test('選圖設定只列 JPEG、PNG，不列 HEIC／HEIF，可以一次選多張並讀出內容', () async {
    final filePicker = FakeFilePicker();

    final images = await FilePickerImagePicker(
      filePicker: filePicker,
    ).pickImages();

    expect(images, isNull);
    expect(filePicker.type, FileType.custom);
    expect(filePicker.allowedExtensions, ['jpg', 'jpeg', 'png']);
    expect(filePicker.allowMultiple, isTrue);
    expect(filePicker.withData, isTrue);
  });
}
