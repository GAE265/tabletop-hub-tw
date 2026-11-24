import 'package:file_picker/file_picker.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';

import '../../support/fakes.dart';

void main() {
  // 選圖設定不列 HEIC：讓 iPhone Safari 有機會在上傳前自動轉成 JPEG；
  // 沒有轉的 HEIC 照常上傳，由後端轉成 JPEG。
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
