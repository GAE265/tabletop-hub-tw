// 標區域頁在手機上：區域多（7 個）、說明長時，上方面板不能把照片擠到看不見，畫面也不能超出
// （2026-11-24 iPhone 實測：面板佔滿整個畫面、超出 51 像素，照片沒有出現）。
// 這頁不能整頁捲動（拖框的手勢會被捲動搶走），所以區域按鈕改成橫向一排、可以左右滑動，說明最多兩行。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/fakes.dart';
import '../video_assets_support.dart';
import 'video_pages_support.dart';

const regionNames = ['主圖版', '死亡區', '獵殺區', '獻祭區', '玩家人數', '白薔薇區', '水晶放置處'];

FakeVideoStudioRepository manyRegionsRepo() => assetsRepo(
  asset:
      sampleAsset(
        hasPhoto: true,
        regions: {for (final name in regionNames) name: null},
      ).copyWith(
        regionHints: {
          for (final name in regionNames)
            name: '對照規則書第 2 頁的圖，框出整個$name。如果照片裡的$name被手或其他配件擋住，請先重拍再框。',
        },
        regionSegments: {
          for (final name in regionNames) name: [1, 3, 5],
        },
      ),
  photo: pngBytes,
);

/// 收集這次畫面的所有錯誤（例如 RenderFlex overflowed）。
List<String> takeErrors(WidgetTester tester) {
  final errors = <String>[];
  for (var e = tester.takeException(); e != null; e = tester.takeException()) {
    errors.add('$e'.split('\n').first);
  }
  return errors;
}

double editorHeight(WidgetTester tester) =>
    tester.getSize(find.byKey(const Key('video-region-editor'))).height;

void main() {
  // 手機扣掉瀏覽器網址列、App 頁首與底部導覽列後，這頁大約剩 520 的高度
  for (final width in [320.0, 360.0, 390.0, 430.0]) {
    testWidgets('手機寬 $width、高 520：沒有超出，照片至少有 120 高', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board/regions',
        repo: manyRegionsRepo(),
        size: Size(width, 520),
      );
      expect(takeErrors(tester), isEmpty);
      expect(editorHeight(tester), greaterThanOrEqualTo(120));
    });
  }

  testWidgets('區域按鈕排成一排，可以左右滑動到最後一個', (tester) async {
    await pumpVideo(
      tester,
      location: '/videos/p1/assets/board/regions',
      repo: manyRegionsRepo(),
      size: const Size(360, 520),
    );
    final first = find.byKey(const Key('video-region-chip-主圖版'));
    final last = find.byKey(const Key('video-region-chip-水晶放置處'));
    expect(tester.getTopLeft(first).dy, tester.getTopLeft(last).dy);
    final row = find.byKey(const Key('video-region-chips'));
    expect(
      find.descendant(of: row, matching: find.byType(Scrollable)),
      findsOneWidget,
    );
    await tester.dragUntilVisible(last, row, const Offset(-200, 0));
    await tester.pumpAndSettle();
    await tester.tap(last);
    await tester.pumpAndSettle();
    expect(find.textContaining('框出整個水晶放置處'), findsOneWidget);
  });

  testWidgets('說明最多兩行，超過的用「…」', (tester) async {
    await pumpVideo(
      tester,
      location: '/videos/p1/assets/board/regions',
      repo: manyRegionsRepo(),
      size: const Size(320, 520),
    );
    final hint = tester.widget<Text>(
      find.byKey(const Key('video-region-hint')),
    );
    expect(hint.maxLines, 2);
    expect(hint.overflow, TextOverflow.ellipsis);
  });

  testWidgets('字放大（1.3 倍）：沒有超出，照片仍然看得到', (tester) async {
    await pumpVideo(
      tester,
      location: '/videos/p1/assets/board/regions',
      repo: manyRegionsRepo(),
      size: const Size(390, 640),
    );
    tester.platformDispatcher.textScaleFactorTestValue = 1.3;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpAndSettle();
    expect(takeErrors(tester), isEmpty);
    expect(editorHeight(tester), greaterThanOrEqualTo(100));
  });
}
