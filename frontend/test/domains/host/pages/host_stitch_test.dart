// 語音主持正式頁面的 Stitch 版面：木紋背景、厚卡片與厚按鈕、頁首的遊戲與狀態、
// 自動接話時的「正在聽」大圓、按住說話的橘色大圓、可以這樣說的小卡、底部提示。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/shell.dart';
import 'package:tabletop_hub/app/theme/app_colors.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';
import 'package:tabletop_hub/domains/host/data/host_models.dart';
import 'package:tabletop_hub/domains/host/data/host_stream.dart';

import '../../../support/fakes.dart';
import '../support.dart';
import 'host_page_test.dart' show HostPageHarness;

void expectThick(WidgetTester tester, Finder box, [String? reason]) {
  final decoration =
      tester.widget<DecoratedBox>(box).decoration as BoxDecoration;
  final border = decoration.border! as Border;
  expect(border.bottom.width, greaterThan(border.top.width), reason: reason);
  expect(decoration.boxShadow, isNotEmpty, reason: reason);
}

Finder firstBoxIn(String key) => find
    .descendant(of: find.byKey(Key(key)), matching: find.byType(DecoratedBox))
    .first;

Finder boxAround(String key) => find
    .ancestor(of: find.byKey(Key(key)), matching: find.byType(DecoratedBox))
    .first;

Finder inKey(String key, Finder finder) =>
    find.descendant(of: find.byKey(Key(key)), matching: finder);

void main() {
  group('開主持前', () {
    testWidgets('木紋背景；人數、接話方式、聲線是厚卡片，「開始主持」是厚按鈕', (tester) async {
      final h = HostPageHarness();
      await h.pump(tester, size: const Size(390, 1600));
      expect(
        find.descendant(
          of: find.byKey(const Key('host-page')),
          matching: find.byType(WoodBackground),
        ),
        findsOneWidget,
      );
      for (final key in [
        'host-section-player-count',
        'host-section-setup-mode',
        'host-section-setup-voice',
      ]) {
        expectThick(tester, firstBoxIn(key), key);
      }
      expectThick(tester, boxAround('host-start'));
    });

    testWidgets('有保留的主持：「接著主持」「重新開始」是厚按鈕', (tester) async {
      final h = HostPageHarness(
        sessions: [
          fakeHostingSession(
            step: HostStep.turn,
            turnNumber: 2,
            phaseNumber: 2,
          ),
        ],
      );
      await h.pump(tester);
      expectThick(tester, boxAround('host-resume'));
      expectThick(tester, boxAround('host-restart'));
    });
  });

  group('主持中', () {
    testWidgets('頁首卡：遊戲名稱與狀態「聆聽中」；暫停中、查規則中跟著變', (tester) async {
      final h = HostPageHarness();
      await h.pump(tester);
      await h.start(tester);
      expectThick(tester, firstBoxIn('host-header'));
      expect(inKey('host-header', find.text('血與刃的白薔薇')), findsOneWidget);
      expect(inKey('host-status', find.text('聆聽中')), findsOneWidget);

      await h.emit(
        tester,
        HostStateMessage(
          liveState(paused: true, pauseReason: HostPauseReason.command),
        ),
      );
      expect(inKey('host-status', find.text('暫停中')), findsOneWidget);

      await h.emit(tester, HostStateMessage(liveState(lookingUp: true)));
      expect(inKey('host-status', find.text('查規則中')), findsOneWidget);
    });

    testWidgets('自動接話：顯示「正在聽」大圓，不能按；沒有按住說話鍵', (tester) async {
      final h = HostPageHarness();
      await h.pump(tester);
      await h.start(tester);
      expect(find.byKey(const Key('host-listening')), findsOneWidget);
      expect(inKey('host-listening', find.text('直接說話，主持人會回答')), findsOneWidget);
      expect(inKey('host-listening', find.byType(InkWell)), findsNothing);
      expect(find.byKey(const Key('host-talk')), findsNothing);
    });

    testWidgets('按住說話：橘色大圓；按著時寫「放開後主持人回答」', (tester) async {
      final h = HostPageHarness();
      await h.pump(tester);
      await tester.tap(find.text('按住說話'));
      await tester.pump();
      await h.start(
        tester,
        live: liveState(turnTakingMode: TurnTakingMode.pushToTalk),
      );
      expect(find.byKey(const Key('host-listening')), findsNothing);
      final circle =
          tester
                  .widget<Container>(find.byKey(const Key('host-talk')))
                  .decoration
              as BoxDecoration;
      expect(circle.color, AppColors.primary);
      expect(circle.shape, BoxShape.circle);
    });

    testWidgets('目前進度與接話方式是厚卡片；流程鍵是厚按鈕', (tester) async {
      final h = HostPageHarness();
      await h.pump(tester);
      await h.start(tester, live: liveState(turnNumber: 2, phaseNumber: 2));
      expectThick(tester, firstBoxIn('host-section-progress'));
      expectThick(tester, firstBoxIn('host-section-mode'));
      for (final key in ['host-previous', 'host-pause', 'host-next']) {
        expectThick(tester, boxAround(key), key);
      }
    });

    testWidgets('可以這樣說：每一句一張小卡', (tester) async {
      final h = HostPageHarness();
      await h.pump(tester);
      await h.start(tester);
      expect(
        find.descendant(
          of: find.byKey(const Key('host-voice-hints')),
          matching: find.byWidgetPredicate(
            (w) =>
                w.key is ValueKey<String> &&
                (w.key! as ValueKey<String>).value.startsWith('host-hint-'),
          ),
        ),
        findsNWidgets(8),
      );
    });

    testWidgets('主持中要求藏起手機底部導覽列（流程鍵固定在底部，避免誤按）；開主持前不藏', (tester) async {
      final h = HostPageHarness();
      await h.pump(tester);
      final container = ProviderScope.containerOf(
        tester.element(find.byKey(const Key('host-page'))),
      );
      expect(container.read(hideBottomNavigationProvider), isFalse);
      await h.start(tester);
      expect(container.read(hideBottomNavigationProvider), isTrue);
    });

    testWidgets('底部有一句小提醒：問規則直接說', (tester) async {
      final h = HostPageHarness();
      await h.pump(tester);
      await h.start(tester);
      expect(find.byKey(const Key('host-tip')), findsOneWidget);
    });
  });
}
