// 訂位正式頁面：訂位、我的訂位、店家看板。
// 操作邏輯已由 booking_state_test 涵蓋，這裡確認畫面正確呈現 state、權限與 RWD。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/domains/booking/data/booking.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/booking/pages/new_booking_page.dart';
import 'package:tabletop_hub/domains/booking/pages/my_bookings_page.dart';
import 'package:tabletop_hub/domains/booking/pages/shop_board_page.dart';
import 'package:tabletop_hub/domains/booking/state/booking_overtime.dart';

import '../../../support/fakes.dart';

const player = DevUser(id: 'u-player', displayName: '測試玩家', role: 'player');
const staff = DevUser(
  id: 'u-staff',
  displayName: '測試店家人員',
  role: 'shop_staff',
  shopId: 's-b',
);
const admin = DevUser(id: 'u-admin', displayName: '測試管理員', role: 'admin');

/// 2026-11-25（星期三）台灣時間 14:00–16:00。
Booking sampleBooking({
  int id = 7,
  String status = 'confirmed',
  String? notice,
}) => Booking(
  id: id,
  reservationCode: 'BK$id',
  shopId: 's-a',
  shopName: '',
  startAt: '2026-11-25T06:00:00Z',
  endAt: '2026-11-25T08:00:00Z',
  partySize: 4,
  status: status,
  tableCodes: const ['T1', 'T2'],
  estimatedFee: const Fee(billableHours: '2.00', venueFee: '480.00'),
  notice: notice,
);

const tableTaken = ApiException(
  code: 'BOOKING_TABLE_TAKEN',
  message: '這個時段已經沒有空桌',
  statusCode: 409,
);

Future<FakeBookingRepository> pumpAt(
  WidgetTester tester,
  String location, {
  FakeBookingRepository? repo,
  DevUser? user = player,
  Size size = const Size(400, 900),
  DateTime Function()? clock,

  /// 畫面底部被蓋住的高度（手機的浮動導覽列，見 AppShell）。
  double bottomInset = 0,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final fake = repo ?? FakeBookingRepository();
  final router = GoRouter(
    initialLocation: location,
    routes: [
      GoRoute(
        path: '/booking',
        builder: (context, state) =>
            NewBookingPage.fromQuery(state.uri.queryParameters),
        routes: [
          GoRoute(
            path: 'mine',
            builder: (context, state) => const MyBookingsPage(),
          ),
          GoRoute(
            path: 'board',
            builder: (context, state) => const ShopBoardPage(),
          ),
        ],
      ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        bookingRepositoryProvider.overrideWithValue(fake),
        currentDevUserProvider.overrideWithValue(user),
        // 店家看板的超時用固定的「現在」（add-booking-notifications）
        if (clock != null) bookingClockProvider.overrideWithValue(clock),
      ],
      child: MaterialApp.router(
        theme: buildAppTheme(const FakeAppFonts()),
        routerConfig: router,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(padding: EdgeInsets.only(bottom: bottomInset)),
          child: child!,
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return fake;
}

Future<void> chooseShop(WidgetTester tester, String name) async {
  await tester.tap(find.byKey(const Key('booking-shop')));
  await tester.pumpAndSettle();
  await tester.tap(find.text(name).last);
  await tester.pumpAndSettle();
}

Future<void> tapKey(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  await tester.ensureVisible(target);
  await tester.tap(target);
  await tester.pumpAndSettle();
}

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

void main() {
  // Stitch 版面（訂位頁）：木紋背景、分段切換的分頁、厚的表單卡與預估費用卡
  group('我的訂位（Stitch 版面）', () {
    testWidgets('木紋背景；分頁在分段切換的軌道裡；狀態篩選是一排膠囊', (tester) async {
      await pumpAt(tester, '/booking/mine');
      expect(
        find.descendant(
          of: find.byKey(const Key('my-bookings-page')),
          matching: find.byType(WoodBackground),
        ),
        findsOneWidget,
      );
      expect(find.byKey(const Key('booking-tabs')), findsOneWidget);
      final all = find.descendant(
        of: find.byKey(const Key('booking-status-all')),
        matching: find.byType(Semantics),
      );
      expect(tester.widget<Semantics>(all.first).properties.selected, isTrue);
    });

    testWidgets('訂位卡片有厚度：店名當標題，時間、人數、桌位、注意事項，底部是代碼與預估費用', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [sampleBooking(notice: '週末每位客人至少需點一杯飲料')];
      await pumpAt(tester, '/booking/mine', repo: repo);
      final card = find.byKey(const Key('booking-card-7'));
      expectThick(tester, firstBoxIn(card));
      Finder inCard(String text) =>
          find.descendant(of: card, matching: find.text(text));
      expect(inCard('甲店'), findsOneWidget);
      expect(inCard('訂位代碼 BK7'), findsOneWidget);
      expect(inCard('預估 480 元'), findsOneWidget);
    });

    testWidgets('「看座位」「取消訂位」是有厚度的按鈕', (tester) async {
      final repo = FakeBookingRepository()..mine = [sampleBooking()];
      await pumpAt(tester, '/booking/mine', repo: repo);
      for (final key in ['booking-seats-7', 'booking-cancel-7']) {
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

    testWidgets('沒有訂位：空狀態卡片有厚度，「去訂位」是厚按鈕', (tester) async {
      await pumpAt(tester, '/booking/mine');
      expectThick(tester, firstBoxIn(find.byKey(const Key('booking-empty'))));
      expectThick(
        tester,
        find
            .ancestor(
              of: find.byKey(const Key('booking-empty-new')),
              matching: find.byType(DecoratedBox),
            )
            .first,
      );
    });

    testWidgets('手機底部被導覽列蓋住：捲到最底時最後一張卡片停在導覽列上方', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [for (var i = 1; i <= 4; i++) sampleBooking(id: i)];
      await pumpAt(
        tester,
        '/booking/mine',
        repo: repo,
        size: const Size(400, 600),
        bottomInset: 120,
      );
      await tester.drag(find.byType(Scrollable).first, const Offset(0, -5000));
      await tester.pumpAndSettle();
      expect(
        tester.getBottomLeft(find.byKey(const Key('booking-card-4'))).dy,
        lessThanOrEqualTo(600 - 120),
      );
    });
  });

  group('訂位（Stitch 版面）', () {
    testWidgets('木紋背景；分頁在分段切換的軌道裡', (tester) async {
      await pumpAt(tester, '/booking', user: staff);
      expect(
        find.descendant(
          of: find.byKey(const Key('booking-page')),
          matching: find.byType(WoodBackground),
        ),
        findsOneWidget,
      );
      final track = find.byKey(const Key('booking-tabs'));
      for (final key in [
        'booking-tab-new',
        'booking-tab-mine',
        'booking-tab-board',
      ]) {
        expect(
          find.descendant(of: track, matching: find.byKey(Key(key))),
          findsOneWidget,
          reason: key,
        );
      }
    });

    testWidgets('表單卡有厚度，每一項有小標', (tester) async {
      await pumpAt(tester, '/booking');
      final form = find.byKey(const Key('booking-form'));
      expectThick(tester, firstBoxIn(form));
      for (final title in ['預約店家', '日期', '時段', '人數', '特殊需求（選填）']) {
        expect(
          find.descendant(of: form, matching: find.text(title)),
          findsOneWidget,
          reason: title,
        );
      }
    });

    testWidgets('日期快選「明天」：送出的日期是台灣時間的明天', (tester) async {
      final repo = FakeBookingRepository()..mine = [sampleBooking()];
      await pumpAt(tester, '/booking?shop_id=s-a', repo: repo);
      await tapKey(tester, 'booking-date-tomorrow');
      await tapKey(tester, 'booking-submit');
      final now = DateTime.now().toUtc().add(const Duration(hours: 8));
      final tomorrow = DateTime(now.year, now.month, now.day + 1);
      String two(int n) => n.toString().padLeft(2, '0');
      expect(
        repo.createCalls.single.startAt,
        startsWith(
          '${tomorrow.year}-${two(tomorrow.month)}-${two(tomorrow.day)}T',
        ),
      );
    });

    testWidgets('日期快選：今天、明天、後天三顆，選中的看得出來', (tester) async {
      await pumpAt(tester, '/booking?date=2026-01-01');
      for (final key in [
        'booking-date-today',
        'booking-date-tomorrow',
        'booking-date-after',
      ]) {
        expect(find.byKey(Key(key)), findsOneWidget, reason: key);
      }
      await tapKey(tester, 'booking-date-today');
      expect(
        tester
            .widget<Semantics>(
              find
                  .descendant(
                    of: find.byKey(const Key('booking-date-today')),
                    matching: find.byType(Semantics),
                  )
                  .first,
            )
            .properties
            .selected,
        isTrue,
      );
    });

    testWidgets('預估費用卡：大字總額、每人約多少、安排桌位，有厚度', (tester) async {
      await pumpAt(tester, '/booking');
      await chooseShop(tester, '甲店');
      await tapKey(tester, 'booking-quote');
      final card = find.byKey(const Key('booking-quote-card'));
      expectThick(tester, firstBoxIn(card));
      expect(
        find.descendant(of: card, matching: find.text('NT\$ 480')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: card, matching: find.textContaining('每人約 \$120')),
        findsOneWidget,
      );
    });

    testWidgets('「預估費用」「確認訂位」都是有厚度的按鈕', (tester) async {
      await pumpAt(tester, '/booking');
      for (final key in ['booking-quote', 'booking-submit']) {
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

    testWidgets('手機底部被導覽列蓋住：捲到最底時「確認訂位」停在導覽列上方', (tester) async {
      await pumpAt(
        tester,
        '/booking',
        size: const Size(400, 600),
        bottomInset: 120,
      );
      await tester.drag(find.byType(Scrollable).first, const Offset(0, -3000));
      await tester.pumpAndSettle();
      expect(
        tester.getBottomLeft(find.byKey(const Key('booking-submit'))).dy,
        lessThanOrEqualTo(600 - 120),
      );
    });
  });

  group('訂位', () {
    testWidgets('開啟：載入店家清單，玩家預設沒有選店家', (tester) async {
      final repo = await pumpAt(tester, '/booking');
      expect(repo.shopCallCount, 1);
      await tester.tap(find.byKey(const Key('booking-shop')));
      await tester.pumpAndSettle();
      expect(find.text('甲店'), findsWidgets);
      expect(find.text('乙店'), findsWidgets);
    });

    testWidgets('店家人員：預設選自己的店家', (tester) async {
      await pumpAt(tester, '/booking', user: staff);
      expect(
        find.descendant(
          of: find.byKey(const Key('booking-shop')),
          matching: find.text('乙店'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('店家載入失敗：顯示錯誤（不含錯誤代碼），按「重試」後恢復', (tester) async {
      final repo = FakeBookingRepository(
        shopError: const ApiException(code: 'NETWORK_ERROR', message: '無法連線'),
      );
      await pumpAt(tester, '/booking', repo: repo);
      expect(find.text('無法連線'), findsOneWidget);
      expect(find.textContaining('NETWORK_ERROR'), findsNothing);

      repo.shopError = null;
      await tapKey(tester, 'booking-retry-shops');
      expect(repo.shopCallCount, 2);
      expect(find.text('無法連線'), findsNothing);
    });

    testWidgets('沒選店家就按「預估費用」：提示選店家，不送出', (tester) async {
      final repo = await pumpAt(tester, '/booking');
      await tapKey(tester, 'booking-quote');
      expect(find.text('請先選擇店家'), findsOneWidget);
      expect(find.byKey(const Key('booking-quote-card')), findsNothing);

      await tapKey(tester, 'booking-submit');
      expect(repo.createCalls, isEmpty);
    });

    testWidgets('預估費用：顯示時數、費用與桌位', (tester) async {
      await pumpAt(tester, '/booking');
      await chooseShop(tester, '甲店');
      await tapKey(tester, 'booking-quote');
      final card = find.byKey(const Key('booking-quote-card'));
      expect(card, findsOneWidget);
      expect(
        find.descendant(of: card, matching: find.textContaining('2.00 小時')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: card, matching: find.textContaining('480')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: card, matching: find.textContaining('T1')),
        findsOneWidget,
      );
    });

    testWidgets('人數：按「+」「−」調整，最少 1 人', (tester) async {
      await pumpAt(tester, '/booking');
      expect(find.byKey(const Key('booking-party-size')), findsOneWidget);
      expect(
        find.descendant(
          of: find.byKey(const Key('booking-party-size')),
          matching: find.text('4'),
        ),
        findsOneWidget,
      );
      await tapKey(tester, 'booking-party-plus');
      expect(
        find.descendant(
          of: find.byKey(const Key('booking-party-size')),
          matching: find.text('5'),
        ),
        findsOneWidget,
      );
      for (var i = 0; i < 6; i++) {
        await tapKey(tester, 'booking-party-minus');
      }
      expect(
        find.descendant(
          of: find.byKey(const Key('booking-party-size')),
          matching: find.text('1'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('確認訂位：送出台灣時間，成功後跳到我的訂位', (tester) async {
      final repo = FakeBookingRepository();
      repo.mine = [sampleBooking()];
      await pumpAt(tester, '/booking', repo: repo);
      await chooseShop(tester, '甲店');
      await tapKey(tester, 'booking-submit');

      expect(repo.createCalls, hasLength(1));
      final call = repo.createCalls.single;
      expect(call.shopId, 's-a');
      expect(call.partySize, 4);
      expect(call.startAt, endsWith('T14:00:00+08:00'));
      expect(call.endAt, endsWith('T16:00:00+08:00'));
      expect(find.byType(MyBookingsPage), findsOneWidget);
      expect(find.text('訂位成功'), findsOneWidget);
    });

    testWidgets('從揪團帶入：店家、日期、時間、人數、特殊需求都已填好', (tester) async {
      final repo = FakeBookingRepository();
      repo.mine = [sampleBooking()];
      await pumpAt(
        tester,
        '/booking?shop_id=s-b&date=2026-11-21&start=19:00&end=23:00'
        '&party_size=2&requests=%E6%8F%AA%E5%9C%98%EF%BC%9A123',
        repo: repo,
      );
      expect(find.text('乙店'), findsOneWidget);
      expect(find.text('揪團：123'), findsOneWidget);
      expect(
        find.descendant(
          of: find.byKey(const Key('booking-party-size')),
          matching: find.text('2'),
        ),
        findsOneWidget,
      );
      await tapKey(tester, 'booking-submit');

      final call = repo.createCalls.single;
      expect(call.shopId, 's-b');
      expect(call.partySize, 2);
      expect(call.startAt, '2026-11-21T19:00:00+08:00');
      expect(call.endAt, '2026-11-21T23:00:00+08:00');
      expect(call.specialRequests, '揪團：123');
    });

    testWidgets('帶入的值不合法：改用預設值', (tester) async {
      final repo = FakeBookingRepository();
      repo.mine = [sampleBooking()];
      await pumpAt(
        tester,
        '/booking?shop_id=s-a&date=abc&start=19:10&end=xx&party_size=99',
        repo: repo,
      );
      await tapKey(tester, 'booking-submit');

      final call = repo.createCalls.single;
      expect(call.partySize, 30);
      expect(call.startAt, endsWith('T14:00:00+08:00'));
      expect(call.endAt, endsWith('T16:00:00+08:00'));
    });

    testWidgets('訂位失敗：顯示中文錯誤（不含錯誤代碼），留在原頁', (tester) async {
      final repo = FakeBookingRepository()..createError = tableTaken;
      await pumpAt(tester, '/booking', repo: repo);
      await chooseShop(tester, '甲店');
      await tapKey(tester, 'booking-submit');

      expect(find.text('這個時段已經沒有空桌'), findsOneWidget);
      expect(find.textContaining('BOOKING_TABLE_TAKEN'), findsNothing);
      expect(find.byType(NewBookingPage), findsOneWidget);
    });

    testWidgets('玩家看不到「店家看板」分頁；店家人員看得到', (tester) async {
      await pumpAt(tester, '/booking');
      expect(find.byKey(const Key('booking-tab-board')), findsNothing);
      expect(find.byKey(const Key('booking-tab-mine')), findsOneWidget);
    });

    testWidgets('店家人員看得到「店家看板」分頁', (tester) async {
      await pumpAt(tester, '/booking', user: staff);
      expect(find.byKey(const Key('booking-tab-board')), findsOneWidget);
    });

    testWidgets('手機：表單與預估結果上下排列；桌機：左右並排', (tester) async {
      await pumpAt(tester, '/booking');
      await chooseShop(tester, '甲店');
      await tapKey(tester, 'booking-quote');
      var form = tester.getRect(find.byKey(const Key('booking-form')));
      var quote = tester.getRect(find.byKey(const Key('booking-quote-card')));
      expect(quote.top, greaterThanOrEqualTo(form.bottom));

      await pumpAt(tester, '/booking', size: const Size(1280, 900));
      await chooseShop(tester, '甲店');
      await tapKey(tester, 'booking-quote');
      form = tester.getRect(find.byKey(const Key('booking-form')));
      quote = tester.getRect(find.byKey(const Key('booking-quote-card')));
      expect(quote.left, greaterThanOrEqualTo(form.right));
    });
  });

  group('我的訂位', () {
    testWidgets('列出訂位：代碼、店家名稱、台灣時間、人數、桌位、中文狀態', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [sampleBooking(notice: '週末每位客人至少需點一杯飲料')];
      await pumpAt(tester, '/booking/mine', repo: repo);
      final card = find.byKey(const Key('booking-card-7'));
      expect(card, findsOneWidget);
      Finder inCard(String text) =>
          find.descendant(of: card, matching: find.textContaining(text));
      expect(inCard('BK7'), findsOneWidget);
      expect(inCard('甲店'), findsOneWidget);
      expect(inCard('11/25（三）14:00–16:00'), findsOneWidget);
      expect(inCard('4 人'), findsOneWidget);
      expect(inCard('T1、T2'), findsOneWidget);
      expect(inCard('已確認'), findsOneWidget);
      expect(inCard('週末每位客人至少需點一杯飲料'), findsOneWidget);
    });

    testWidgets('沒有訂位：顯示提示與「去訂位」', (tester) async {
      await pumpAt(tester, '/booking/mine');
      expect(find.text('還沒有訂位'), findsOneWidget);
      await tapKey(tester, 'booking-empty-new');
      expect(find.byType(NewBookingPage), findsOneWidget);
    });

    testWidgets('取消訂位：先確認，確認後狀態變成已取消、取消按鈕消失', (tester) async {
      final repo = FakeBookingRepository()..mine = [sampleBooking()];
      await pumpAt(tester, '/booking/mine', repo: repo);

      await tapKey(tester, 'booking-cancel-7');
      expect(find.text('確定要取消這筆訂位嗎？'), findsOneWidget);
      await tapKey(tester, 'booking-cancel-dismiss');
      expect(repo.patchCalls, isEmpty);

      await tapKey(tester, 'booking-cancel-7');
      await tapKey(tester, 'booking-cancel-confirm');
      expect(repo.patchCalls.single.patch, {'status': 'cancelled'});
      final card = find.byKey(const Key('booking-card-7'));
      expect(
        find.descendant(of: card, matching: find.text('已取消')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('booking-cancel-7')), findsNothing);
    });

    testWidgets('已取消、已完成的訂位沒有取消按鈕', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [
          sampleBooking(id: 1, status: 'cancelled'),
          sampleBooking(id: 2, status: 'completed'),
        ];
      await pumpAt(tester, '/booking/mine', repo: repo);
      expect(find.byKey(const Key('booking-cancel-1')), findsNothing);
      expect(find.byKey(const Key('booking-cancel-2')), findsNothing);
    });

    testWidgets('取消失敗：顯示中文錯誤，狀態不變', (tester) async {
      final repo = FakeBookingRepository()
        ..mine = [sampleBooking()]
        ..patchError = const ApiException(
          code: 'BOOKING_STATUS_INVALID',
          message: '這筆訂位已經不能取消',
        );
      await pumpAt(tester, '/booking/mine', repo: repo);
      await tapKey(tester, 'booking-cancel-7');
      await tapKey(tester, 'booking-cancel-confirm');
      expect(find.text('這筆訂位已經不能取消'), findsOneWidget);
      expect(find.byKey(const Key('booking-cancel-7')), findsOneWidget);
    });
  });

  group('店家看板', () {
    testWidgets('玩家：顯示沒有權限，不查詢', (tester) async {
      final repo = await pumpAt(tester, '/booking/board');
      expect(find.byKey(const Key('board-no-permission')), findsOneWidget);
      expect(repo.boardQueries, isEmpty);
    });

    testWidgets('店家人員：查詢自己店家當天的訂位', (tester) async {
      final repo = FakeBookingRepository()..board = [sampleBooking()];
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);
      expect(repo.boardQueries, hasLength(1));
      final query = repo.boardQueries.single;
      expect(query.shopId, 's-b');
      expect(query.from, endsWith('T00:00:00+08:00'));
      expect(query.to, endsWith('T23:59:59+08:00'));
      expect(find.byKey(const Key('board-card-7')), findsOneWidget);
    });

    testWidgets('客人到店、離店結帳：依狀態顯示按鈕，按下後更新', (tester) async {
      final repo = FakeBookingRepository()..board = [sampleBooking()];
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);
      expect(find.byKey(const Key('board-complete-7')), findsNothing);
      expect(
        find.descendant(
          of: find.byKey(const Key('board-seated-7')),
          matching: find.text('客人到店'),
        ),
        findsOneWidget,
      );

      await tapKey(tester, 'board-seated-7');
      expect(repo.patchCalls.last.patch, {'status': 'seated'});
      expect(
        find.descendant(
          of: find.byKey(const Key('board-complete-7')),
          matching: find.text('離店結帳'),
        ),
        findsOneWidget,
      );
      final card = find.byKey(const Key('board-card-7'));
      expect(
        find.descendant(of: card, matching: find.text('已入座')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('board-seated-7')), findsNothing);

      await tapKey(tester, 'board-complete-7');
      expect(repo.patchCalls.last.patch, {'status': 'completed'});
      expect(
        find.descendant(of: card, matching: find.text('已完成')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: card, matching: find.textContaining('結算 480')),
        findsOneWidget,
      );
    });

    testWidgets('沒有訂位：顯示提示', (tester) async {
      await pumpAt(tester, '/booking/board', user: staff);
      expect(find.text('這天沒有訂位'), findsOneWidget);
    });

    testWidgets('管理員：先選店家才查詢', (tester) async {
      final repo = FakeBookingRepository()..board = [sampleBooking()];
      await pumpAt(tester, '/booking/board', repo: repo, user: admin);
      expect(repo.boardQueries, isEmpty);
      await chooseShop(tester, '甲店');
      expect(repo.boardQueries.single.shopId, 's-a');
    });
  });
}
