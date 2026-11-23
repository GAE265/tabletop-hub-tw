// 店家看板的 Stitch 版面：木紋背景、店家卡（日期快選、統計）、厚的座位圖卡、
// 訂位列表的標題條與篩選、厚的訂位卡片與剩餘時間。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';

import '../../../support/fakes.dart';
import 'board_overtime_test.dart' show plansWith, utc;
import 'booking_pages_test.dart' show pumpAt, sampleBooking, staff, tapKey;

void expectThick(WidgetTester tester, Finder box, [String? reason]) {
  final decoration =
      tester.widget<DecoratedBox>(box).decoration as BoxDecoration;
  final border = decoration.border! as Border;
  expect(border.bottom.width, greaterThan(border.top.width), reason: reason);
  expect(decoration.boxShadow, isNotEmpty, reason: reason);
}

Finder firstBoxIn(Finder of) =>
    find.descendant(of: of, matching: find.byType(DecoratedBox)).first;

FakeBookingRepository repoWith(List<String> statuses) => FakeBookingRepository()
  ..board = [
    for (final (i, s) in statuses.indexed) sampleBooking(id: i + 1, status: s),
  ]
  ..seatingPlans = plansWith('seated');

void main() {
  testWidgets('木紋背景；店家卡有店名、日期快選與統計，有厚度', (tester) async {
    await pumpAt(
      tester,
      '/booking/board',
      repo: repoWith(['seated', 'confirmed']),
      user: staff,
      clock: () => utc(7, 0),
    );
    expect(
      find.descendant(
        of: find.byKey(const Key('shop-board-page')),
        matching: find.byType(WoodBackground),
      ),
      findsOneWidget,
    );
    final header = find.byKey(const Key('board-header'));
    expectThick(tester, firstBoxIn(header));
    for (final key in [
      'board-date-today',
      'board-date-tomorrow',
      'board-date',
    ]) {
      expect(
        find.descendant(of: header, matching: find.byKey(Key(key))),
        findsOneWidget,
        reason: key,
      );
    }
    final stats = find.byKey(const Key('board-stats'));
    for (final label in ['全店桌數', '使用中', '已超時', '空桌']) {
      expect(
        find.descendant(of: stats, matching: find.text(label)),
        findsOneWidget,
        reason: label,
      );
    }
  });

  testWidgets('日期快選「明天」：查詢明天的訂位', (tester) async {
    final repo = repoWith(['confirmed']);
    await pumpAt(
      tester,
      '/booking/board',
      repo: repo,
      user: staff,
      clock: () => utc(7, 0),
    );
    await tapKey(tester, 'board-date-tomorrow');
    expect(repo.boardQueries.last.from, startsWith('2026-11-26'));
  });

  testWidgets('座位圖卡片有厚度', (tester) async {
    await pumpAt(
      tester,
      '/booking/board',
      repo: repoWith(['seated']),
      user: staff,
      clock: () => utc(7, 0),
    );
    expectThick(tester, firstBoxIn(find.byKey(const Key('board-seating'))));
  });

  testWidgets('訂位列表：標題條寫筆數；篩選「進行中」只留已入座的', (tester) async {
    await pumpAt(
      tester,
      '/booking/board',
      repo: repoWith(['seated', 'confirmed', 'confirmed']),
      user: staff,
      clock: () => utc(7, 0),
    );
    final bar = find.byKey(const Key('board-list-header'));
    expect(
      find.descendant(of: bar, matching: find.text('今日預約與現場桌況')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: bar, matching: find.text('3 筆')),
      findsOneWidget,
    );
    await tapKey(tester, 'board-filter-seated');
    expect(find.byKey(const Key('board-card-1')), findsOneWidget);
    expect(find.byKey(const Key('board-card-2')), findsNothing);
    await tapKey(tester, 'board-filter-waiting');
    expect(find.byKey(const Key('board-card-1')), findsNothing);
    expect(find.byKey(const Key('board-card-2')), findsOneWidget);
  });

  testWidgets('訂位卡片有厚度；已入座、還沒到結束時間：顯示剩餘分鐘', (tester) async {
    await pumpAt(
      tester,
      '/booking/board',
      repo: repoWith(['seated']),
      user: staff,
      clock: () => utc(7, 15),
    );
    final card = find.byKey(const Key('board-card-1'));
    expectThick(tester, firstBoxIn(card));
    expect(
      find.descendant(of: card, matching: find.text('剩餘 45 分鐘')),
      findsOneWidget,
    );
  });

  testWidgets('操作按鈕都是有厚度的按鈕', (tester) async {
    await pumpAt(
      tester,
      '/booking/board',
      repo: repoWith(['confirmed']),
      user: staff,
      clock: () => utc(5, 0),
    );
    for (final key in [
      'board-cancel-1',
      'board-change-table-1',
      'board-seated-1',
    ]) {
      expectThick(
        tester,
        find
            .ancestor(
              of: find.byKey(Key(key)),
              matching: find.byType(DecoratedBox),
            )
            .first,
        key,
      );
    }
  });

  testWidgets('手機底部被導覽列蓋住：捲到最底時最後一張卡片停在導覽列上方', (tester) async {
    await pumpAt(
      tester,
      '/booking/board',
      repo: repoWith(['confirmed', 'confirmed', 'confirmed']),
      user: staff,
      clock: () => utc(5, 0),
      size: const Size(400, 600),
      bottomInset: 120,
    );
    for (var i = 0; i < 2; i++) {
      await tester.drag(find.byType(Scrollable).first, const Offset(0, -5000));
      await tester.pumpAndSettle();
    }
    expect(
      tester.getBottomLeft(find.byKey(const Key('board-card-3'))).dy,
      lessThanOrEqualTo(600 - 120),
    );
  });
}
