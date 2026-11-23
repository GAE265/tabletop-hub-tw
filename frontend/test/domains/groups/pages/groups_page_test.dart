// 正式月曆頁（spec：groups-calendar-page 的「RWD 與路由」與畫面情境）。
// 邏輯已由 state 測試涵蓋，這裡只確認畫面有正確呈現 state。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/app_colors.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/pages/groups_page.dart';
import 'package:tabletop_hub/domains/groups/pages/widgets/group_widgets.dart';

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

/// [box] 的外框底邊比上邊粗，而且有陰影（有厚度）。
void expectThick(WidgetTester tester, Finder box, [String? reason]) {
  final decoration =
      tester.widget<DecoratedBox>(box).decoration as BoxDecoration;
  final border = decoration.border! as Border;
  expect(border.bottom.width, greaterThan(border.top.width), reason: reason);
  expect(decoration.boxShadow, isNotEmpty, reason: reason);
}

Finder firstBoxIn(Finder of) =>
    find.descendant(of: of, matching: find.byType(DecoratedBox)).first;

Finder boxAround(Finder of) =>
    find.ancestor(of: of, matching: find.byType(DecoratedBox)).first;

void main() {
  // Stitch 版面（docs/ui/stitch/）：木紋背景，文字放在卡片或白底條上，卡片與按鈕有厚度、按得下去
  group('Stitch 版面', () {
    for (final size in const [Size(400, 900), Size(1280, 900)]) {
      testWidgets('寬度 ${size.width.toInt()}：木紋背景，頁首白底卡有標題、說明與開團主篩選', (
        tester,
      ) async {
        await pumpGroupsWidget(
          tester,
          const GroupsPage(),
          repo: sampleRepo(),
          size: size,
        );
        expect(
          find.descendant(
            of: find.byKey(const Key('groups-page')),
            matching: find.byType(WoodBackground),
          ),
          findsOneWidget,
        );
        final header = find.byKey(const Key('groups-header'));
        Finder inHeader(Finder f) => find.descendant(of: header, matching: f);
        expect(inHeader(find.text('找人一起玩・揪團月曆')), findsOneWidget);
        expect(inHeader(find.text('選取日期看當日開團，隨時加入或自己當團主')), findsOneWidget);
        expect(inHeader(find.text('全部開團主')), findsOneWidget);
        expectThick(tester, firstBoxIn(header), 'header');
      });
    }

    testWidgets('月曆卡片有厚度', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      expectThick(tester, firstBoxIn(calendar));
    });

    testWidgets('當日標題條：日期與「共 N 場」', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      final bar = find.byKey(const Key('groups-day-header'));
      expect(
        find.descendant(of: bar, matching: find.text('11/14（六）的揪團')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: bar, matching: find.text('共 2 場')),
        findsOneWidget,
      );
      expectThick(tester, firstBoxIn(bar));
    });

    testWidgets('沒有揪團的日期：標題條不顯示場數', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      await tester.tap(find.text('15'));
      await tester.pumpAndSettle();
      expect(find.textContaining('共 '), findsNothing);
    });

    testWidgets('揪團卡片：遊戲、名稱、簡介、時間、店家、開團主、費用、查看詳情', (tester) async {
      final repo = FakeGroupsRepository(
        groups: [
          fakeGroup(
            title: '卡坦島新手團',
            description: '從零開始教，歡迎新手',
            startAt: taipei(11, 14, 19),
            fee: 150,
            organizerName: '阿瑋',
            games: const [
              GameRef(id: 1, name: '卡坦島'),
              GameRef(id: 2, name: '璀璨寶石'),
            ],
          ),
        ],
      );
      await pumpGroupsWidget(tester, const GroupsPage(), repo: repo);
      final card = find.byType(GroupCard);
      Finder inCard(String text) =>
          find.descendant(of: card, matching: find.text(text));
      expect(inCard('卡坦島'), findsOneWidget);
      expect(inCard('璀璨寶石'), findsOneWidget);
      expect(inCard('卡坦島新手團'), findsOneWidget);
      expect(inCard('從零開始教，歡迎新手'), findsOneWidget);
      expect(inCard('19:00 – 21:00'), findsOneWidget);
      expect(inCard('測試桌遊店'), findsOneWidget);
      expect(inCard('開團主：阿瑋'), findsOneWidget);
      expect(inCard('\$150／人'), findsOneWidget);
      expect(inCard('查看詳情'), findsOneWidget);
      expectThick(tester, firstBoxIn(card));
    });

    testWidgets('「查看詳情」在卡片底部置中，沒有箭頭', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      final card = find.byType(GroupCard).first;
      final label = find.descendant(of: card, matching: find.text('查看詳情'));
      expect(
        tester.getCenter(label).dx,
        moreOrLessEquals(tester.getCenter(card).dx, epsilon: 1),
      );
      expect(
        find.descendant(of: card, matching: find.byIcon(Icons.arrow_forward)),
        findsNothing,
      );
    });

    testWidgets('按住揪團卡片：往下沉，移開後彈回', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      final card = find.byType(GroupCard).first;
      final title = find.descendant(of: card, matching: find.text('阿瓦隆夜'));
      double edge() =>
          ((tester.widget<DecoratedBox>(firstBoxIn(card)).decoration
                          as BoxDecoration)
                      .border!
                  as Border)
              .bottom
              .width;
      await tester.ensureVisible(card);
      await tester.pumpAndSettle();
      final restEdge = edge();
      final restTop = tester.getTopLeft(title).dy;
      final gesture = await tester.startGesture(tester.getCenter(title));
      await tester.pumpAndSettle();
      expect(edge(), lessThan(restEdge));
      expect(tester.getTopLeft(title).dy, greaterThan(restTop));
      await gesture.cancel();
      await tester.pumpAndSettle();
      expect(edge(), restEdge);
      expect(tester.getTopLeft(title).dy, restTop);
    });

    testWidgets('「我要揪團」是有厚度的深色按鈕', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      expectThick(
        tester,
        boxAround(find.byKey(const Key('groups-day-create'))),
      );
      await tester.tap(find.text('15'));
      await tester.pumpAndSettle();
      expectThick(
        tester,
        boxAround(find.byKey(const Key('groups-empty-create'))),
      );
    });

    testWidgets('兩顆「我要揪團」樣式一致：深炭色、同一個圖示、撐滿寬度', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      (Color?, IconData?, double) look(String key) {
        final button = find.byKey(Key(key));
        final style = tester.widget<ButtonStyleButton>(button).style!;
        final icon = tester
            .widget<Icon>(
              find.descendant(of: button, matching: find.byType(Icon)),
            )
            .icon;
        return (
          style.backgroundColor!.resolve({}),
          icon,
          tester.getSize(button).width,
        );
      }

      final withGroups = look('groups-day-create');
      await tester.tap(find.text('15'));
      await tester.pumpAndSettle();
      final empty = look('groups-empty-create');
      expect(withGroups.$1, AppColors.ink);
      expect(empty.$1, withGroups.$1);
      expect(empty.$2, withGroups.$2);
      // 空狀態的按鈕在卡片裡，左右各少了卡片的內距，但一樣撐滿可用寬度
      expect(empty.$3, greaterThan(300));
    });

    testWidgets('手機底部被導覽列蓋住：捲到最底時「我要揪團」停在導覽列上方', (tester) async {
      await pumpGroupsWidget(
        tester,
        const GroupsPage(),
        repo: sampleRepo(),
        bottomInset: 120,
      );
      await tester.drag(find.byType(Scrollable).first, const Offset(0, -3000));
      await tester.pumpAndSettle();
      expect(
        tester.getBottomLeft(find.byKey(const Key('groups-day-create'))).dy,
        lessThanOrEqualTo(900 - 120),
      );
    });
  });

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

    testWidgets('點選沒有揪團的日期：顯示「這天還沒有人揪團」與「我要揪團」', (tester) async {
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
      // Stitch 版面多了頁首，卡片在畫面下方，先捲過去
      await tester.ensureVisible(find.text('週末輕策略'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('週末輕策略'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('group-detail-page')), findsOneWidget);
    });

    testWidgets('「我要揪團」開啟表單，日期預設為選取的日期', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      // 右上角的按鈕拿掉了，改用當天列表下方的「我要揪團」（add-groups-notifications）
      await tester.ensureVisible(find.byKey(const Key('groups-day-create')));
      await tester.tap(find.byKey(const Key('groups-day-create')));
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
        // Stitch 版面的卡片不是 Card，改找 GroupCard
        of: find.ancestor(
          of: find.text('成團了'),
          matching: find.byType(GroupCard),
        ),
        matching: find.text('已成團'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('今天以前的日期格停用，但照樣顯示團數', (tester) async {
    final repo = FakeGroupsRepository(
      groups: [fakeGroup(id: 'past', startAt: taipei(11, 10))],
    );
    await pumpGroupsWidget(tester, const GroupsPage(), repo: repo);
    InkWell cell(String day) => tester.widget<InkWell>(
      find.ancestor(of: find.text(day), matching: find.byType(InkWell)).first,
    );
    expect(find.text('1 團'), findsOneWidget);
    expect(cell('10').onTap, isNull);
    expect(cell('13').onTap, isNull);
    expect(cell('14').onTap, isNotNull);
    expect(cell('20').onTap, isNotNull);
  });

  testWidgets('已過的揪團：日期格是灰底灰字，和之後的揪團看得出差別', (tester) async {
    final repo = FakeGroupsRepository(
      groups: [
        fakeGroup(id: 'past', startAt: taipei(11, 10)),
        fakeGroup(id: 'future', startAt: taipei(11, 20)),
      ],
    );
    await pumpGroupsWidget(tester, const GroupsPage(), repo: repo);
    Material cell(String day) => tester.widget<Material>(
      find.ancestor(of: find.text(day), matching: find.byType(Material)).first,
    );
    Text count(String day) => tester.widget<Text>(
      find.descendant(
        of: find
            .ancestor(of: find.text(day), matching: find.byType(Column))
            .first,
        matching: find.text('1 團'),
      ),
    );
    expect(cell('10').color, AppColors.border);
    expect(count('10').style!.color, AppColors.inkMuted);
    expect(cell('20').color, isNot(AppColors.border));
    expect(count('20').style!.color, isNot(AppColors.inkMuted));
  });

  group('開團入口（add-groups-notifications）', () {
    testWidgets('右上角沒有開團按鈕', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      expect(find.byKey(const Key('groups-create')), findsNothing);
    });

    testWidgets('當天有揪團：列表下方有「我要揪團」，只有一顆', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      expect(find.byKey(const Key('groups-day-create')), findsOneWidget);
      expect(find.byKey(const Key('groups-empty-create')), findsNothing);
      expect(
        find.descendant(
          of: find.byKey(const Key('groups-day-create')),
          matching: find.text('我要揪團'),
        ),
        findsOneWidget,
      );
      final lastCard = find.byType(GroupCard).last;
      expect(
        tester.getTopLeft(find.byKey(const Key('groups-day-create'))).dy,
        greaterThan(tester.getBottomLeft(lastCard).dy),
      );
    });

    testWidgets('當天沒有揪團：只有空狀態裡的一顆', (tester) async {
      await pumpGroupsWidget(tester, const GroupsPage(), repo: sampleRepo());
      await tester.tap(find.text('15'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('groups-empty-create')), findsOneWidget);
      expect(find.byKey(const Key('groups-day-create')), findsNothing);
    });
  });
}
