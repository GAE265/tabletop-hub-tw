// 首頁（spec：home-page）。資料規則由 upcoming_state_test 涵蓋，這裡確認畫面與導頁。
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';

import '../../domains/groups/support.dart';
import '../../support/fakes.dart';
import 'support.dart';

const cards = {
  'home-card-advisor': ('今天玩什麼？', '跟助理聊聊，幫你挑遊戲', '/games-advisor'),
  'home-card-groups': ('找人一起玩', '開團或加入，額滿可候補', '/groups'),
  'home-card-booking': ('訂個位子', '挑桌遊店，直接選座位', '/booking'),
  'home-card-rules': ('這遊戲怎麼玩', '看教學、隨時問規則', '/rules'),
};

Future<void> tapKey(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  await tester.ensureVisible(target);
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Offset topLeftOf(WidgetTester tester, String key) =>
    tester.getTopLeft(find.byKey(Key(key)));

void main() {
  testWidgets('開啟首頁：品牌、登入、主標、副標、四張入口卡片與行程區', (tester) async {
    await pumpHome(tester);
    expect(find.text('遊任有娛'), findsOneWidget);
    expect(find.byKey(const Key('home-login')), findsOneWidget);
    expect(find.text('今天想怎麼玩？'), findsOneWidget);
    expect(find.text('找遊戲、揪人、訂位、學規則，一個地方搞定。'), findsOneWidget);
    for (final MapEntry(key: key, value: (title, body, _)) in cards.entries) {
      final card = find.byKey(Key(key));
      expect(card, findsOneWidget);
      expect(
        find.descendant(of: card, matching: find.text(title)),
        findsOneWidget,
      );
      expect(
        find.descendant(of: card, matching: find.text(body)),
        findsOneWidget,
      );
    }
    expect(find.text('接下來的行程'), findsOneWidget);
  });

  for (final user in <DevUser>[homePlayer, homeStaff, homeAdmin]) {
    testWidgets('${user.role}：看到相同的首頁內容', (tester) async {
      final bookings = FakeBookingRepository();
      if (user.role == 'shop_staff') bookings.mineError = forbidden;
      await pumpHome(tester, user: user, bookings: bookings);
      expect(find.text('今天想怎麼玩？'), findsOneWidget);
      for (final key in cards.keys) {
        expect(find.byKey(Key(key)), findsOneWidget);
      }
      expect(find.text('接下來的行程'), findsOneWidget);
      expect(find.byKey(const Key('home-upcoming-error')), findsNothing);
    });
  }

  for (final MapEntry(key: key, value: (title, _, path)) in cards.entries) {
    testWidgets('點「$title」前往 $path', (tester) async {
      await pumpHome(tester);
      await tapKey(tester, key);
      expect(find.text('到了 $path'), findsOneWidget);
    });
  }

  testWidgets('登入尚未開放：提示「登入功能即將推出」，停留在首頁', (tester) async {
    await pumpHome(tester);
    await tapKey(tester, 'home-login');
    expect(find.text('登入功能即將推出'), findsOneWidget);
    expect(find.text('今天想怎麼玩？'), findsOneWidget);
  });

  testWidgets('手機：入口卡片排成兩欄兩列', (tester) async {
    await pumpHome(tester, size: const Size(400, 900));
    final advisor = topLeftOf(tester, 'home-card-advisor');
    final groups = topLeftOf(tester, 'home-card-groups');
    final booking = topLeftOf(tester, 'home-card-booking');
    final rules = topLeftOf(tester, 'home-card-rules');
    expect(groups.dy, advisor.dy);
    expect(groups.dx, greaterThan(advisor.dx));
    expect(booking.dy, greaterThan(advisor.dy));
    expect(booking.dx, advisor.dx);
    expect(rules.dy, booking.dy);
  });

  testWidgets('桌機：四張入口卡片在同一列', (tester) async {
    await pumpHome(tester, size: const Size(1280, 900));
    final ys = {for (final key in cards.keys) topLeftOf(tester, key).dy};
    expect(ys, hasLength(1));
  });

  group('接下來的行程', () {
    testWidgets('有訂位也有揪團：依時間各一列，顯示日期、標題、說明與狀態', (tester) async {
      final bookings = FakeBookingRepository(
        mine: [homeBooking(id: 1, startAt: taipei(11, 21, 19), shopId: 's-b')],
      );
      final groups = FakeGroupsRepository(
        groups: [
          fakeGroup(
            title: '阿瓦隆之夜',
            startAt: taipei(11, 22, 19),
            capacity: 7,
            memberCount: 5,
            myStatus: 'member',
          ),
        ],
      );
      await pumpHome(tester, bookings: bookings, groups: groups);

      final first = find.byKey(const Key('home-upcoming-0'));
      final second = find.byKey(const Key('home-upcoming-1'));
      Finder inRow(Finder row, String text) =>
          find.descendant(of: row, matching: find.text(text));
      expect(inRow(first, '訂位・19:00・4 人'), findsOneWidget);
      expect(inRow(first, '乙店・桌號 T1、T2'), findsOneWidget);
      expect(inRow(first, '已確認'), findsOneWidget);
      expect(inRow(first, '21'), findsOneWidget);
      expect(inRow(second, '揪團・阿瓦隆之夜'), findsOneWidget);
      expect(inRow(second, '已報名 5 / 7 人'), findsOneWidget);
      expect(inRow(second, '招募中'), findsOneWidget);
      expect(inRow(second, '22'), findsOneWidget);
      expect(find.byKey(const Key('home-upcoming-2')), findsNothing);
    });

    testWidgets('候補中與已額滿的狀態文字', (tester) async {
      final groups = FakeGroupsRepository(
        groups: [
          fakeGroup(
            id: 'g-wait',
            startAt: taipei(11, 21),
            capacity: 4,
            memberCount: 4,
            myStatus: 'waitlisted',
          ),
          fakeGroup(
            id: 'g-full',
            startAt: taipei(11, 22),
            capacity: 4,
            memberCount: 4,
            myStatus: 'member',
          ),
        ],
      );
      await pumpHome(tester, groups: groups);
      expect(
        find.descendant(
          of: find.byKey(const Key('home-upcoming-0')),
          matching: find.text('候補中'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: find.byKey(const Key('home-upcoming-1')),
          matching: find.text('已額滿'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('點訂位列前往我的訂位', (tester) async {
      await pumpHome(
        tester,
        bookings: FakeBookingRepository(
          mine: [homeBooking(id: 1, startAt: taipei(11, 21))],
        ),
      );
      await tapKey(tester, 'home-upcoming-0');
      expect(find.text('到了 /booking/mine'), findsOneWidget);
    });

    testWidgets('點揪團列前往該揪團的詳細頁', (tester) async {
      await pumpHome(
        tester,
        groups: FakeGroupsRepository(
          groups: [fakeGroup(startAt: taipei(11, 21), myStatus: 'member')],
        ),
      );
      await tapKey(tester, 'home-upcoming-0');
      expect(find.text('到了 /groups/g-1'), findsOneWidget);
    });

    testWidgets('載入中：行程區顯示載入指示，入口卡片照常顯示', (tester) async {
      final bookings = FakeBookingRepository()..mineGate = Completer<void>();
      await pumpHome(tester, bookings: bookings, settle: false);
      await tester.pump();
      expect(find.byKey(const Key('home-upcoming-loading')), findsOneWidget);
      expect(find.byKey(const Key('home-card-advisor')), findsOneWidget);
      bookings.mineGate!.complete();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('home-upcoming-loading')), findsNothing);
    });

    testWidgets('沒有行程：顯示空狀態與兩個按鈕', (tester) async {
      await pumpHome(tester);
      expect(find.byKey(const Key('home-upcoming-empty')), findsOneWidget);
      await tapKey(tester, 'home-empty-groups');
      expect(find.text('到了 /groups'), findsOneWidget);
    });

    testWidgets('沒有行程：「訂個位子」按鈕前往訂位', (tester) async {
      await pumpHome(tester);
      await tapKey(tester, 'home-empty-booking');
      expect(find.text('到了 /booking'), findsOneWidget);
    });

    testWidgets('載入失敗：顯示錯誤與「重試」，入口卡片可點；重試成功後顯示行程', (tester) async {
      final bookings = FakeBookingRepository(
        mine: [homeBooking(id: 1, startAt: taipei(11, 21))],
      )..mineError = networkError;
      await pumpHome(tester, bookings: bookings);
      final error = find.byKey(const Key('home-upcoming-error'));
      expect(error, findsOneWidget);
      expect(
        find.descendant(of: error, matching: find.textContaining('無法連線到伺服器')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('home-card-advisor')), findsOneWidget);

      bookings.mineError = null;
      await tapKey(tester, 'home-upcoming-retry');
      expect(error, findsNothing);
      expect(find.byKey(const Key('home-upcoming-0')), findsOneWidget);
    });

    testWidgets('載入失敗時入口卡片仍可點', (tester) async {
      await pumpHome(
        tester,
        bookings: FakeBookingRepository()..mineError = networkError,
      );
      await tapKey(tester, 'home-card-rules');
      expect(find.text('到了 /rules'), findsOneWidget);
    });
  });
}
