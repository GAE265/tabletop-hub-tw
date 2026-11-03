import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('lib/ 內沒有任何寫死的 UUID（測試帳號 UUID 只在後端）', () {
    final uuid = RegExp(
      r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',
    );
    final hits = <String>[];
    for (final file in Directory(
      'lib',
    ).listSync(recursive: true).whereType<File>()) {
      if (!file.path.endsWith('.dart')) continue;
      if (uuid.hasMatch(file.readAsStringSync())) hits.add(file.path);
    }
    expect(hits, isEmpty);
  });
}
