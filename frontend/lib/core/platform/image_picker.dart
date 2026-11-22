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
  @override
  Future<List<PickedImage>?> pickImages() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      // HEIC 也讓店員選得到，選到時由畫面說明要改成 JPEG（不支援 HEIC）
      allowedExtensions: ['jpg', 'jpeg', 'png', 'heic', 'heif'],
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
