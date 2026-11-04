import 'package:flutter/widgets.dart';

/// RWD 斷點的唯一定義處（AGENTS.md 5.3）。各頁面不得自訂斷點。
enum ScreenSize { mobile, tablet, desktop }

const double mobileMaxWidth = 600;
const double tabletMaxWidth = 1024;

/// 寬度 < 600 為手機、< 1024 為平板，其餘為桌機。
ScreenSize screenSizeForWidth(double width) {
  if (width < mobileMaxWidth) return ScreenSize.mobile;
  if (width < tabletMaxWidth) return ScreenSize.tablet;
  return ScreenSize.desktop;
}

extension ScreenSizeContext on BuildContext {
  ScreenSize get screenSize =>
      screenSizeForWidth(MediaQuery.sizeOf(this).width);
}
