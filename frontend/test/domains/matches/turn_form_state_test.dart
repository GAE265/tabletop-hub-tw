// 情境對應 openspec/changes/add-matches-record/specs/matches-record-prototype/spec.md
// 「同一回合已有紀錄」「使用者確認覆蓋」「使用者取消覆蓋」，以及白薔薇的回合表單。
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/matches/state/match_detail_state.dart';
import 'package:tabletop_hub/domains/matches/state/turn_form_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

Future<TurnFormNotifier> openForm(
  ProviderContainer container, {
  String id = fakeMatchId,
}) async {
  await openDetail(container, id);
  container.listen(turnFormProvider(id), (_, _) {});
  return container.read(turnFormProvider(id).notifier);
}

TurnFormState stateOf(ProviderContainer container) =>
    container.read(turnFormProvider(fakeMatchId));

void fillOne(TurnFormNotifier form) {
  form
    ..setFirstSeat(2)
    ..togglePlayedSeat(2)
    ..togglePlayedSeat(1)
    ..setCount(TurnCounter.doubleBlade, 1)
    ..setCount(TurnCounter.faithful, 2)
    ..setHasWhiteRose(true);
}

void main() {
  test('預設從第 1 回合開始，數量都是 0', () async {
    final container = makeContainer(FakeMatchesRepository());
    await openForm(container);
    final state = stateOf(container);
    expect(state.turnNumber, 1);
    expect(state.playedSeats, isEmpty);
    expect(state.doubleBladeCount, 0);
    expect(state.hasWhiteRose, isFalse);
  });

  test('點選出牌的座位：再點一次取消', () async {
    final container = makeContainer(FakeMatchesRepository());
    final form = await openForm(container)
      ..togglePlayedSeat(2)
      ..togglePlayedSeat(1);
    expect(stateOf(container).playedSeats, {1, 2});
    form.togglePlayedSeat(2);
    expect(stateOf(container).playedSeats, {1});
  });

  test('數量不會小於 0', () async {
    final container = makeContainer(FakeMatchesRepository());
    final form = await openForm(container)
      ..setCount(TurnCounter.giantBlade, -3);
    expect(stateOf(container).giantBladeCount, 0);
    form.setCount(TurnCounter.giantBlade, 2);
    expect(stateOf(container).giantBladeCount, 2);
  });

  test('本回合首家預設不選，也不是必填；沒選出牌座位才不送出', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = await openForm(container);
    expect(stateOf(container).firstSeat, isNull);
    await form.submit();
    expect(stateOf(container).errors.keys, ['playedSeats']);
    expect(repo.turnCalls, isEmpty);
  });

  test('沒選本回合首家也能送出：seat_number 送 null', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = await openForm(container)
      ..togglePlayedSeat(1)
      ..togglePlayedSeat(2);
    await form.submit();
    final input = repo.turnCalls.single.input;
    expect(input.seatNumber, isNull);
    expect(input.toJson()['seat_number'], isNull);
    expect(input.toJson().containsKey('seat_number'), isTrue);
    expect(repo.match.turns.single.seatNumber, isNull);
  });

  test('選了本回合首家再改成不選：送 null', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = await openForm(container)
      ..setFirstSeat(2)
      ..setFirstSeat(null)
      ..togglePlayedSeat(1);
    await form.submit();
    expect(repo.turnCalls.single.input.seatNumber, isNull);
  });

  test('回合編號小於 1：不送出', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillOne(form);
    form.setTurnNumber(0);
    await form.submit();
    expect(stateOf(container).errors.keys, ['turnNumber']);
    expect(repo.turnCalls, isEmpty);
  });

  test('記錄回合成功：送出白薔薇格式，詳細資料多一個回合，表單準備下一回合', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillOne(form);
    await form.submit();

    final call = repo.turnCalls.single;
    expect(call.overwrite, isFalse);
    expect(call.input.toJson(), {
      'turn_number': 1,
      'seat_number': 2,
      'game_data': {
        'played_seat_numbers': [1, 2],
        'double_blade_count': 1,
        'dark_blade_count': 0,
        'giant_blade_count': 0,
        'faithful_count': 2,
        'has_white_rose': true,
      },
    });
    final state = stateOf(container);
    expect(state.message, '第 1 回合已記錄');
    expect(state.busy, isFalse);
    expect(state.overwrite, isNull);
    expect(state.turnNumber, 2);
    expect(state.playedSeats, isEmpty);
    expect(state.firstSeat, isNull);
    final turns = container
        .read(matchDetailProvider(fakeMatchId))
        .match
        .value!
        .turns;
    expect(turns.map((t) => t.turnNumber), [1]);
  });

  test('同一回合已有紀錄：進入「已經有人記錄了，要更新嗎？」，舊紀錄不變', () async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(turns: [fakeMatchTurn(seatNumber: 1)]),
    );
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillOne(form);
    await form.submit();

    final state = stateOf(container);
    expect(state.overwrite, isNotNull);
    expect(state.overwrite!.existing['seat_number'], 1);
    expect(state.overwrite!.input.turnNumber, 1);
    expect(overwritePromptText, '已經有人記錄了，要更新嗎？');
    expect(state.error, isNull);
    expect(state.turnNumber, 1); // 還沒成功，不前進
    expect(repo.turnCalls, hasLength(1));
    expect(repo.match.turns.single.seatNumber, 1);
  });

  test('確認覆蓋：帶 overwrite 重送同一份內容', () async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(turns: [fakeMatchTurn(seatNumber: 1)]),
    );
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillOne(form);
    await form.submit();
    await form.confirmOverwrite();

    expect(repo.turnCalls, hasLength(2));
    expect(repo.turnCalls.last.overwrite, isTrue);
    expect(
      repo.turnCalls.last.input.toJson(),
      repo.turnCalls.first.input.toJson(),
    );
    final state = stateOf(container);
    expect(state.overwrite, isNull);
    expect(state.message, '第 1 回合已更新');
    final turns = container
        .read(matchDetailProvider(fakeMatchId))
        .match
        .value!
        .turns;
    expect(turns.single.seatNumber, 2);
  });

  test('取消覆蓋：清除提示，不再送出，舊紀錄不變', () async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(turns: [fakeMatchTurn(seatNumber: 1)]),
    );
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillOne(form);
    await form.submit();
    form.cancelOverwrite();

    expect(stateOf(container).overwrite, isNull);
    expect(repo.turnCalls, hasLength(1));
    expect(repo.match.turns.single.seatNumber, 1);
  });

  test('沒有待確認的覆蓋時，確認覆蓋什麼都不做', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = await openForm(container);
    await form.confirmOverwrite();
    expect(repo.turnCalls, isEmpty);
  });

  test('其他錯誤（不是已有紀錄）：保留錯誤碼，不出現覆蓋提示', () async {
    final repo = FakeMatchesRepository()
      ..actionError = const ApiException(
        code: 'PERMISSION_DENIED',
        message: '沒有權限執行此操作',
        statusCode: 403,
      );
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillOne(form);
    await form.submit();
    final state = stateOf(container);
    expect(state.error?.code, 'PERMISSION_DENIED');
    expect(state.overwrite, isNull);
    expect(state.busy, isFalse);
  });

  test('座位不存在（422）：顯示後端訊息', () async {
    final repo = FakeMatchesRepository()
      ..actionError = const ApiException(
        code: 'MATCH_SEAT_NOT_FOUND',
        message: '這一局沒有座位 [9]',
        statusCode: 422,
        details: {
          'seat_numbers': [9],
        },
      );
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillOne(form);
    await form.submit();
    expect(stateOf(container).error?.details['seat_numbers'], [9]);
  });

  test('送出中不重複送出', () async {
    final gate = Completer<void>();
    final repo = FakeMatchesRepository()..actionGate = gate;
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillOne(form);
    final first = form.submit();
    await Future<void>.delayed(Duration.zero);
    expect(stateOf(container).busy, isTrue);
    await form.submit();
    gate.complete();
    await first;
    expect(repo.turnCalls, hasLength(1));
  });
}
