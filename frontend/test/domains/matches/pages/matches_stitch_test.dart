// 戰績頁與一局詳情的 Stitch 版面：木紋背景、有厚度的卡片與按鈕、日期快選、
// 最近的局的結果摘要、一局的回合數與人數、複製編號、參加者一列、退出、回合小卡。
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';
import 'package:tabletop_hub/domains/matches/state/white_rose.dart';

import '../../../support/fakes.dart';
import 'support.dart';

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

void main() {
  group('戰績頁', () {
    testWidgets('木紋背景；頁首、用編號打開、開局表單都是有厚度的卡片', (tester) async {
      await pumpMatches(tester, '/matches');
      expect(
        find.descendant(
          of: find.byKey(const Key('matches-page')),
          matching: find.byType(WoodBackground),
        ),
        findsOneWidget,
      );
      expect(inKey('match-header', find.text('對局戰績')), findsOneWidget);
      for (final key in [
        'match-header',
        'match-open-card',
        'match-form-card',
      ]) {
        expectThick(tester, firstBoxIn(key), key);
      }
    });

    testWidgets('「打開」與「立即開局」是有厚度的按鈕', (tester) async {
      await pumpMatches(tester, '/matches');
      for (final key in ['match-open', 'match-create']) {
        expectThick(tester, boxAround(key), key);
      }
      expect(inKey('match-create', find.text('立即開局')), findsOneWidget);
    });

    testWidgets('日期快選「昨天」：開局的日期是昨天', (tester) async {
      final repo = await pumpMatches(tester, '/matches');
      await choose(tester, 'match-game', '阿不思學院');
      await tapKey(tester, 'match-date-yesterday');
      await tapKey(tester, 'match-create');
      final yesterday = DateTime.now().subtract(const Duration(days: 1));
      final played = repo.createCalls.single.playedOn;
      expect(
        (played.year, played.month, played.day),
        (yesterday.year, yesterday.month, yesterday.day),
      );
    });

    testWidgets('最近的局：標題條寫「最近 N 局」；每一局一張有厚度的卡片', (tester) async {
      await pumpMatches(tester, '/matches');
      final header = find.byKey(const Key('match-list-header'));
      await tester.ensureVisible(header);
      expect(
        find.descendant(of: header, matching: find.text('最近 1 局')),
        findsOneWidget,
      );
      expectThick(tester, firstBoxIn('match-item-m-1'));
    });

    testWidgets('陣營勝負的局：顯示獲勝陣營與我的陣營', (tester) async {
      final repo = FakeMatchesRepository()
        ..listItems = [
          fakeMatch(
            status: 'finished',
            result: const {'type': 'faction', 'winning_faction': 'rose'},
            participants: [
              fakeMatchParticipant(faction: 'rose', isWinner: true),
              fakeMatchParticipant(
                id: 'p-2',
                seatNumber: 2,
                userId: 'u-b',
                displayName: '玩家乙',
                faction: 'blood_blade',
                isWinner: false,
              ),
            ],
          ),
        ];
      await pumpMatches(tester, '/matches', repo: repo);
      final item = find.byKey(const Key('match-item-m-1'));
      await tester.ensureVisible(item);
      for (final text in [
        '${factionLabel('rose')}獲勝',
        '我的陣營：${factionLabel('rose')}',
      ]) {
        expect(
          find.descendant(of: item, matching: find.text(text)),
          findsOneWidget,
          reason: text,
        );
      }
    });

    testWidgets('有分數與名次的局：顯示獲勝者與分數、我的名次與分數', (tester) async {
      final repo = FakeMatchesRepository()
        ..listItems = [
          fakeMatch(
            status: 'finished',
            participants: [
              fakeMatchParticipant().copyWith(
                score: 98,
                placement: 2,
                isWinner: false,
              ),
              fakeMatchParticipant(
                id: 'p-2',
                seatNumber: 2,
                userId: 'u-b',
                displayName: '玩家乙',
              ).copyWith(score: 112, placement: 1, isWinner: true),
            ],
          ),
        ];
      await pumpMatches(tester, '/matches', repo: repo);
      final item = find.byKey(const Key('match-item-m-1'));
      await tester.ensureVisible(item);
      for (final text in ['獲勝：玩家乙（112 分）', '我排名第 2（98 分）']) {
        expect(
          find.descendant(of: item, matching: find.text(text)),
          findsOneWidget,
          reason: text,
        );
      }
    });

    testWidgets('還沒有結果的局：不顯示結果摘要', (tester) async {
      await pumpMatches(tester, '/matches');
      final item = find.byKey(const Key('match-item-m-1'));
      await tester.ensureVisible(item);
      expect(
        find.descendant(of: item, matching: find.textContaining('獲勝')),
        findsNothing,
      );
    });
  });

  group('一局詳情', () {
    const detail = '/matches/m-1';

    testWidgets('木紋背景；資訊卡有厚度，標出第幾回合與幾人對局', (tester) async {
      await pumpMatches(
        tester,
        detail,
        repo: FakeMatchesRepository(
          match: fakeMatch(
            turns: [fakeMatchTurn(turnNumber: 1), fakeMatchTurn(turnNumber: 2)],
          ),
        ),
      );
      expect(
        find.descendant(
          of: find.byKey(const Key('match-detail-page')),
          matching: find.byType(WoodBackground),
        ),
        findsOneWidget,
      );
      expectThick(tester, firstBoxIn('match-info'));
      for (final text in ['第 2 回合', '3 人對局', '編號 m-1']) {
        expect(
          inKey('match-info', find.text(text)),
          findsOneWidget,
          reason: text,
        );
      }
    });

    testWidgets('還沒有回合：不顯示第幾回合', (tester) async {
      await pumpMatches(tester, detail);
      expect(inKey('match-info', find.textContaining('回合')), findsNothing);
    });

    testWidgets('複製編號：把局的編號放進剪貼簿，並提示已複製', (tester) async {
      String? copied;
      final messenger = tester.binding.defaultBinaryMessenger;
      messenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
        if (call.method == 'Clipboard.setData') {
          copied = (call.arguments as Map)['text'] as String?;
        }
        return null;
      });
      addTearDown(
        () => messenger.setMockMethodCallHandler(SystemChannels.platform, null),
      );
      await pumpMatches(tester, detail);
      await tapKey(tester, 'match-copy-id');
      expect(copied, 'm-1');
      expect(find.text('已複製局的編號'), findsOneWidget);
    });

    testWidgets('參加者一列：有沒有帳號的標籤、確認狀態；有分數時顯示分數與獲勝', (tester) async {
      await pumpMatches(
        tester,
        detail,
        repo: FakeMatchesRepository(
          match: fakeMatch(
            participants: [
              fakeMatchParticipant().copyWith(score: 15, isWinner: true),
              fakeMatchParticipant(
                id: 'p-2',
                seatNumber: 2,
                userId: 'u-b',
                displayName: '玩家乙',
              ),
              fakeMatchParticipant(
                id: 'p-3',
                seatNumber: 3,
                userId: null,
                displayName: 'Amy',
              ),
            ],
          ),
        ),
      );
      for (final (key, text) in [
        ('participant-p-1', '15 分'),
        ('participant-p-1', '獲勝'),
        ('participant-p-1', '有帳號'),
        ('participant-p-2', '尚未確認'),
        ('participant-p-3', '沒有帳號'),
      ]) {
        expect(
          inKey(key, find.text(text)),
          findsOneWidget,
          reason: '$key $text',
        );
      }
      // 沒有帳號的人不用確認
      expect(inKey('participant-p-3', find.text('尚未確認')), findsNothing);
    });

    testWidgets('進行中的參加者：有「退出這一局」按鈕，按下先確認才送出', (tester) async {
      final repo = await pumpMatches(tester, detail);
      expectThick(tester, boxAround('leave'));
      await tapKey(tester, 'leave');
      expect(find.text('要退出這一局（座位 1）嗎？'), findsOneWidget);
      await tapKey(tester, 'remove-cancel');
      expect(repo.removeCalls, isEmpty);
      await tapKey(tester, 'leave');
      await tapKey(tester, 'remove-confirm');
      expect(repo.removeCalls, ['p-1']);
    });

    testWidgets('不是參加者：沒有「退出這一局」', (tester) async {
      await pumpMatches(tester, detail, userId: 'u-other');
      expect(find.byKey(const Key('leave')), findsNothing);
    });

    testWidgets('回合紀錄：每回合一張小卡，出牌數量與白薔薇用膠囊顯示（0 的不顯示）', (tester) async {
      await pumpMatches(
        tester,
        detail,
        repo: FakeMatchesRepository(
          match: fakeMatch(
            turns: [
              fakeMatchTurn(
                gameData: const {
                  'played_seat_numbers': [1, 2],
                  'double_blade_count': 2,
                  'dark_blade_count': 0,
                  'giant_blade_count': 1,
                  'faithful_count': 0,
                  'has_white_rose': true,
                },
              ),
            ],
          ),
        ),
      );
      final turn = find.byKey(const Key('turn-1'));
      await tester.ensureVisible(turn);
      for (final text in ['雙刃 2', '巨刃 1', '白薔薇']) {
        expect(
          find.descendant(of: turn, matching: find.text(text)),
          findsOneWidget,
          reason: text,
        );
      }
      for (final text in ['暗刃 0', '信者 0']) {
        expect(
          find.descendant(of: turn, matching: find.text(text)),
          findsNothing,
          reason: text,
        );
      }
    });

    testWidgets('記錄回合、記錄結果、確認紀錄都是有厚度的按鈕', (tester) async {
      await pumpMatches(tester, detail);
      for (final key in ['turn-submit', 'result-submit', 'add-named']) {
        await tester.ensureVisible(find.byKey(Key(key)));
        expectThick(tester, boxAround(key), key);
      }
      await pumpMatches(
        tester,
        detail,
        repo: FakeMatchesRepository(
          match: fakeMatch(
            status: 'finished',
            result: const {'type': 'faction', 'winning_faction': 'rose'},
          ),
        ),
      );
      await tester.ensureVisible(find.byKey(const Key('confirm')));
      expectThick(tester, boxAround('confirm'));
    });
  });
}
