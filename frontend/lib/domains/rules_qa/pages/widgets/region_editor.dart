import 'dart:typed_data';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import '../../../../app/theme/app_spacing.dart';

/// 在照片上拖矩形標區域（design.md D14 與外觀決定）。
///
/// 一次只改 [current] 這個區域：在空白處拖出新框、拖四個角微調、拖中間移動。框的座標是
/// 0–1 的比例，以套用方向之後的圖為準。角的把手看得到 [AppSizes.regionHandle]，
/// 可點範圍 [AppSizes.regionHandleHitArea]。
class RegionEditor extends StatefulWidget {
  const RegionEditor({
    required this.photo,
    required this.aspectRatio,
    required this.orientation,
    required this.boxes,
    required this.current,
    required this.onChanged,
    super.key,
  });

  final Uint8List photo;

  /// 套用方向之後的寬高比。
  final double aspectRatio;
  final int orientation;
  final Map<String, Rect?> boxes;
  final String? current;
  final void Function(String name, Rect box) onChanged;

  @override
  State<RegionEditor> createState() => _RegionEditorState();
}

enum _Mode { create, move, corner }

class _RegionEditorState extends State<RegionEditor> {
  Rect? _dragging;
  _Mode? _mode;
  Offset _start = Offset.zero;
  Rect? _origin;

  /// 正在拖的角：0 左上、1 右上、2 左下、3 右下。
  int _corner = 0;

  Rect? get _currentBox =>
      _dragging ??
      (widget.current == null ? null : widget.boxes[widget.current]);

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: widget.aspectRatio,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final size = constraints.biggest;
          return GestureDetector(
            key: const Key('video-region-editor'),
            dragStartBehavior: DragStartBehavior.down,
            onPanStart: (d) => _panStart(d.localPosition, size),
            onPanUpdate: (d) => _panUpdate(d.localPosition, size),
            onPanEnd: (_) => _panEnd(),
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                Positioned.fill(
                  child: RotatedBox(
                    quarterTurns: widget.orientation ~/ 90,
                    child: Image.memory(widget.photo, fit: BoxFit.fill),
                  ),
                ),
                for (final entry in widget.boxes.entries)
                  if (entry.key != widget.current && entry.value != null)
                    _box(context, size, entry.key, entry.value!, active: false),
                if (widget.current != null && _currentBox != null) ...[
                  _box(
                    context,
                    size,
                    widget.current!,
                    _currentBox!,
                    active: true,
                  ),
                  for (final (i, corner) in _corners(_currentBox!).indexed)
                    _handle(context, i, _scale(corner, size)),
                ],
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _box(
    BuildContext context,
    Size size,
    String name,
    Rect box, {
    required bool active,
  }) {
    final scheme = Theme.of(context).colorScheme;
    final color = active ? scheme.primary : scheme.surfaceContainerHighest;
    final rect = Rect.fromLTRB(
      box.left * size.width,
      box.top * size.height,
      box.right * size.width,
      box.bottom * size.height,
    );
    return Positioned.fromRect(
      rect: rect,
      child: IgnorePointer(
        child: DecoratedBox(
          key: Key('video-region-box-$name'),
          decoration: BoxDecoration(
            border: Border.all(color: color, width: AppSizes.regionBorder),
          ),
          child: Align(
            alignment: Alignment.topLeft,
            child: ColoredBox(
              color: color,
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.xSmall,
                ),
                child: Text(
                  name,
                  style: Theme.of(context).textTheme.labelSmall!.copyWith(
                    color: active ? scheme.onPrimary : scheme.onSurface,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _handle(BuildContext context, int index, Offset center) {
    const hit = AppSizes.regionHandleHitArea;
    return Positioned(
      left: center.dx - hit / 2,
      top: center.dy - hit / 2,
      child: IgnorePointer(
        child: SizedBox.square(
          key: Key('video-region-handle-hit-$index'),
          dimension: hit,
          child: Center(
            child: Container(
              key: Key('video-region-handle-$index'),
              width: AppSizes.regionHandle,
              height: AppSizes.regionHandle,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                shape: BoxShape.circle,
                border: Border.all(
                  color: Theme.of(context).colorScheme.primary,
                  width: AppSizes.regionBorder,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  static List<Offset> _corners(Rect box) => [
    box.topLeft,
    box.topRight,
    box.bottomLeft,
    box.bottomRight,
  ];

  static Offset _scale(Offset point, Size size) =>
      Offset(point.dx * size.width, point.dy * size.height);

  static Offset _normalize(Offset point, Size size) => Offset(
    (point.dx / size.width).clamp(0, 1),
    (point.dy / size.height).clamp(0, 1),
  );

  void _panStart(Offset position, Size size) {
    final name = widget.current;
    if (name == null) return;
    final box = widget.boxes[name];
    _start = _normalize(position, size);
    _origin = box;
    if (box != null) {
      for (final (i, corner) in _corners(box).indexed) {
        if ((_scale(corner, size) - position).distance <=
            AppSizes.regionHandleHitArea / 2) {
          _mode = _Mode.corner;
          _corner = i;
          return;
        }
      }
      final onScreen = Rect.fromPoints(
        _scale(box.topLeft, size),
        _scale(box.bottomRight, size),
      );
      if (onScreen.contains(position)) {
        _mode = _Mode.move;
        return;
      }
    }
    _mode = _Mode.create;
  }

  void _panUpdate(Offset position, Size size) {
    final mode = _mode;
    if (mode == null) return;
    final point = _normalize(position, size);
    final origin = _origin;
    setState(() {
      switch (mode) {
        case _Mode.create:
          _dragging = Rect.fromPoints(_start, point);
        case _Mode.move when origin != null:
          final delta = point - _start;
          // 整個框留在照片內
          final dx = delta.dx.clamp(-origin.left, 1 - origin.right);
          final dy = delta.dy.clamp(-origin.top, 1 - origin.bottom);
          _dragging = origin.shift(Offset(dx, dy));
        case _Mode.corner when origin != null:
          // 對角固定，拖的角跟著手指
          final fixed = _corners(origin)[3 - _corner];
          _dragging = Rect.fromPoints(fixed, point);
        default:
          break;
      }
    });
  }

  void _panEnd() {
    final box = _dragging;
    final name = widget.current;
    setState(() {
      _dragging = null;
      _mode = null;
    });
    if (box != null && name != null) widget.onChanged(name, box);
  }
}
