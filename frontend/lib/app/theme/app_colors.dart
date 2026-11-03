import 'package:flutter/material.dart';

/// 顏色只能定義在 `app/theme/`，頁面不得寫死色碼（AGENTS.md 5.4）。
abstract final class AppColors {
  static const seed = Color(0xFF2E7D6B);
  static const success = Color(0xFF2E7D32);
  static const warning = Color(0xFFB26A00);
}
