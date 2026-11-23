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
  static const double xxLarge = 48;

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

  /// 首頁的大標題卡片。
  static const double hero = 24;

  /// 按鈕、輸入框、SnackBar。
  static const double button = 12;

  /// 膠囊標籤：夠大就會變成兩端全圓。
  static const double pill = 999;

  /// 座位圖上的桌子與圖例色塊。
  static const double seatTable = 6;
}

/// 尺寸。
/// 動畫時間。
abstract final class AppDurations {
  /// 按下有厚度的按鈕時往下沉的時間。
  static const press = Duration(milliseconds: 80);
}

abstract final class AppSizes {
  /// 單手好按的最小觸控高度（規格要求 44 以上，取 Material 建議的 48）。
  static const double minTouchTarget = 48;

  /// 底部導覽列高度。
  static const double navigationBarHeight = 72;

  /// 空畫面的大圖示（之後有插圖時換成圖片，尺寸沿用）。
  static const double emptyStateIcon = 96;

  /// 頭像（例如推薦 Agent 的圖示）。
  static const double avatar = 40;

  /// 品牌 logo 的高度：平板與桌機的頂部導覽列。
  static const double logoHeight = 44;

  /// 品牌 logo 的高度：手機頂部列（較高，logo 裡的英文小字才看得清楚）。
  static const double logoHeightMobile = 60;

  /// 頂部列的圓形按鈕（鈴鐺、登入）。
  static const double roundButton = 44;

  /// 小按鈕（頂部列的圓形按鈕）的厚度，比卡片薄。
  static const double smallThickness = 2;

  /// 首頁入口卡片的圖示方塊。
  static const double entryIconBox = 48;

  /// 首頁入口卡片的最小寬度：放不下四張時改成兩欄。
  static const double entryCardMinWidth = 220;

  /// 首頁行程列的日期徽章。
  static const double dateBadge = 52;

  /// 跟著文字的小圖示（日期、人數、箭頭）。
  static const double inlineIcon = 18;

  /// 捲動區上下邊緣淡出的高度（內容捲到邊緣時慢慢消失，不會被硬切）。
  static const double scrollFade = 24;

  /// 首頁卡片底部較粗的邊（卡片的厚度）。
  static const double cardThickness = 4;

  /// 按下有厚度的按鈕時，剩下的底邊厚度（其餘的變成往下沉的距離）。
  static const double pressedThickness = 1;

  /// 行程卡片的虛線：每一段的長度與間隔。
  static const double dashLength = 6;
  static const double dashGap = 4;

  /// 區塊標題左邊的小圓點。
  static const double sectionDot = 8;

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

  /// 規則書匯入：選好的圖片縮圖（直式，接近書頁比例）。
  static const double pageThumbWidth = 48;
  static const double pageThumbHeight = 64;

  /// 規則影片標區域：角的把手看得到的大小，與可點範圍（至少 44，2026-11-21 永傑決定）。
  static const double regionHandle = 24;
  static const double regionHandleHitArea = 44;

  /// 規則影片標區域：框線粗細。
  static const double regionBorder = 2;
}

/// 暖色柔和陰影，分四層（Stitch 設計系統）。
abstract final class AppShadows {
  /// 第 1 層：卡片等浮在背景上的容器。
  static List<BoxShadow> get card => [
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.06),
      blurRadius: 8,
      spreadRadius: -1,
      offset: const Offset(0, 2),
    ),
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.04),
      blurRadius: 3,
      spreadRadius: -1,
      offset: const Offset(0, 1),
    ),
  ];

  /// 第 2 層：滑過或按住可以點的卡片。
  static List<BoxShadow> get hover => [
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.10),
      blurRadius: 20,
      spreadRadius: -3,
      offset: const Offset(0, 8),
    ),
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.06),
      blurRadius: 6,
      spreadRadius: -2,
      offset: const Offset(0, 3),
    ),
  ];

  /// 首頁有厚度的卡片與按鈕：比 [hover] 深、擴散得更開，像放在木桌上的木牌。
  static List<BoxShadow> get raised => [
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.30),
      blurRadius: 32,
      spreadRadius: 2,
      offset: const Offset(0, 14),
    ),
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.16),
      blurRadius: 10,
      offset: const Offset(0, 4),
    ),
  ];

  /// 第 3 層：底部導覽列等固定在畫面上的列。
  static List<BoxShadow> get floating => [
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.08),
      blurRadius: 12,
      offset: const Offset(0, -2),
    ),
  ];

  /// 小按鈕（頂部列的圓形按鈕）的淡陰影：只貼在按鈕下方。
  static List<BoxShadow> get soft => [
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.12),
      blurRadius: 6,
      offset: const Offset(0, 2),
    ),
  ];

  /// 第 4 層：對話框、底部面板。
  static List<BoxShadow> get modal => [
    BoxShadow(
      color: AppColors.shadow.withValues(alpha: 0.18),
      blurRadius: 36,
      spreadRadius: -4,
      offset: const Offset(0, 16),
    ),
  ];
}
