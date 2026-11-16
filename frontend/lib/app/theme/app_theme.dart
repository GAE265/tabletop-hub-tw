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
    fontSize: 16,
    fontWeight: FontWeight.w600,
  );

  final primaryButton = ButtonStyle(
    backgroundColor: WidgetStateProperty.resolveWith(
      (states) => states.contains(WidgetState.disabled)
          ? AppColors.neutralTint
          : AppColors.primary,
    ),
    foregroundColor: WidgetStateProperty.resolveWith(
      (states) => states.contains(WidgetState.disabled)
          ? AppColors.inkMuted
          : Colors.white,
    ),
    overlayColor: WidgetStatePropertyAll(
      AppColors.primaryBright.withValues(alpha: 0.24),
    ),
    elevation: const WidgetStatePropertyAll(0),
    minimumSize: const WidgetStatePropertyAll(buttonMinSize),
    padding: const WidgetStatePropertyAll(buttonPadding),
    shape: WidgetStatePropertyAll(buttonShape),
    textStyle: WidgetStatePropertyAll(buttonText),
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
      style: ButtonStyle(
        foregroundColor: const WidgetStatePropertyAll(AppColors.primaryText),
        side: const WidgetStatePropertyAll(
          BorderSide(color: AppColors.primary, width: 1.5),
        ),
        minimumSize: const WidgetStatePropertyAll(buttonMinSize),
        padding: const WidgetStatePropertyAll(buttonPadding),
        shape: WidgetStatePropertyAll(buttonShape),
        textStyle: WidgetStatePropertyAll(buttonText),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: ButtonStyle(
        foregroundColor: const WidgetStatePropertyAll(AppColors.primaryText),
        minimumSize: const WidgetStatePropertyAll(buttonMinSize),
        padding: const WidgetStatePropertyAll(
          EdgeInsets.symmetric(horizontal: AppSpacing.medium),
        ),
        shape: WidgetStatePropertyAll(buttonShape),
        textStyle: WidgetStatePropertyAll(buttonText),
      ),
    ),
    iconButtonTheme: const IconButtonThemeData(
      style: ButtonStyle(
        foregroundColor: WidgetStatePropertyAll(AppColors.ink),
        minimumSize: WidgetStatePropertyAll(
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
      fillColor: AppColors.surface,
      contentPadding: const EdgeInsets.all(AppSpacing.medium),
      border: input,
      enabledBorder: input,
      focusedBorder: input.copyWith(
        borderSide: const BorderSide(color: AppColors.primary, width: 2),
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
          foreground: AppColors.inkMuted,
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
          horizontal: AppSpacing.small + AppSpacing.xSmall,
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
  final base = typography.englishLike.merge(typography.black).apply(
    bodyColor: AppColors.ink,
    displayColor: AppColors.ink,
  );
  TextStyle h(TextStyle? s, FontWeight w) =>
      fonts.heading(s!.copyWith(fontWeight: w));
  TextStyle b(TextStyle? s) => fonts.body(s!);
  return base.copyWith(
    displayLarge: h(base.displayLarge, FontWeight.w700),
    displayMedium: h(base.displayMedium, FontWeight.w700),
    displaySmall: h(base.displaySmall, FontWeight.w700),
    headlineLarge: h(base.headlineLarge, FontWeight.w700),
    headlineMedium: h(base.headlineMedium, FontWeight.w700),
    headlineSmall: h(base.headlineSmall, FontWeight.w700),
    titleLarge: h(base.titleLarge, FontWeight.w700),
    titleMedium: b(base.titleMedium!.copyWith(fontWeight: FontWeight.w600)),
    titleSmall: b(base.titleSmall!.copyWith(fontWeight: FontWeight.w600)),
    bodyLarge: b(base.bodyLarge),
    bodyMedium: b(base.bodyMedium),
    bodySmall: b(base.bodySmall!.copyWith(color: AppColors.inkMuted)),
    labelLarge: b(base.labelLarge),
    labelMedium: b(base.labelMedium),
    labelSmall: b(base.labelSmall),
  );
}
