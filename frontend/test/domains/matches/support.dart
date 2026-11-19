import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/groups/state/group_clock.dart';
import 'package:tabletop_hub/domains/matches/data/matches_repository.dart';
import 'package:tabletop_hub/domains/matches/state/match_current_user.dart';
import 'package:tabletop_hub/domains/matches/state/match_detail_state.dart';

import '../../support/fakes.dart';

/// 測試用容器：換掉 repository 與目前使用者。[userId] 預設是開局者（座位 1 的測試玩家）。
ProviderContainer makeContainer(
  FakeMatchesRepository repo, {
  String? userId = 'u-player',
  FakeBookingRepository? booking,
  FakeGroupsRepository? groups,
}) {
  final container = ProviderContainer(
    overrides: [
      matchesRepositoryProvider.overrideWithValue(repo),
      bookingRepositoryProvider.overrideWithValue(
        booking ?? FakeBookingRepository(),
      ),
      groupsRepositoryProvider.overrideWithValue(
        groups ?? FakeGroupsRepository(),
      ),
      // 固定在 UTC+8，結果不受執行測試的電腦時區影響
      groupClockProvider.overrideWithValue(
        FixedOffsetClock(DateTime.utc(2026, 11, 14, 4)),
      ),
      matchUserIdProvider.overrideWithValue(userId),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

/// 打開一局的詳細資料並等它載入完成。畫面開著時一直有人監聽，測試也照做（autoDispose）。
Future<MatchDetailNotifier> openDetail(
  ProviderContainer container, [
  String id = fakeMatchId,
]) async {
  container.listen(matchDetailProvider(id), (_, _) {});
  final notifier = container.read(matchDetailProvider(id).notifier);
  await notifier.loaded;
  return notifier;
}
