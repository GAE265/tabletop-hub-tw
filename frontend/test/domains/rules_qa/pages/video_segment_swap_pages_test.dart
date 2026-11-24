// 草稿頁的「每段的素材」與換素材（2026-11-25 永傑決定，最小版）；
// 素材清單把沒有段在用的素材另外列出、寫明不用拍。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';

import '../video_swap_support.dart';
import 'video_pages_support.dart';

/// 收集這次畫面的所有錯誤（例如 RenderFlex overflowed）。
List<String> takeErrors(WidgetTester tester) {
  final errors = <String>[];
  for (var e = tester.takeException(); e != null; e = tester.takeException()) {
    errors.add('$e'.split('\n').first);
  }
  return errors;
}

void main() {
  group('草稿頁：每段的素材', () {
    testWidgets('每段列出格子用了哪個素材（中文名稱）', (tester) async {
      await pumpVideo(tester, location: '/videos/p1/draft', repo: swapRepo());
      expect(
        find.byKey(const Key('video-draft-segment-assets')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('video-segment-s1-sidebar')), findsOneWidget);
      expect(find.text('側欄：圖板'), findsOneWidget);
      expect(find.text('主畫面：紅牌'), findsOneWidget);
      expect(find.text('主畫面：紅牌、牌背、藍牌'), findsOneWidget);
    });

    testWidgets('放好幾張牌的格子：寫明不支援、沒有換素材按鈕', (tester) async {
      await pumpVideo(tester, location: '/videos/p1/draft', repo: swapRepo());
      expect(
        find.byKey(const Key('video-segment-s1-main-unsupported')),
        findsOneWidget,
      );
      expect(find.text('這一段目前不支援換素材'), findsOneWidget);
      expect(find.byKey(const Key('video-segment-s1-main-swap')), findsNothing);
      expect(
        find.byKey(const Key('video-segment-s1-sidebar-swap')),
        findsOneWidget,
      );
    });

    testWidgets('按換素材：只列出可以換的素材', (tester) async {
      await pumpVideo(tester, location: '/videos/p1/draft', repo: swapRepo());
      await tapKey(tester, 'video-segment-s1-sidebar-swap');
      for (final key in ['back', 'red', 'blue']) {
        expect(find.byKey(Key('video-swap-option-$key')), findsOneWidget);
      }
      for (final key in ['board', 'dice', 'coin']) {
        expect(find.byKey(Key('video-swap-option-$key')), findsNothing);
      }
    });

    testWidgets('選了之後換掉，顯示移除了什麼，格子改成新素材', (tester) async {
      final repo = swapRepo()..swapResult = sidebarSwapResult;
      await pumpVideo(tester, location: '/videos/p1/draft', repo: repo);
      await tapKey(tester, 'video-segment-s1-sidebar-swap');
      await tapKey(tester, 'video-swap-option-blue');
      expect(repo.swaps.single.$3.assetKey, 'blue');
      expect(find.byKey(const Key('video-swap-notice')), findsOneWidget);
      expect(find.textContaining('已移除：框線 1 個、動作 1 個'), findsOneWidget);
      expect(find.text('側欄：藍牌'), findsOneWidget);
    });

    testWidgets('版本衝突：顯示後端的說明', (tester) async {
      final repo = swapRepo()
        ..swapError = const ApiException(
          code: 'RULES_VIDEO_CONFLICT',
          message: '草稿已被修改，請重新整理後再換',
          statusCode: 409,
        );
      await pumpVideo(tester, location: '/videos/p1/draft', repo: repo);
      await tapKey(tester, 'video-segment-s1-sidebar-swap');
      await tapKey(tester, 'video-swap-option-blue');
      expect(find.byKey(const Key('video-swap-error')), findsOneWidget);
      expect(find.text('草稿已被修改，請重新整理後再換'), findsOneWidget);
    });

    testWidgets('手機寬 320：不超出', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: swapRepo(),
        size: const Size(320, 900),
      );
      expect(takeErrors(tester), isEmpty);
    });
  });

  group('素材清單：沒有段在用的素材', () {
    testWidgets('另外列出，寫明不用拍', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/assets',
        repo: swapRepo(draft: swapDraft(boardUsed: const [])),
      );
      expect(
        find.byKey(const Key('video-assets-unused-header')),
        findsOneWidget,
      );
      expect(find.textContaining('目前沒有段用到，不用拍'), findsWidgets);
    });

    testWidgets('都有段在用：沒有這一區', (tester) async {
      final draft = swapDraft();
      final repo = swapRepo(
        draft: draft.copyWith(
          assets: [
            for (final a in draft.assets)
              if (a.assetKey != 'dice') a,
          ],
        ),
      );
      await pumpVideo(tester, location: '/videos/p1/assets', repo: repo);
      expect(find.byKey(const Key('video-assets-unused-header')), findsNothing);
    });
  });
}
