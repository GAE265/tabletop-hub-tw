import 'package:flutter/material.dart';

import '../../core/layout/breakpoints.dart';
import 'app_colors.dart';

/// 間距與版面寬度只能定義在 `app/theme/`。
abstract final class AppSpacing {
  static const double xSmall = 4;
  static const double small = 8;
  static const double medium = 16;
  static const double large = 24;
  static const double xLarge = 32;

  /// 內容區最大寬度：手機佔滿，平板與桌機各自限制寬度。
  static double? contentMaxWidth(ScreenSize size) => switch (size) {
    ScreenSize.mobile => null,
    ScreenSize.tablet => 560,
    ScreenSize.desktop => 720,
  };

  /// 左右並排版面（例如月曆＋當日列表）的最大寬度。
  static const double splitContentMaxWidth = 1120;
}

/// 圓角。
abstract final class AppRadius {
  /// 卡片、對話框。
  static const double card = 16;

  /// 按鈕、輸入框、SnackBar。
  static const double button = 12;

  /// 膠囊標籤：夠大就會變成兩端全圓。
  static const double pill = 999;

  /// 座位圖上的桌子與圖例色塊。
  static const double seatTable = 6;
}

/// 尺寸。
abstract final class AppSizes {
  /// 單手好按的最小觸控高度（規格要求 44 以上，取 Material 建議的 48）。
  static const double minTouchTarget = 48;

  /// 底部導覽列高度。
  static const double navigationBarHeight = 72;

  /// 空畫面的大圖示（之後有插圖時換成圖片，尺寸沿用）。
  static const double emptyStateIcon = 96;

  /// 頭像（例如推薦 Agent 的圖示）。
  static const double avatar = 40;

  /// 品牌標誌的方塊（導覽列與首頁頂部）。
  static const double brandMark = 36;

  /// 首頁入口卡片的圖示方塊。
  static const double entryIconBox = 48;

  /// 首頁入口卡片的最小寬度：放不下四張時改成兩欄。
  static const double entryCardMinWidth = 220;

  /// 首頁行程列的日期徽章。
  static const double dateBadge = 52;

  /// 戰績「記錄回合」的回合編號欄位寬度。
  static const double turnNumberFieldWidth = 120;

  /// 座位圖的最大高度：桌子配置依寬度放大，但不會超過這個高度。
  static const double seatingPlanHeight = 420;

  /// 座位圖相鄰桌子之間的空隙（每張桌四周各留這麼多，以座標的像素計）。
  static const double seatGap = 3;

  /// 座位圖桌子的外框粗細。
  static const double seatTableBorder = 2;

  /// 座位圖圖例的色塊。
  static const double legendSwatch = 16;

  /// 通知列表中，未讀通知右側的圓點。
  static const double unreadDot = 10;

  /// 列表捲到距離底部這麼近時，載入下一頁。
  static const double loadMoreThreshold = 200;
}

/// 暖色柔和懸浮陰影。
abstract final class AppShadows {
  /// 卡片等浮在背景上的容器。
  static List<BoxShadow> get card => [
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.08),
      blurRadius: 24,
      offset: const Offset(0, 8),
    ),
  ];

  /// 底部導覽列等更靠近使用者的元件。
  static List<BoxShadow> get floating => [
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.12),
      blurRadius: 32,
      offset: const Offset(0, 12),
    ),
  ];
}
