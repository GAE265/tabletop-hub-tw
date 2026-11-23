import 'package:flutter/material.dart';

import 'app_colors.dart';

/// 木紋背景：圖片重複鋪滿，載入前先顯示木紋的平均色。
///
/// 木紋顏色較深，放在上面的文字一律要包在卡片或白底條裡，
/// 不直接壓在木紋上。
class WoodBackground extends StatelessWidget {
  const WoodBackground({required this.child, super.key});

  /// 木紋圖的路徑（`pubspec.yaml` 的 assets）。
  static const asset = 'assets/images/wood.webp';

  /// 木紋圖一格在畫面上的大小（邏輯像素）。
  static const tileSize = 512.0;

  final Widget child;

  /// 上層已經畫了木紋（例如手機的畫面框架），頁面就不用再畫一次。
  static bool isPaintedAbove(BuildContext context) =>
      context.findAncestorWidgetOfExactType<WoodBackground>() != null;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppColors.woodFallback,
        image: DecorationImage(
          image: AssetImage(asset),
          repeat: ImageRepeat.repeat,
          alignment: Alignment.topLeft,
          // 原圖 1024，縮成 512 一格
          scale: 1024 / tileSize,
        ),
      ),
      child: child,
    );
  }
}
