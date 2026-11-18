import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/matches/state/match_list_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

void main() {
  test('取得最近的局', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final matches = await container.read(matchListProvider(null).future);
    expect(matches.map((m) => m.id), [fakeMatchId]);
    expect(repo.listGroupIds, [null]);
  });

  test('帶揪團：只列這個揪團的局（呼叫 list 時帶 group_id）', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    await container.read(matchListProvider('g-1').future);
    expect(repo.listGroupIds, ['g-1']);
  });

  test('載入失敗：保留後端的錯誤碼', () async {
    final repo = FakeMatchesRepository()
      ..error = const ApiException(code: 'NETWORK_ERROR', message: '無法連線到伺服器');
    final container = makeContainer(repo);
    container.listen(matchListProvider(null), (_, _) {});
    await expectLater(
      container.read(matchListProvider(null).future),
      throwsA(isA<ApiException>()),
    );
  });
}
