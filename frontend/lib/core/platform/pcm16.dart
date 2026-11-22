import 'dart:typed_data';

/// 把 16 位元 little-endian PCM 轉成 -1 到 1 的浮點數，給 Web Audio 播放。
///
/// 一則訊息的長度是奇數時，最後一個 byte 留到下一則再接上。
class Pcm16Decoder {
  int? _carry;

  Float32List decode(Uint8List bytes) {
    final Uint8List data;
    if (_carry != null) {
      data = Uint8List(bytes.length + 1)
        ..[0] = _carry!
        ..setRange(1, bytes.length + 1, bytes);
      _carry = null;
    } else {
      data = bytes;
    }
    final count = data.length >> 1;
    if (data.length.isOdd) _carry = data[data.length - 1];
    final view = ByteData.sublistView(data);
    final samples = Float32List(count);
    for (var i = 0; i < count; i++) {
      samples[i] = view.getInt16(i * 2, Endian.little) / 32768;
    }
    return samples;
  }

  /// 丟掉留著的半個樣本。停播並清空時呼叫。
  void reset() => _carry = null;
}
