// 情境對應 openspec/changes/add-matches-record/specs/matches-record-prototype/spec.md
// 與 matches-record 的「開局」。
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/booking/data/shop.dart';
import 'package:tabletop_hub/domains/matches/state/match_form_state.dart';
import 'package:tabletop_hub/domains/matches/state/match_shops.dart';

import '../../support/fakes.dart';
import 'support.dart';

MatchFormNotifier open(ProviderContainer container) {
  container.listen(matchFormProvider, (_, _) {});
  return container.read(matchFormProvider.notifier);
}

void main() {
  test('什麼都沒填就送出：每個必填欄位都有錯誤，不送出', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = open(container);
    await form.submit();
    final state = container.read(matchFormProvider);
    expect(state.errors.keys, containsAll(['gameId', 'playedOn']));
    expect(state.created, isNull);
    expect(repo.createCalls, isEmpty);
  });

  test('自家開局：不帶店家，帶自己選的座位', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = open(container)
      ..setGameId(1)
      ..setPlayedOn(DateTime(2026, 11, 20))
      ..setLocationType('home')
      ..setSeatNumber(4);
    await form.submit();
    expect(repo.createCalls.single.toJson(), {
      'game_id': 1,
      'played_on': '2026-11-20',
      'location_type': 'home',
      'seat_number': 4,
    });
    final state = container.read(matchFormProvider);
    expect(state.created?.id, fakeMatchId);
    expect(state.busy, isFalse);
    expect(state.errors, isEmpty);
  });

  test('店家開局：沒選店家時不送出', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = open(container)
      ..setGameId(1)
      ..setPlayedOn(DateTime(2026, 11, 20))
      ..setLocationType('shop');
    await form.submit();
    expect(container.read(matchFormProvider).errors.keys, ['shopId']);
    expect(repo.createCalls, isEmpty);
  });

  test('店家開局：帶店家', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = open(container)
      ..setGameId(1)
      ..setPlayedOn(DateTime(2026, 11, 20))
      ..setLocationType('shop')
      ..setShopId('s-1');
    await form.submit();
    final json = repo.createCalls.single.toJson();
    expect(json['location_type'], 'shop');
    expect(json['shop_id'], 's-1');
    expect(json.containsKey('seat_number'), isFalse);
  });

  test('改成自家會清掉已選的店家', () {
    final container = makeContainer(FakeMatchesRepository());
    open(container)
      ..setLocationType('shop')
      ..setShopId('s-1')
      ..setLocationType('home');
    expect(container.read(matchFormProvider).shopId, '');
  });

  test('後端回錯誤：顯示訊息，沒有建立', () async {
    final repo = FakeMatchesRepository()
      ..actionError = const ApiException(
        code: 'MATCH_GAME_NOT_FOUND',
        message: '找不到這款遊戲',
        statusCode: 404,
      );
    final container = makeContainer(repo);
    final form = open(container)
      ..setGameId(999)
      ..setPlayedOn(DateTime(2026, 11, 20));
    await form.submit();
    final state = container.read(matchFormProvider);
    expect(state.error?.code, 'MATCH_GAME_NOT_FOUND');
    expect(state.created, isNull);
    expect(state.busy, isFalse);
  });

  test('送出中不重複送出', () async {
    final gate = Completer<void>();
    final repo = FakeMatchesRepository()..actionGate = gate;
    final container = makeContainer(repo);
    final form = open(container)
      ..setGameId(1)
      ..setPlayedOn(DateTime(2026, 11, 20));
    final first = form.submit();
    await Future<void>.delayed(Duration.zero);
    expect(container.read(matchFormProvider).busy, isTrue);
    await form.submit();
    gate.complete();
    await first;
    expect(repo.createCalls, hasLength(1));
  });

  test('店家清單取自 booking 的店家 API', () async {
    final container = makeContainer(
      FakeMatchesRepository(),
      booking: FakeBookingRepository(shops: const [fakeShopA, fakeShopB]),
    );
    final shops = await container.read(matchShopsProvider.future);
    expect(shops.map((Shop s) => s.id), [fakeShopA.id, fakeShopB.id]);
  });
}
