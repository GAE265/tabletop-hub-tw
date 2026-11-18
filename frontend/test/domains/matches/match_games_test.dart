// 開局表單的遊戲選項（取自 GET /api/v1/games）。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/groups_repository.dart';
import 'package:tabletop_hub/domains/matches/state/match_games.dart';

import '../../support/fakes.dart';

ProviderContainer makeGamesContainer(FakeGroupsRepository repo) {
  final container = ProviderContainer(
    overrides: [groupsRepositoryProvider.overrideWithValue(repo)],
  );
  addTearDown(container.dispose);
  container.listen(matchGameOptionsProvider, (_, _) {});
  return container;
}

void main() {
  test('列出全部遊戲', () async {
    final container = makeGamesContainer(FakeGroupsRepository());
    final games = await container.read(matchGameOptionsProvider.future);
    expect(games.map((g) => g.name), ['阿瓦隆', '阿不思學院', '馬可波羅']);
  });

  test('載入失敗：錯誤狀態，不自動重試；重新載入後成功', () async {
    final repo = FakeGroupsRepository()
      ..gamesError = const ApiException(code: 'X', message: '失敗');
    final container = makeGamesContainer(repo);
    await expectLater(
      container.read(matchGameOptionsProvider.future),
      throwsA(isA<ApiException>()),
    );
    expect(repo.gamesCalls, 1);

    repo.gamesError = null;
    container.invalidate(matchGameOptionsProvider);
    final games = await container.read(matchGameOptionsProvider.future);
    expect(games, hasLength(3));
  });
}
