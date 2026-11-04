import '../../core/layout/breakpoints.dart';

/// 間距與版面寬度只能定義在 `app/theme/`。
abstract final class AppSpacing {
  static const double small = 8;
  static const double medium = 16;
  static const double large = 24;

  /// 內容區最大寬度：手機佔滿，平板與桌機各自限制寬度。
  static double? contentMaxWidth(ScreenSize size) => switch (size) {
    ScreenSize.mobile => null,
    ScreenSize.tablet => 560,
    ScreenSize.desktop => 720,
  };
}
