import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class PickedImage {
  const PickedImage({required this.name, required this.bytes});

  final String name;
  final Uint8List bytes;
}

abstract interface class ImagePicker {
  Future<List<PickedImage>?> pickImages();
}

class FilePickerImagePicker implements ImagePicker {
  /// [filePicker] 給測試換成 fake；沒給就用 `FilePicker.platform`。
  FilePickerImagePicker({FilePicker? filePicker}) : _filePicker = filePicker;

  final FilePicker? _filePicker;

  @override
  Future<List<PickedImage>?> pickImages() async {
    final result = await (_filePicker ?? FilePicker.platform).pickFiles(
      type: FileType.custom,
      // 不列 HEIC：讓 iPhone Safari 有機會在上傳前自動轉成 JPEG。實測仍會交出 HEIC，
      // 所以 HEIC 照常上傳，由後端轉成 JPEG（2026-11-24 永傑決定）
      allowedExtensions: ['jpg', 'jpeg', 'png'],
      allowMultiple: true,
      withData: true,
    );
    if (result == null) return null;
    return result.files.map((file) {
      final bytes = file.bytes;
      if (bytes == null) throw StateError('無法讀取圖片：${file.name}');
      return PickedImage(name: file.name, bytes: bytes);
    }).toList();
  }
}

final imagePickerProvider = Provider<ImagePicker>(
  (ref) => FilePickerImagePicker(),
);
