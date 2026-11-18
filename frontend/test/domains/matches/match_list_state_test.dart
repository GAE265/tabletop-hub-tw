import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/matches/state/match_list_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

void main() {
  test('取得最近的局', () async {
    final container = makeContainer(FakeMatchesRepository());
    final matches = await container.read(matchListProvider.future);
    expect(matches.map((m) => m.id), [fakeMatchId]);
  });

  test('載入失敗：保留後端的錯誤碼', () async {
    final repo = FakeMatchesRepository()
      ..error = const ApiException(code: 'NETWORK_ERROR', message: '無法連線到伺服器');
    final container = makeContainer(repo);
    container.listen(matchListProvider, (_, _) {});
    await expectLater(
      container.read(matchListProvider.future),
      throwsA(isA<ApiException>()),
    );
  });
}
