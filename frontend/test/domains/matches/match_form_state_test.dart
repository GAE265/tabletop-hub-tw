// 情境對應 openspec/changes/add-matches-record/specs/matches-record-prototype/spec.md
// 與 matches-record 的「開局」。
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/booking/data/shop.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
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

  test('從揪團開局：setGroupId 後送出帶 group_id', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = open(container)
      ..setGameId(1)
      ..setPlayedOn(DateTime(2026, 11, 21))
      ..setGroupId('g-1');
    await form.submit();
    expect(repo.createCalls.single.groupId, 'g-1');
    expect(repo.createCalls.single.toJson()['group_id'], 'g-1');
  });

  group('loadGroup：從揪團帶入', () {
    final start = DateTime.utc(2026, 11, 21, 16, 30); // 台灣 11/22 00:30

    Group groupWith(List<GameRef> games) => fakeGroup(
      id: 'g-7',
      title: '週末輕策略',
      startAt: start,
      shopId: 's-b',
      games: games,
    );

    test('揪團只選一款遊戲：帶入揪團、桌遊店、店家、遊戲與台灣日期', () async {
      final groups = FakeGroupsRepository(
        groups: [
          groupWith(const [GameRef(id: 2, name: '阿不思學院')]),
        ],
      );
      final repo = FakeMatchesRepository();
      final container = makeContainer(repo, groups: groups);
      final form = open(container);
      await form.loadGroup('g-7');
      final state = container.read(matchFormProvider);
      expect(state.group?.title, '週末輕策略');
      expect(state.groupId, 'g-7');
      expect(state.locationType, 'shop');
      expect(state.shopId, 's-b');
      expect(state.gameId, 2);
      expect(state.playedOn, DateTime(2026, 11, 22));
      expect(state.groupError, isNull);

      await form.submit();
      final json = repo.createCalls.single.toJson();
      expect(json['group_id'], 'g-7');
      expect(json['shop_id'], 's-b');
      expect(json['location_type'], 'shop');
      expect(json['game_id'], 2);
    });

    test('揪團選了兩款以上遊戲：不自動選遊戲', () async {
      final groups = FakeGroupsRepository(
        groups: [
          groupWith(const [
            GameRef(id: 2, name: '阿不思學院'),
            GameRef(id: 3, name: '馬可波羅'),
          ]),
        ],
      );
      final container = makeContainer(FakeMatchesRepository(), groups: groups);
      final form = open(container);
      await form.loadGroup('g-7');
      final state = container.read(matchFormProvider);
      expect(state.gameId, isNull);
      expect(state.groupId, 'g-7');
      expect(state.shopId, 's-b');
    });

    test('揪團沒選遊戲：不自動選遊戲', () async {
      final groups = FakeGroupsRepository(groups: [groupWith(const [])]);
      final container = makeContainer(FakeMatchesRepository(), groups: groups);
      final form = open(container);
      await form.loadGroup('g-7');
      expect(container.read(matchFormProvider).gameId, isNull);
    });

    test('讀取揪團失敗：記下錯誤，不帶 group_id，表單仍可使用', () async {
      final container = makeContainer(
        FakeMatchesRepository(),
        groups: FakeGroupsRepository(),
      );
      final form = open(container);
      await form.loadGroup('g-missing');
      var state = container.read(matchFormProvider);
      expect(state.groupError?.code, 'GROUP_NOT_FOUND');
      expect(state.group, isNull);
      expect(state.groupId, isNull);

      final repo = FakeMatchesRepository();
      final other = makeContainer(repo, groups: FakeGroupsRepository());
      final form2 = open(other)
        ..setGameId(1)
        ..setPlayedOn(DateTime(2026, 11, 21));
      await form2.loadGroup('g-missing');
      await form2.submit();
      expect(repo.createCalls.single.groupId, isNull);
      state = other.read(matchFormProvider);
      expect(state.created, isNotNull);
    });

    test('重試讀取成功後清掉錯誤', () async {
      final groups = FakeGroupsRepository(groups: [groupWith(const [])])
        ..error = const ApiException(code: 'NETWORK_ERROR', message: '無法連線');
      final container = makeContainer(FakeMatchesRepository(), groups: groups);
      final form = open(container);
      await form.loadGroup('g-7');
      expect(container.read(matchFormProvider).groupError, isNotNull);
      groups.error = null;
      await form.loadGroup('g-7');
      final state = container.read(matchFormProvider);
      expect(state.groupError, isNull);
      expect(state.groupId, 'g-7');
    });
  });

  test('沒有設定揪團：不帶 group_id', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = open(container)
      ..setGameId(1)
      ..setPlayedOn(DateTime(2026, 11, 21));
    await form.submit();
    expect(repo.createCalls.single.groupId, isNull);
    expect(repo.createCalls.single.toJson().containsKey('group_id'), isFalse);
  });
}
