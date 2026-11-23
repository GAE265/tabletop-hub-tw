import 'package:flutter/material.dart';

/// 顏色只能定義在 `app/theme/`，頁面不得寫死色碼（AGENTS.md 5.4）。
///
/// 風格：現代簡約＋北歐白橡木，像溫暖咖啡館裡的桌邊助理。
abstract final class AppColors {
  // 底色與容器
  /// 頁面背景：偏白的淺橡木色。之後換成木紋圖時，這個顏色當作圖片載入前的底色。
  static const background = Color(0xFFFAF7F2);

  /// 次要底色：輸入框、分隔區塊等需要和背景稍微區分的地方。
  static const backgroundAlt = Color(0xFFF8F5F0);

  /// 卡片、對話框、底部導覽列。
  static const surface = Color(0xFFFFFFFF);

  /// 卡片與輸入框的極細暖灰邊框。
  static const border = Color(0xFFEAE3DA);

  /// 懸浮陰影的顏色（實際使用時再加透明度，見 `AppShadows`）。
  static const shadow = Color(0xFF5A3A22);

  // 主色：焦糖深暖橘（CTA、目前選取的項目）
  static const primary = Color(0xFFD9531E);

  /// 較亮的焦糖橘：選取外框、進度條等不放文字的強調處。
  static const primaryBright = Color(0xFFEA580C);

  /// 放在白底上的焦糖橘文字（文字按鈕、連結）。比主色深一點，才能達到 4.5:1。
  static const primaryText = Color(0xFFA63F16);

  /// 焦糖橘的淡底（重點標籤、導覽列選取底色）。
  static const primaryTint = Color(0xFFFBEAE2);

  // 輔助色
  /// 森林鼠尾草綠：新手友善、人數。
  static const sage = Color(0xFF486458);
  static const sageTint = Color(0xFFE6EEE9);

  /// 蜂蜜琥珀黃：進行中、時間。不直接當文字色，文字用 [amberText]。
  static const amber = Color(0xFFD97706);
  static const amberText = Color(0xFF8A4B08);
  static const amberTint = Color(0xFFFDF1DC);

  /// 一般標籤的淡底。
  static const neutralTint = Color(0xFFF1ECE4);

  // 文字
  /// 主標題與內文：暖炭褐。
  static const ink = Color(0xFF27221E);

  /// 副標與說明文字：暖灰。
  static const inkMuted = Color(0xFF6B635B);

  /// 深色卡片（[ink] 底）上的說明文字。
  static const onInkMuted = Color(0xFFD6CBBE);

  // 背景圖
  /// 木紋背景的平均色：木紋圖載入前先顯示這個顏色。
  static const woodFallback = Color(0xFFC07D3B);

  /// 卡片的邊（底部較粗，看起來有厚度）。
  static const cardEdge = Color(0xFFE2D5C5);

  /// 深色卡片的邊。
  static const inkEdge = Color(0xFF110E0C);

  /// 白底條（頁首、區塊標題）：放在木紋上的半透明白。
  static const surfaceGlass = Color(0xEBFFFFFF);

  /// 手機頂部列：放在木紋上的半透明暖米色。
  static const headerGlass = Color(0xF2F6EEE7);

  /// 手機底部導覽列：浮在木紋上的半透明米白膠囊。
  static const navGlass = Color(0xF5FBF8F4);

  /// 對話框、底部面板後面的遮罩：暖炭色 45%。
  static const scrim = Color(0x7327221E);

  // 狀態
  static const success = sage;
  static const warning = amberText;
  static const error = Color(0xFFB3261E);

  /// 危險操作（退出、取消揪團）那一列的淡紅底。
  static const errorTint = Color(0xFFFDF0EE);

  /// 危險操作那一列的邊。
  static const errorEdge = Color(0xFFEECDC8);

  /// 紅色按鈕的底邊（比 [error] 深）。
  static const errorDark = Color(0xFF8C1C16);
}
