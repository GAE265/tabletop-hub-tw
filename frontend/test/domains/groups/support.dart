import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/state/current_user.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';

import '../../support/fakes.dart';

/// 現在時間：2026-11-14 04:00 UTC，也就是台灣時間 11/14 12:00。
final nowUtc = DateTime.utc(2026, 11, 14, 4);

/// 台灣時間（UTC+8）轉成 UTC。
DateTime taipei(int month, int day, [int hour = 19, int minute = 0]) =>
    DateTime.utc(
      2026,
      month,
      day,
      hour,
      minute,
    ).subtract(const Duration(hours: 8));

/// 測試中的目前使用者，可以用 [switchUser] 切換（模擬身分切換器或換人登入）。
class TestUserId extends Notifier<String?> {
  TestUserId(this.initial);

  final String? initial;

  @override
  String? build() => initial;

  void set(String? id) => state = id;
}

final testUserIdProvider = NotifierProvider<TestUserId, String?>(
  () => TestUserId(null),
);

ProviderContainer makeContainer(
  FakeGroupsRepository repo, {
  FixedOffsetClock? clock,
  String? userId = 'u-player',
}) {
  final container = ProviderContainer(
    overrides: [
      groupsRepositoryProvider.overrideWithValue(repo),
      groupClockProvider.overrideWithValue(clock ?? FixedOffsetClock(nowUtc)),
      testUserIdProvider.overrideWith(() => TestUserId(userId)),
      currentUserIdProvider.overrideWith(
        (ref) => ref.watch(testUserIdProvider),
      ),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

/// 切換目前使用者，並等 Riverpod 通知完監聽者（重新載入在這之後才開始）。
Future<void> switchUser(ProviderContainer container, String? userId) {
  container.read(testUserIdProvider.notifier).set(userId);
  return container.pump();
}
