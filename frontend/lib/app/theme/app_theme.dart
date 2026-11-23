import 'package:flutter/material.dart';

import '../../core/widgets/pill_badge.dart';
import 'app_colors.dart';
import 'app_fonts.dart';
import 'app_spacing.dart';

/// 全站主題：現代簡約＋北歐白橡木。正式頁面一律從這裡取樣式，不寫死數值。
ThemeData buildAppTheme(AppFonts fonts) {
  final scheme = ColorScheme.fromSeed(seedColor: AppColors.primary).copyWith(
    primary: AppColors.primary,
    onPrimary: Colors.white,
    primaryContainer: AppColors.primaryTint,
    onPrimaryContainer: AppColors.primaryText,
    secondary: AppColors.sage,
    onSecondary: Colors.white,
    secondaryContainer: AppColors.sageTint,
    onSecondaryContainer: AppColors.sage,
    tertiary: AppColors.amber,
    onTertiary: Colors.white,
    tertiaryContainer: AppColors.amberTint,
    onTertiaryContainer: AppColors.amberText,
    error: AppColors.error,
    surface: AppColors.surface,
    onSurface: AppColors.ink,
    onSurfaceVariant: AppColors.inkMuted,
    surfaceContainerLowest: AppColors.surface,
    surfaceContainerLow: AppColors.background,
    surfaceContainer: AppColors.backgroundAlt,
    surfaceContainerHigh: AppColors.neutralTint,
    surfaceContainerHighest: AppColors.neutralTint,
    outline: AppColors.border,
    outlineVariant: AppColors.border,
    shadow: AppColors.shadow,
    surfaceTint: Colors.transparent,
  );

  final textTheme = _textTheme(fonts);
  final buttonShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(AppRadius.button),
  );
  const buttonMinSize = Size(64, AppSizes.minTouchTarget);
  const buttonPadding = EdgeInsets.symmetric(horizontal: AppSpacing.large);
  final buttonText = textTheme.labelLarge!.copyWith(
    fontSize: 15,
    fontWeight: FontWeight.w600,
  );

  final primaryButton = ButtonStyle(
    backgroundColor: WidgetStateProperty.resolveWith(
      (states) => states.contains(WidgetState.disabled)
          ? AppColors.neutralTint
          // 按下時變深
          : states.contains(WidgetState.pressed)
          ? AppColors.primaryText
          : AppColors.primary,
    ),
    foregroundColor: WidgetStateProperty.resolveWith(
      (states) => states.contains(WidgetState.disabled)
          ? AppColors.inkMuted
          : Colors.white,
    ),
    overlayColor: WidgetStatePropertyAll(
      AppColors.primaryBright.withValues(alpha: 0.12),
    ),
    elevation: const WidgetStatePropertyAll(0),
    minimumSize: const WidgetStatePropertyAll(buttonMinSize),
    padding: const WidgetStatePropertyAll(buttonPadding),
    shape: WidgetStatePropertyAll(buttonShape),
    textStyle: WidgetStatePropertyAll(buttonText),
  );

  // 停用時一律改成暖灰，看得出來不能按
  WidgetStateProperty<Color> enabledOr(Color color) =>
      WidgetStateProperty.resolveWith(
        (states) =>
            states.contains(WidgetState.disabled) ? AppColors.inkMuted : color,
      );

  final input = OutlineInputBorder(
    borderRadius: BorderRadius.circular(AppRadius.button),
    borderSide: const BorderSide(color: AppColors.border),
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    textTheme: textTheme,
    scaffoldBackgroundColor: AppColors.background,
    canvasColor: AppColors.background,
    dividerTheme: const DividerThemeData(
      color: AppColors.border,
      thickness: 1,
      space: 1,
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: AppColors.background,
      foregroundColor: AppColors.ink,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: textTheme.titleLarge,
    ),
    cardTheme: CardThemeData(
      color: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      shadowColor: AppColors.shadow.withValues(alpha: 0.3),
      elevation: 2,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.card),
        side: const BorderSide(color: AppColors.border),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(style: primaryButton),
    elevatedButtonTheme: ElevatedButtonThemeData(style: primaryButton),
    outlinedButtonTheme: OutlinedButtonThemeData(
      // 次要按鈕：米白底、細邊框、深色字
      style: ButtonStyle(
        backgroundColor: const WidgetStatePropertyAll(AppColors.background),
        foregroundColor: enabledOr(AppColors.ink),
        overlayColor: WidgetStatePropertyAll(
          AppColors.neutralTint.withValues(alpha: 0.8),
        ),
        side: const WidgetStatePropertyAll(BorderSide(color: AppColors.border)),
        minimumSize: const WidgetStatePropertyAll(buttonMinSize),
        padding: const WidgetStatePropertyAll(buttonPadding),
        shape: WidgetStatePropertyAll(buttonShape),
        textStyle: WidgetStatePropertyAll(buttonText),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: ButtonStyle(
        foregroundColor: enabledOr(AppColors.primaryText),
        minimumSize: const WidgetStatePropertyAll(buttonMinSize),
        padding: const WidgetStatePropertyAll(
          EdgeInsets.symmetric(horizontal: AppSpacing.medium),
        ),
        shape: WidgetStatePropertyAll(buttonShape),
        textStyle: WidgetStatePropertyAll(buttonText),
      ),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: ButtonStyle(
        foregroundColor: enabledOr(AppColors.ink),
        minimumSize: const WidgetStatePropertyAll(
          Size.square(AppSizes.minTouchTarget),
        ),
      ),
    ),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      backgroundColor: AppColors.primary,
      foregroundColor: Colors.white,
      elevation: 3,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.card),
      ),
      extendedTextStyle: buttonText,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.backgroundAlt,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.medium,
        vertical: AppSpacing.medium - AppSpacing.xSmall / 2,
      ),
      border: input,
      enabledBorder: input,
      focusedBorder: input.copyWith(
        borderSide: const BorderSide(
          color: AppColors.primaryBright,
          width: 1.5,
        ),
      ),
      errorBorder: input.copyWith(
        borderSide: const BorderSide(color: AppColors.error),
      ),
      labelStyle: textTheme.bodyMedium!.copyWith(color: AppColors.inkMuted),
      hintStyle: textTheme.bodyMedium!.copyWith(color: AppColors.inkMuted),
    ),
    chipTheme: ChipThemeData(
      shape: const StadiumBorder(side: BorderSide(color: AppColors.border)),
      backgroundColor: AppColors.surface,
      selectedColor: AppColors.primaryTint,
      checkmarkColor: AppColors.primaryText,
      labelStyle: textTheme.labelLarge!.copyWith(color: AppColors.ink),
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.small),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: AppSizes.navigationBarHeight,
      backgroundColor: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      indicatorColor: AppColors.primaryTint,
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(
          color: states.contains(WidgetState.selected)
              ? AppColors.primaryText
              : AppColors.inkMuted,
        ),
      ),
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => textTheme.labelMedium!.copyWith(
          color: states.contains(WidgetState.selected)
              ? AppColors.primaryText
              : AppColors.inkMuted,
          fontWeight: states.contains(WidgetState.selected)
              ? FontWeight.w700
              : FontWeight.w500,
        ),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: AppColors.surface,
      barrierColor: AppColors.scrim,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.card),
      ),
      titleTextStyle: textTheme.titleLarge,
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: AppColors.ink,
      contentTextStyle: textTheme.bodyMedium!.copyWith(color: Colors.white),
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.button),
      ),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      modalBarrierColor: AppColors.scrim,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AppRadius.card),
        ),
      ),
    ),
    listTileTheme: const ListTileThemeData(
      iconColor: AppColors.inkMuted,
      minTileHeight: AppSizes.minTouchTarget,
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: AppColors.primary,
    ),
    extensions: [
      PillBadgeTheme(
        neutral: const PillColors(
          background: AppColors.neutralTint,
          foreground: AppColors.ink,
        ),
        players: const PillColors(
          background: AppColors.sageTint,
          foreground: AppColors.sage,
        ),
        duration: const PillColors(
          background: AppColors.amberTint,
          foreground: AppColors.amberText,
        ),
        accent: const PillColors(
          background: AppColors.primaryTint,
          foreground: AppColors.primaryText,
        ),
        radius: AppRadius.pill,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.small + AppSpacing.xSmall / 2,
          vertical: AppSpacing.xSmall,
        ),
        iconGap: AppSpacing.xSmall,
        textStyle: textTheme.labelMedium!.copyWith(fontWeight: FontWeight.w600),
      ),
    ],
  );
}

/// 標題角色用標題字型，其餘用內文字型；文字顏色統一為暖炭褐。
TextTheme _textTheme(AppFonts fonts) {
  // black 只有顏色，englishLike 才有字級大小與行高，兩者合併才是完整的字級
  final typography = Typography.material2021();
  final base = typography.englishLike
      .merge(typography.black)
      .apply(bodyColor: AppColors.ink, displayColor: AppColors.ink);
  // 字級、行高、字距依 Stitch 設計系統（docs/ui/stitch/DESIGN.md）
  TextStyle size(
    TextStyle? s,
    double fontSize,
    double lineHeight,
    FontWeight weight, [
    double letterSpacingEm = 0,
  ]) => s!.copyWith(
    fontSize: fontSize,
    height: lineHeight / fontSize,
    fontWeight: weight,
    letterSpacing: letterSpacingEm * fontSize,
  );
  TextStyle h(
    TextStyle? s,
    double fs,
    double lh,
    FontWeight w, [
    double ls = 0,
  ]) => fonts.heading(size(s, fs, lh, w, ls));
  TextStyle b(
    TextStyle? s,
    double fs,
    double lh,
    FontWeight w, [
    double ls = 0,
  ]) => fonts.body(size(s, fs, lh, w, ls));
  const bold = FontWeight.w700;
  const semi = FontWeight.w600;
  const regular = FontWeight.w400;
  return base.copyWith(
    displayLarge: h(base.displayLarge, 36, 44, bold, -0.02),
    displayMedium: h(base.displayMedium, 32, 40, bold, -0.02),
    displaySmall: h(base.displaySmall, 28, 36, bold, -0.01),
    headlineLarge: h(base.headlineLarge, 28, 36, bold, -0.01),
    headlineMedium: h(base.headlineMedium, 22, 30, bold),
    headlineSmall: h(base.headlineSmall, 20, 28, semi),
    titleLarge: h(base.titleLarge, 22, 30, bold),
    titleMedium: b(base.titleMedium, 16, 24, semi, 0.01),
    titleSmall: b(base.titleSmall, 14, 20, semi, 0.01),
    bodyLarge: b(base.bodyLarge, 16, 24, regular),
    bodyMedium: b(base.bodyMedium, 14, 22, regular, 0.01),
    bodySmall: b(
      base.bodySmall!.copyWith(color: AppColors.inkMuted),
      13,
      18,
      regular,
      0.01,
    ),
    labelLarge: b(base.labelLarge, 14, 20, semi, 0.02),
    labelMedium: b(base.labelMedium, 12, 16, semi, 0.03),
    labelSmall: b(base.labelSmall, 11, 14, FontWeight.w500, 0.04),
  );
}
