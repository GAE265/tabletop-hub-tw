// 訂位正式頁面：訂位、我的訂位、店家看板。
// 操作邏輯已由 booking_state_test 涵蓋，這裡確認畫面正確呈現 state、權限與 RWD。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/domains/booking/data/booking.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/booking/pages/new_booking_page.dart';
import 'package:tabletop_hub/domains/booking/pages/my_bookings_page.dart';
import 'package:tabletop_hub/domains/booking/pages/shop_board_page.dart';

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
        builder: (context, state) => const NewBookingPage(),
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
      ],
      child: MaterialApp.router(
        theme: buildAppTheme(const FakeAppFonts()),
        routerConfig: router,
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

void main() {
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

    testWidgets('未到店：先確認，標記後可以改回客人到店', (tester) async {
      final repo = FakeBookingRepository()..board = [sampleBooking()];
      await pumpAt(tester, '/booking/board', repo: repo, user: staff);
      final card = find.byKey(const Key('board-card-7'));

      await tapKey(tester, 'board-noshow-7');
      expect(find.text('確定要標記為未到店嗎？'), findsOneWidget);
      await tapKey(tester, 'booking-cancel-dismiss');
      expect(repo.patchCalls, isEmpty);

      await tapKey(tester, 'board-noshow-7');
      await tapKey(tester, 'booking-cancel-confirm');
      expect(repo.patchCalls.single.patch, {'status': 'no_show'});
      expect(
        find.descendant(of: card, matching: find.text('未到店')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('board-noshow-7')), findsNothing);
      expect(find.byKey(const Key('board-cancel-7')), findsNothing);

      // 標錯時改回客人到店
      await tapKey(tester, 'board-seated-7');
      expect(repo.patchCalls.last.patch, {'status': 'seated'});
      expect(
        find.descendant(of: card, matching: find.text('已入座')),
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
