// 情境對應 openspec/changes/add-matches-record/specs/matches-record-prototype/spec.md
// 記錄結果（陣營勝負）與覆蓋流程。
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/matches/state/match_detail_state.dart';
import 'package:tabletop_hub/domains/matches/state/result_form_state.dart';
import 'package:tabletop_hub/domains/matches/state/white_rose.dart';

import '../../support/fakes.dart';
import 'support.dart';

Future<ResultFormNotifier> openForm(ProviderContainer container) async {
  await openDetail(container);
  container.listen(resultFormProvider(fakeMatchId), (_, _) {});
  return container.read(resultFormProvider(fakeMatchId).notifier);
}

ResultFormState stateOf(ProviderContainer container) =>
    container.read(resultFormProvider(fakeMatchId));

void fillAll(ResultFormNotifier form) {
  form
    ..setWinningFaction('rose')
    ..setFaction(1, 'rose')
    ..setFaction(2, 'blood_blade')
    ..setFaction(3, 'rose');
}

void main() {
  test('陣營選項：薔薇陣營與血刃陣營', () {
    expect(whiteRoseFactions.map((f) => f.code), ['rose', 'blood_blade']);
    expect(factionLabel('rose'), '薔薇陣營');
    expect(factionLabel('blood_blade'), '血刃陣營');
    expect(factionLabel(null), '尚未記錄');
  });

  test('沒選獲勝陣營、有座位沒選陣營：列出錯誤，不送出', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = await openForm(container);
    form.setFaction(1, 'rose');
    await form.submit();
    final state = stateOf(container);
    expect(state.errors['winningFaction'], '請選擇獲勝陣營');
    expect(state.errors['factions'], contains('2, 3'));
    expect(repo.resultCalls, isEmpty);
  });

  test('記錄結果成功：送出每個座位的陣營，局變成已結束，我自動確認', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillAll(form);
    await form.submit();

    final call = repo.resultCalls.single;
    expect(call.overwrite, isFalse);
    expect(call.input.toJson(), {
      'winning_faction': 'rose',
      'participants': [
        {'seat_number': 1, 'faction': 'rose'},
        {'seat_number': 2, 'faction': 'blood_blade'},
        {'seat_number': 3, 'faction': 'rose'},
      ],
    });
    expect(stateOf(container).message, '已記錄結果');
    final match = container.read(matchDetailProvider(fakeMatchId)).match.value!;
    expect(match.status, 'finished');
    expect(match.confirmedCount, 1); // 只有記錄結果的人自動確認
    expect(match.isValid, isFalse);
  });

  test('已有結果：進入「已經有人記錄了，要更新嗎？」，舊結果不變', () async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(
        status: 'finished',
        result: const {'type': 'faction', 'winning_faction': 'blood_blade'},
      ),
    );
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillAll(form);
    await form.submit();
    final prompt = stateOf(container).overwrite;
    expect(prompt, isNotNull);
    expect(
      (prompt!.existing['result'] as Map)['winning_faction'],
      'blood_blade',
    );
    expect(repo.match.result!['winning_faction'], 'blood_blade');
  });

  test('確認覆蓋：帶 overwrite 重送，其他人的確認被清除', () async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(
        status: 'finished',
        result: const {'type': 'faction', 'winning_faction': 'blood_blade'},
        participants: [
          fakeMatchParticipant(isConfirmed: true),
          fakeMatchParticipant(
            id: 'p-2',
            seatNumber: 2,
            userId: 'u-b',
            displayName: '玩家乙',
            isConfirmed: true,
          ),
          fakeMatchParticipant(
            id: 'p-3',
            seatNumber: 3,
            userId: null,
            displayName: 'Amy',
          ),
        ],
      ),
      currentUserId: 'u-b',
    );
    final container = makeContainer(repo, userId: 'u-b');
    final form = await openForm(container);
    fillAll(form);
    await form.submit();
    await form.confirmOverwrite();

    expect(repo.resultCalls.last.overwrite, isTrue);
    expect(
      repo.resultCalls.last.input.toJson(),
      repo.resultCalls.first.input.toJson(),
    );
    final state = stateOf(container);
    expect(state.overwrite, isNull);
    expect(state.message, '結果已更新');
    final people = container
        .read(matchDetailProvider(fakeMatchId))
        .match
        .value!
        .participants;
    final confirmed = {for (final p in people) p.displayName: p.isConfirmed};
    expect(confirmed, {'測試玩家': false, '玩家乙': true, 'Amy': false});
  });

  test('取消覆蓋：清除提示，不再送出', () async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(
        status: 'finished',
        result: const {'type': 'faction', 'winning_faction': 'blood_blade'},
      ),
    );
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillAll(form);
    await form.submit();
    form.cancelOverwrite();
    expect(stateOf(container).overwrite, isNull);
    expect(repo.resultCalls, hasLength(1));
  });

  test('結果類型還沒設定（409）：顯示後端訊息，不出現覆蓋提示', () async {
    final repo = FakeMatchesRepository()
      ..actionError = const ApiException(
        code: 'MATCH_GAME_RESULT_TYPE_NOT_SET',
        message: '這款遊戲還沒有設定結果類型，不能記錄結果',
        statusCode: 409,
      );
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillAll(form);
    await form.submit();
    final state = stateOf(container);
    expect(state.error?.code, 'MATCH_GAME_RESULT_TYPE_NOT_SET');
    expect(state.overwrite, isNull);
  });

  test('送出中不重複送出', () async {
    final gate = Completer<void>();
    final repo = FakeMatchesRepository()..actionGate = gate;
    final container = makeContainer(repo);
    final form = await openForm(container);
    fillAll(form);
    final first = form.submit();
    await Future<void>.delayed(Duration.zero);
    await form.submit();
    gate.complete();
    await first;
    expect(repo.resultCalls, hasLength(1));
  });
}
