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
    });

    // 完整版：放好幾張牌的格子逐張列出，可以換正面；有牌背的也可以換牌背
    testWidgets('放好幾張牌的格子：逐張列出，可以換正面或牌背', (tester) async {
      await pumpVideo(tester, location: '/videos/p1/draft', repo: swapRepo());
      expect(find.text('第 1 張：紅牌（牌背：牌背）'), findsOneWidget);
      expect(find.text('第 3 張：紅牌'), findsOneWidget);
      for (final item in ['c1', 'c2', 'c3']) {
        expect(
          find.byKey(Key('video-segment-s1-main-$item-front')),
          findsOneWidget,
        );
      }
      expect(
        find.byKey(const Key('video-segment-s1-main-c1-back')),
        findsOneWidget,
      );
      // c3 沒有牌背
      expect(
        find.byKey(const Key('video-segment-s1-main-c3-back')),
        findsNothing,
      );
      expect(find.text('這一段目前不支援換素材'), findsNothing);
    });

    testWidgets('換牌背：送出哪一張與牌背', (tester) async {
      final repo = swapRepo();
      await pumpVideo(tester, location: '/videos/p1/draft', repo: repo);
      await tapKey(tester, 'video-segment-s1-main-c1-back');
      // 目前的牌背、繪製、已略過的不列
      expect(find.byKey(const Key('video-swap-option-back')), findsNothing);
      await tapKey(tester, 'video-swap-option-blue');
      final input = repo.swaps.single.$3;
      expect((input.slot, input.itemKey, input.face), ('main', 'c1', 'back'));
      expect(input.assetKey, 'blue');
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

    testWidgets('選了之後換掉，顯示要重標的區域，格子改成新素材', (tester) async {
      final repo = swapRepo()..swapResult = sidebarSwapResult;
      await pumpVideo(tester, location: '/videos/p1/draft', repo: repo);
      await tapKey(tester, 'video-segment-s1-sidebar-swap');
      await tapKey(tester, 'video-swap-option-blue');
      expect(repo.swaps.single.$3.assetKey, 'blue');
      expect(find.byKey(const Key('video-swap-notice')), findsOneWidget);
      expect(find.textContaining('要在新照片上標出：甲區、乙區'), findsOneWidget);
      expect(find.text('側欄：藍牌'), findsOneWidget);
    });

    testWidgets('換完提醒影片要重新產生，按鈕直接前往產生影片', (tester) async {
      final repo = swapRepo()..swapResult = sidebarSwapResult;
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: repo,
      );
      expect(find.byKey(const Key('video-swap-go-render')), findsNothing);
      await tapKey(tester, 'video-segment-s1-sidebar-swap');
      await tapKey(tester, 'video-swap-option-blue');
      expect(find.text('影片要重新產生才會用新的素材'), findsOneWidget);
      await tapKey(tester, 'video-swap-go-render');
      expect(h.path, '/videos/p1/render');
    });

    testWidgets('換素材失敗：不顯示前往產生影片', (tester) async {
      final repo = swapRepo()
        ..swapError = const ApiException(
          code: 'RULES_VIDEO_CONFLICT',
          message: '草稿已被修改，請重新整理後再換',
          statusCode: 409,
        );
      await pumpVideo(tester, location: '/videos/p1/draft', repo: repo);
      await tapKey(tester, 'video-segment-s1-sidebar-swap');
      await tapKey(tester, 'video-swap-option-blue');
      expect(find.byKey(const Key('video-swap-go-render')), findsNothing);
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

    testWidgets('新增素材：填名稱後建立並直接換上', (tester) async {
      final repo = swapRepo();
      await pumpVideo(tester, location: '/videos/p1/draft', repo: repo);
      await tapKey(tester, 'video-segment-s2-main-swap');
      await tapKey(tester, 'video-swap-new');
      await tester.enterText(
        find.byKey(const Key('video-new-asset-label')),
        '白薔薇',
      );
      await tester.enterText(
        find.byKey(const Key('video-new-asset-shot')),
        '整張牌正面朝上',
      );
      await tapKey(tester, 'video-new-asset-submit');
      expect(repo.createdAssets.single.$2.label, '白薔薇');
      expect(repo.swaps.single.$3.assetKey, 'custom_1');
      expect(find.textContaining('已換成「白薔薇」'), findsOneWidget);
    });

    testWidgets('新增素材：名稱空白時不能送出', (tester) async {
      final repo = swapRepo();
      await pumpVideo(tester, location: '/videos/p1/draft', repo: repo);
      await tapKey(tester, 'video-segment-s2-main-swap');
      await tapKey(tester, 'video-swap-new');
      await tester.enterText(
        find.byKey(const Key('video-new-asset-label')),
        '   ',
      );
      await tester.pump();
      final submit = tester.widget<FilledButton>(
        find.byKey(const Key('video-new-asset-submit')),
      );
      expect(submit.onPressed, isNull);
      expect(repo.createdAssets, isEmpty);
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
