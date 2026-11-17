import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../booking/data/booking_repository.dart';
import '../../booking/data/shop.dart';

/// 開局時「在桌遊店玩」的店家選項，取自 booking 的 `GET /api/v1/shops`。
final matchShopsProvider = FutureProvider.autoDispose<List<Shop>>(
  (ref) => ref.watch(bookingRepositoryProvider).listShops(),
  retry: (_, _) => null,
);
