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

ProviderContainer makeContainer(
  FakeGroupsRepository repo, {
  FixedOffsetClock? clock,
  String? userId = 'u-player',
}) {
  final container = ProviderContainer(
    overrides: [
      groupsRepositoryProvider.overrideWithValue(repo),
      groupClockProvider.overrideWithValue(clock ?? FixedOffsetClock(nowUtc)),
      currentUserIdProvider.overrideWithValue(userId),
    ],
  );
  addTearDown(container.dispose);
  return container;
}
