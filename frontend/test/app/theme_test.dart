// 主題規格：現代簡約＋北歐白橡木（見 MR 說明的色票）。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/app_colors.dart';
import 'package:tabletop_hub/app/theme/app_spacing.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/widgets/pill_badge.dart';

import '../support/fakes.dart';

/// WCAG 對比值：(較亮 + 0.05) / (較暗 + 0.05)。
double contrast(Color a, Color b) {
  final la = a.computeLuminance();
  final lb = b.computeLuminance();
  final (hi, lo) = la > lb ? (la, lb) : (lb, la);
  return (hi + 0.05) / (lo + 0.05);
}

void main() {
  final theme = buildAppTheme(const FakeAppFonts());
  final scheme = theme.colorScheme;

  group('色票套用', () {
    test('主色、背景、卡片、文字色等於規格色碼', () {
      expect(AppColors.background, const Color(0xFFFAF7F2));
      expect(AppColors.surface, const Color(0xFFFFFFFF));
      expect(AppColors.primary, const Color(0xFFD9531E));
      expect(AppColors.sage, const Color(0xFF486458));
      expect(AppColors.amber, const Color(0xFFD97706));
      expect(AppColors.ink, const Color(0xFF27221E));
      expect(AppColors.inkMuted, const Color(0xFF6B635B));

      expect(scheme.primary, AppColors.primary);
      expect(scheme.onPrimary, Colors.white);
      expect(scheme.secondary, AppColors.sage);
      expect(scheme.tertiary, AppColors.amber);
      expect(scheme.surface, AppColors.surface);
      expect(scheme.onSurface, AppColors.ink);
      expect(scheme.onSurfaceVariant, AppColors.inkMuted);
      expect(theme.scaffoldBackgroundColor, AppColors.background);
      expect(theme.canvasColor, AppColors.background);
      expect(theme.cardTheme.color, AppColors.surface);
    });
  });

  group('文字對比 ≥ 4.5:1（WCAG AA）', () {
    final pairs = <String, (Color, Color)>{
      '主標題／背景': (AppColors.ink, AppColors.background),
      '副標／背景': (AppColors.inkMuted, AppColors.background),
      '副標／卡片': (AppColors.inkMuted, AppColors.surface),
      '文字按鈕／卡片': (AppColors.primaryText, AppColors.surface),
      '文字按鈕／背景': (AppColors.primaryText, AppColors.background),
      '一般標籤': (AppColors.inkMuted, AppColors.neutralTint),
      '人數標籤': (AppColors.sage, AppColors.sageTint),
      '時間標籤': (AppColors.amberText, AppColors.amberTint),
      '重點標籤': (AppColors.primaryText, AppColors.primaryTint),
    };
    for (final MapEntry(key: name, value: (fg, bg)) in pairs.entries) {
      test(name, () => expect(contrast(fg, bg), greaterThanOrEqualTo(4.5)));
    }

    test('主色按鈕（白字／焦糖橘）達到 UI 元件的 3:1', () {
      expect(
        contrast(Colors.white, AppColors.primary),
        greaterThanOrEqualTo(3),
      );
    });
  });

  group('觸控大小與圓角', () {
    Size? minSize(ButtonStyle? style) => style?.minimumSize?.resolve({});
    OutlinedBorder? shape(ButtonStyle? style) => style?.shape?.resolve({});

    test('按鈕高度 ≥ 48，圓角 12', () {
      for (final style in [
        theme.filledButtonTheme.style,
        theme.elevatedButtonTheme.style,
        theme.outlinedButtonTheme.style,
        theme.textButtonTheme.style,
      ]) {
        expect(minSize(style)!.height, greaterThanOrEqualTo(48));
        expect(
          shape(style),
          RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.button),
          ),
        );
      }
      expect(AppSizes.minTouchTarget, greaterThanOrEqualTo(44));
    });

    test('卡片圓角 16，帶淺色邊框', () {
      final shape = theme.cardTheme.shape! as RoundedRectangleBorder;
      expect(AppRadius.card, 16);
      expect(shape.borderRadius, BorderRadius.circular(16));
      expect(shape.side.color, AppColors.border);
    });

    test('Chip 是膠囊形', () {
      expect(theme.chipTheme.shape, isA<StadiumBorder>());
    });

    test('主色按鈕：焦糖橘底、白字', () {
      final style = theme.filledButtonTheme.style!;
      expect(style.backgroundColor!.resolve({}), AppColors.primary);
      expect(style.foregroundColor!.resolve({}), Colors.white);
    });
  });

  group('字型', () {
    test('標題用標題字型，內文用內文字型', () {
      final t = theme.textTheme;
      for (final style in [
        t.displayLarge,
        t.headlineMedium,
        t.headlineSmall,
        t.titleLarge,
      ]) {
        expect(style!.fontFamily, FakeAppFonts.headingFamily);
      }
      for (final style in [
        t.titleMedium,
        t.bodyLarge,
        t.bodyMedium,
        t.labelLarge,
      ]) {
        expect(style!.fontFamily, FakeAppFonts.bodyFamily);
      }
      expect(t.bodyMedium!.color, AppColors.ink);
      expect(theme.appBarTheme.titleTextStyle!.fontFamily, FakeAppFonts.headingFamily);
    });
  });

  group('膠囊標籤', () {
    for (final (tone, bg, fg) in [
      (PillTone.neutral, AppColors.neutralTint, AppColors.inkMuted),
      (PillTone.players, AppColors.sageTint, AppColors.sage),
      (PillTone.duration, AppColors.amberTint, AppColors.amberText),
      (PillTone.accent, AppColors.primaryTint, AppColors.primaryText),
    ]) {
      testWidgets('${tone.name}：套用主題中的顏色', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: theme,
            home: Scaffold(body: PillBadge(label: '4 人', tone: tone)),
          ),
        );
        final box = tester.widget<DecoratedBox>(
          find.descendant(
            of: find.byType(PillBadge),
            matching: find.byType(DecoratedBox),
          ),
        );
        final decoration = box.decoration as BoxDecoration;
        expect(decoration.color, bg);
        expect(decoration.borderRadius, BorderRadius.circular(AppRadius.pill));
        final text = tester.widget<Text>(find.text('4 人'));
        expect(text.style?.color, fg);
      });
    }

    testWidgets('有圖示時顯示圖示', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: theme,
          home: const Scaffold(
            body: PillBadge(
              label: '60 分鐘',
              tone: PillTone.duration,
              icon: Icons.schedule,
            ),
          ),
        ),
      );
      expect(find.byIcon(Icons.schedule), findsOneWidget);
    });
  });
}
