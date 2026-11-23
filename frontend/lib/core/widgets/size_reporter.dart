import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';

/// 量出 [child] 的高度，變了就呼叫 [onHeight]（排版完成後才呼叫，避免在排版途中改狀態）。
///
/// 用在浮在內容上的輸入區：頁面依它的高度在捲動內容最下面留出空間。
class SizeReporter extends SingleChildRenderObjectWidget {
  const SizeReporter({required this.onHeight, required super.child, super.key});

  final ValueChanged<double> onHeight;

  @override
  RenderObject createRenderObject(BuildContext context) =>
      RenderSizeReporter(onHeight);

  @override
  void updateRenderObject(
    BuildContext context,
    RenderSizeReporter renderObject,
  ) {
    renderObject.onHeight = onHeight;
  }
}

class RenderSizeReporter extends RenderProxyBox {
  RenderSizeReporter(this.onHeight);

  ValueChanged<double> onHeight;
  double? _last;

  @override
  void performLayout() {
    super.performLayout();
    final height = size.height;
    if (height == _last) return;
    _last = height;
    WidgetsBinding.instance.addPostFrameCallback((_) => onHeight(height));
  }
}
