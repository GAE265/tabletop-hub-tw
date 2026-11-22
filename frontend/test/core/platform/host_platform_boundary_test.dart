// 只能在網頁上用的程式包在 core/platform/ 後面（AGENTS.md §5.3、host spec §14.1）。
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

Iterable<File> _dartFiles(String path) => Directory(path)
    .listSync(recursive: true)
    .whereType<File>()
    .where((file) => file.path.endsWith('.dart'));

void main() {
  test('domains/host 不直接 import 瀏覽器的 API', () {
    final forbidden = RegExp(
      r'''import\s+['"](dart:(html|js|js_util|js_interop|js_interop_unsafe|web_audio)|package:web/)''',
    );
    final offenders = [
      for (final file in _dartFiles('lib/domains/host'))
        if (forbidden.hasMatch(file.readAsStringSync())) file.path,
    ];
    expect(Directory('lib/domains/host').existsSync(), isTrue);
    expect(offenders, isEmpty);
  });

  test('前端沒有阿里雲的設定與金鑰', () {
    final aliyun = RegExp(
      r'dashscope|aliyun|alibabacloud|DASHSCOPE|ALIYUN|sk-[A-Za-z0-9]{16,}',
    );
    final offenders = [
      for (final file in _dartFiles('lib'))
        if (aliyun.hasMatch(file.readAsStringSync())) file.path,
    ];
    expect(offenders, isEmpty);
  });

  test('四個介面各有網頁實作，domains/host 透過 provider 取得', () {
    final web = File('lib/core/platform/browser_media_web.dart');
    expect(web.existsSync(), isTrue);
    final source = web.readAsStringSync();
    for (final name in [
      'implements AudioCapture',
      'implements AudioPlayback',
      'implements ScreenWakeLock',
      'implements PageVisibility',
    ]) {
      expect(source, contains(name));
    }
  });
}
