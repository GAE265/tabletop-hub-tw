import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

/// 字型的來源。包成介面是為了讓測試換成 `FakeAppFonts`，不連網路下載字型。
abstract interface class AppFonts {
  /// 標題（display、headline、titleLarge、AppBar 標題）。
  TextStyle heading(TextStyle style);

  /// 內文、按鈕、標籤。
  TextStyle body(TextStyle style);
}

/// 執行時從 Google Fonts 下載：標題用 Epilogue，內文用 Plus Jakarta Sans。
///
/// 中文不在這裡載入：Flutter Web 會自動補上 Noto Sans TC（只下載用到的字），
/// 手機則使用系統內建的中文字型，避免一次下載好幾 MB 的完整字型檔。
class GoogleAppFonts implements AppFonts {
  const GoogleAppFonts();

  @override
  TextStyle heading(TextStyle style) => GoogleFonts.epilogue(textStyle: style);

  @override
  TextStyle body(TextStyle style) =>
      GoogleFonts.plusJakartaSans(textStyle: style);
}

final appFontsProvider = Provider<AppFonts>((ref) => const GoogleAppFonts());
