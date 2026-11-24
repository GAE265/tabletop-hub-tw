// 首頁入口卡片在各種手機寬度都不能超出（開發版會出現黃黑條紋，正式版內容被切掉）；
// 同一排的兩張卡片一樣高。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support.dart';

/// 收集這次畫面的所有錯誤（例如 RenderFlex overflowed）。
List<String> takeErrors(WidgetTester tester) {
  final errors = <String>[];
  for (var e = tester.takeException(); e != null; e = tester.takeException()) {
    errors.add('$e'.split('\n').first);
  }
  return errors;
}

double heightOf(WidgetTester tester, String key) =>
    tester.getSize(find.byKey(Key(key))).height;

void main() {
  for (final width in [320.0, 360.0, 390.0, 430.0]) {
    testWidgets('手機寬 $width：入口卡片沒有超出，同一排的兩張一樣高', (tester) async {
      await pumpHome(tester, size: Size(width, 900));
      expect(takeErrors(tester), isEmpty);
      expect(
        heightOf(tester, 'home-card-advisor'),
        heightOf(tester, 'home-card-groups'),
      );
      expect(
        heightOf(tester, 'home-card-booking'),
        heightOf(tester, 'home-card-rules'),
      );
    });
  }

  testWidgets('字放大（1.3 倍）：入口卡片沒有超出，卡片跟著變高', (tester) async {
    await pumpHome(tester, size: const Size(390, 1400));
    final before = heightOf(tester, 'home-card-groups');
    tester.platformDispatcher.textScaleFactorTestValue = 1.3;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpAndSettle();
    expect(takeErrors(tester), isEmpty);
    expect(heightOf(tester, 'home-card-groups'), greaterThan(before));
    expect(
      heightOf(tester, 'home-card-advisor'),
      heightOf(tester, 'home-card-groups'),
    );
  });
}
