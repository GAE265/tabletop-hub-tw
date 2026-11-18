import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/home/pages/home_page.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/domains/booking/data/booking.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';

import '../../domains/groups/support.dart';
import '../../support/fakes.dart';

const homePlayer = DevUser(id: 'u-player', displayName: '測試玩家', role: 'player');
const homeStaff = DevUser(
  id: 'u-staff',
  displayName: '測試店家人員',
  role: 'shop_staff',
  shopId: 's-b',
);
const homeAdmin = DevUser(id: 'u-admin', displayName: '測試管理員', role: 'admin');

/// 店家人員查「我的訂位」時後端回的 403。
const forbidden = ApiException(
  code: 'PERMISSION_DENIED',
  message: '沒有權限',
  statusCode: 403,
);

const networkError = ApiException(
  code: ApiException.networkErrorCode,
  message: '無法連線到伺服器',
);

/// 一筆已確認的訂位；[startAt] 是 UTC。
Booking homeBooking({
  required int id,
  required DateTime startAt,
  String status = 'confirmed',
  String shopId = 's-a',
  int partySize = 4,
  List<String> tableCodes = const ['T1', 'T2'],
}) => Booking(
  id: id,
  reservationCode: 'BK$id',
  shopId: shopId,
  shopName: '',
  startAt: startAt.toUtc().toIso8601String(),
  endAt: startAt.add(const Duration(hours: 2)).toUtc().toIso8601String(),
  partySize: partySize,
  status: status,
  tableCodes: tableCodes,
  estimatedFee: const Fee(billableHours: '2.00', venueFee: '480.00'),
);

/// 首頁會導向的頁面，測試裡換成只顯示路徑的假頁面。
const homeTargets = [
  '/groups',
  '/games-advisor',
  '/booking',
  '/booking/mine',
  '/rules',
];

/// 以正式主題與路由開啟首頁；導向的頁面只顯示「到了 <路徑>」。
Future<void> pumpHome(
  WidgetTester tester, {
  FakeBookingRepository? bookings,
  FakeGroupsRepository? groups,
  DevUser? user = homePlayer,
  Size size = const Size(400, 900),
  bool settle = true,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (context, state) => const HomePage()),
      for (final path in homeTargets)
        GoRoute(
          path: path,
          builder: (context, state) => Scaffold(body: Text('到了 $path')),
        ),
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        bookingRepositoryProvider.overrideWithValue(
          bookings ?? FakeBookingRepository(),
        ),
        groupsRepositoryProvider.overrideWithValue(
          groups ?? FakeGroupsRepository(),
        ),
        groupClockProvider.overrideWithValue(FixedOffsetClock(nowUtc)),
        currentDevUserProvider.overrideWithValue(user),
      ],
      child: MaterialApp.router(
        theme: buildAppTheme(const FakeAppFonts()),
        routerConfig: router,
      ),
    ),
  );
  if (settle) await tester.pumpAndSettle();
}
