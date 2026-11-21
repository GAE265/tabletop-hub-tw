// 播音前把 16 位元 PCM 轉成浮點數（host spec §12.2、§14.1）。
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/platform/pcm16.dart';

void main() {
  test('little-endian 16 位元轉成 -1 到 1', () {
    final decoder = Pcm16Decoder();
    final samples = decoder.decode(
      Uint8List.fromList([0x00, 0x80, 0x00, 0x00, 0xff, 0x7f]),
    );
    expect(samples, hasLength(3));
    expect(samples[0], -1.0);
    expect(samples[1], 0.0);
    expect(samples[2], closeTo(32767 / 32768, 1e-6));
  });

  test('奇數長度：最後一個 byte 留到下一段再接上', () {
    final decoder = Pcm16Decoder();
    expect(decoder.decode(Uint8List.fromList([0x00])), isEmpty);
    final samples = decoder.decode(Uint8List.fromList([0x40, 0x00, 0xc0]));
    expect(samples, hasLength(2));
    expect(samples[0], 0.5);
    expect(samples[1], closeTo(-0.5, 1e-6));
  });

  test('reset：丟掉留著的半個樣本（停播時用）', () {
    final decoder = Pcm16Decoder();
    decoder.decode(Uint8List.fromList([0x12]));
    decoder.reset();
    final samples = decoder.decode(Uint8List.fromList([0x00, 0x40]));
    expect(samples.single, 0.5);
  });
}
