// 正式月曆頁（spec：groups-calendar-page 的「RWD 與路由」與畫面情境）。
// 邏輯已由 state 測試涵蓋，這裡只確認畫面有正確呈現 state。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/pages/groups_page.dart';

import '../../../support/fakes.dart';
import '../support.dart';
import 'page_support.dart';

/// 11/14 兩團（14:00 額滿、19:00 有空位）、11/20 一團。
FakeGroupsRepository sampleRepo() => FakeGroupsRepository(
  groups: [
    fakeGroup(
      id: 'g-evening',
      title: '週末輕策略',
      startAt: taipei(11, 14, 19),
      organizerId: 'u-a',
      organizerName: '小安',
    ),
    fakeGroup(
      id: 'g-afternoon',
      title: '阿瓦隆夜',
      startAt: taipei(11, 14, 14),
      memberCount: 4,
      waitlistCount: 2,
      organizerId: 'u-b',
      organizerName: '阿寶',
    ),
    fakeGroup(
      id: 'g-later',
      title: '新手教學團',
      startAt: taipei(11, 20, 19),
      organizerId: 'u-a',
      organizerName: '小安',
    ),
  ],
);

final calendar = find.byKey(const Key('groups-calendar'));
final dayList = find.byKey(const Key('groups-day-list'));

void main() {
  group('RWD', () {
    testWidgets('手機寬度（360）：月曆在上、當日列表在下，沒有溢出', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupsPage(),
        repo: sampleRepo(),
        size: const Size(360, 800),
      );
      expect(
        tester.getTopLeft(dayList).dy,
        greaterThanOrEqualTo(tester.getBottomLeft(calendar).dy),
      );
    });

    for (final width in [800.0, 1280.0]) {
      testWidgets('寬度 $width：月曆與當日列表左右並排', (tester) async {
        await pumpGroupsWidget(
          tester,
          const GroupsPage(),
          repo: sampleRepo(),
          size: Size(width, 900),
        );
        expect(
          tester.getTopLeft(dayList).dx,
          greaterThanOrEqualTo(tester.getTopRight(calendar).dx),
        );
      });
    }
  });

  group('月曆', () {
    testWidgets('每天顯示團數', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      expect(find.byKey(const Key('groups-page')), findsOneWidget);
      expect(find.text('2026 年 11 月'), findsOneWidget);
      expect(find.text('2 團'), findsOneWidget);
      expect(find.text('1 團'), findsOneWidget);
    });

    testWidgets('載入中顯示載入指示，不顯示團數', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupsPage(),
        repo: sampleRepo(),
        settle: false,
      );
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('2 團'), findsNothing);
      await tester.pumpAndSettle();
    });

    testWidgets('載入失敗：顯示錯誤訊息，按「重試」重新載入', (tester) async {
      final repo = sampleRepo()
        ..error = const ApiException(
          code: 'NETWORK_ERROR',
          message: '無法連線到伺服器',
        );
      await pumpGroupsWidget(tester, const GroupsPage(), repo: repo);
      expect(find.text('無法連線到伺服器'), findsOneWidget);

      repo.error = null;
      await tester.tap(find.text('重試'));
      await tester.pumpAndSettle();
      expect(find.text('2 團'), findsOneWidget);
    });

    testWidgets('切換到下個月', (tester) async {
      final repo = sampleRepo();
      await pumpGroupsWidget(tester, const GroupsPage(), repo: repo);
      await tester.tap(find.byTooltip('下個月'));
      await tester.pumpAndSettle();
      expect(find.text('2026 年 12 月'), findsOneWidget);
      expect(find.text('2 團'), findsNothing);
    });
  });

  group('當日列表', () {
    testWidgets('今天的揪團依開始時間排序，顯示時段、店家、開團主與名額', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      final afternoon = find.text('阿瓦隆夜');
      final evening = find.text('週末輕策略');
      expect(
        tester.getTopLeft(afternoon).dy,
        lessThan(tester.getTopLeft(evening).dy),
      );
      expect(find.text('14:00 – 16:00'), findsOneWidget);
      expect(find.text('已額滿，候補 2 人'), findsOneWidget);
      expect(find.text('剩 3 位'), findsOneWidget);
      expect(find.text('測試桌遊店'), findsWidgets);
      expect(find.text('開團主：阿寶'), findsOneWidget);
    });

    testWidgets('點選沒有揪團的日期：顯示「這天還沒有人揪團」與「我要開團」', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      await tester.tap(find.text('15'));
      await tester.pumpAndSettle();
      expect(find.text('這天還沒有人揪團'), findsOneWidget);
      expect(find.byKey(const Key('groups-empty-create')), findsOneWidget);
    });

    testWidgets('依開團主篩選：月曆與列表只算該開團主', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      await tester.tap(find.text('全部開團主'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('小安（2 場）').last);
      await tester.pumpAndSettle();
      expect(find.text('阿瓦隆夜'), findsNothing);
      expect(find.text('週末輕策略'), findsOneWidget);
      expect(find.text('2 團'), findsNothing);
    });

    testWidgets('點揪團開啟詳細資料', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      await tester.tap(find.text('週末輕策略'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('group-detail-page')), findsOneWidget);
    });

    testWidgets('「我要開團」開啟表單，日期預設為選取的日期', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      await tester.tap(find.byKey(const Key('groups-create')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('group-form-page')), findsOneWidget);
      expect(find.text('2026/11/14'), findsOneWidget);
    });
  });

  testWidgets('卡片顯示揪團的多款遊戲', (tester) async {
    final repo = FakeGroupsRepository(
      groups: [
        fakeGroup(
          id: 'g-games',
          title: '桌遊之夜',
          startAt: taipei(11, 14, 18),
          games: const [
            GameRef(id: 1, name: '阿瓦隆'),
            GameRef(id: 3, name: '馬可波羅'),
          ],
        ),
      ],
    );
    await pumpGroupsWidget(tester, const GroupsPage(), repo: repo);
    expect(find.text('阿瓦隆'), findsOneWidget);
    expect(find.text('馬可波羅'), findsOneWidget);
  });

  testWidgets('已成團的揪團，卡片顯示「已成團」', (tester) async {
    final repo = FakeGroupsRepository(
      groups: [
        fakeGroup(
          id: 'g-yes',
          title: '成團了',
          startAt: taipei(11, 14, 18),
          confirmedAt: nowUtc,
        ),
        fakeGroup(id: 'g-no', title: '還沒成團', startAt: taipei(11, 14, 20)),
      ],
    );
    await pumpGroupsWidget(tester, const GroupsPage(), repo: repo);
    expect(find.text('已成團'), findsOneWidget);
    expect(
      find.descendant(
        of: find.ancestor(of: find.text('成團了'), matching: find.byType(Card)),
        matching: find.text('已成團'),
      ),
      findsOneWidget,
    );
  });
}
