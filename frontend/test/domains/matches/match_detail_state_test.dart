// 情境對應 openspec/changes/add-matches-record/specs/matches-record-prototype/spec.md
// 「data 與 state」：查詢（含刷新）、參加者、確認、人數統計與有效紀錄。
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/matches/state/match_detail_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

void main() {
  test('載入一局：顯示 N 人參加、M 人有帳號、K 人已確認', () async {
    final container = makeContainer(FakeMatchesRepository());
    await openDetail(container);
    final state = container.read(matchDetailProvider(fakeMatchId));
    expect(state.match.value?.id, fakeMatchId);
    expect(state.participantSummary, '3 人參加、2 人有帳號、0 人已確認');
    expect(state.validityLabel, '尚未成為有效紀錄');
  });

  test('載入失敗：保留後端的錯誤碼', () async {
    final repo = FakeMatchesRepository()
      ..error = const ApiException(
        code: 'MATCH_NOT_FOUND',
        message: '找不到這一局',
        statusCode: 404,
      );
    final container = makeContainer(repo);
    await openDetail(container);
    final state = container.read(matchDetailProvider(fakeMatchId));
    expect(state.match.hasError, isTrue);
    expect((state.match.error! as ApiException).code, 'MATCH_NOT_FOUND');
    expect(state.participantSummary, isNull);
  });

  test('刷新：重新查詢，取得別人剛記錄的內容', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final detail = await openDetail(container);
    expect(
      container.read(matchDetailProvider(fakeMatchId)).match.value!.turns,
      isEmpty,
    );
    // 別人用另一台裝置記錄了第 1 回合
    repo.match = repo.match.copyWith(turns: [fakeMatchTurn()]);
    await detail.reload();
    final turns = container
        .read(matchDetailProvider(fakeMatchId))
        .match
        .value!
        .turns;
    expect(turns.single.turnNumber, 1);
    expect(repo.getCalls, hasLength(2));
  });

  test('自己加入：不帶名字，加入後重新載入', () async {
    final repo = FakeMatchesRepository(currentUserId: 'u-c');
    final container = makeContainer(repo, userId: 'u-c');
    final detail = await openDetail(container);
    await detail.joinSelf();
    expect(repo.addCalls.single.toJson(), isEmpty);
    final state = container.read(matchDetailProvider(fakeMatchId));
    expect(state.match.value!.participantCount, 4);
    expect(state.message, '已加入這一局');
    expect(state.busy, isFalse);
  });

  test('自己加入時選座位', () async {
    final repo = FakeMatchesRepository(currentUserId: 'u-c');
    final container = makeContainer(repo, userId: 'u-c');
    final detail = await openDetail(container);
    await detail.joinSelf(seatNumber: 5);
    expect(repo.addCalls.single.toJson(), {'seat_number': 5});
  });

  test('新增沒有帳號的人：送出名字與座位', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final detail = await openDetail(container);
    await detail.addNamed('  Bob ', seatNumber: 6);
    expect(repo.addCalls.single.toJson(), {
      'display_name': 'Bob',
      'seat_number': 6,
    });
    final match = container.read(matchDetailProvider(fakeMatchId)).match.value!;
    expect((match.participantCount, match.accountCount), (4, 2));
  });

  test('新增沒有帳號的人：名字空白不送出', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final detail = await openDetail(container);
    await detail.addNamed('   ');
    expect(repo.addCalls, isEmpty);
    expect(
      container.read(matchDetailProvider(fakeMatchId)).error?.code,
      'EMPTY_NAME',
    );
  });

  test('移除參加者：移除沒有帳號的人', () async {
    final repo = FakeMatchesRepository();
    final container = makeContainer(repo);
    final detail = await openDetail(container);
    await detail.remove('p-3');
    expect(repo.removeCalls, ['p-3']);
    final match = container.read(matchDetailProvider(fakeMatchId)).match.value!;
    expect(match.participants.map((p) => p.displayName), ['測試玩家', '玩家乙']);
  });

  test('移除參加者被回合擋下：保留錯誤與回合編號，名單不變', () async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(turns: [fakeMatchTurn(seatNumber: 2)]),
    );
    final container = makeContainer(repo);
    final detail = await openDetail(container);
    await detail.remove('p-2');
    final state = container.read(matchDetailProvider(fakeMatchId));
    expect(state.error?.code, 'MATCH_PARTICIPANT_HAS_TURNS');
    expect(state.error?.details['turn_numbers'], [1]);
    expect(state.match.value!.participantCount, 3);
  });

  test('確認：只確認自己的那一位，人數與有效紀錄跟著變', () async {
    final finished = fakeMatch(
      status: 'finished',
      result: const {'type': 'faction', 'winning_faction': 'rose'},
      participants: [
        fakeMatchParticipant(isConfirmed: true),
        fakeMatchParticipant(
          id: 'p-2',
          seatNumber: 2,
          userId: 'u-b',
          displayName: '玩家乙',
        ),
        fakeMatchParticipant(
          id: 'p-3',
          seatNumber: 3,
          userId: null,
          displayName: 'Amy',
        ),
      ],
    );
    final repo = FakeMatchesRepository(match: finished, currentUserId: 'u-b');
    final container = makeContainer(repo, userId: 'u-b');
    final detail = await openDetail(container);
    expect(
      container.read(matchDetailProvider(fakeMatchId)).participantSummary,
      '3 人參加、2 人有帳號、1 人已確認',
    );
    await detail.confirmMine();
    expect(repo.confirmCalls, ['p-2']);
    final state = container.read(matchDetailProvider(fakeMatchId));
    expect(state.participantSummary, '3 人參加、2 人有帳號、2 人已確認');
    expect(state.validityLabel, '有效紀錄');
    expect(state.message, '已確認');
  });

  test('確認：不是參加者就不送出', () async {
    final repo = FakeMatchesRepository(match: fakeMatch(status: 'finished'));
    final container = makeContainer(repo, userId: 'u-outsider');
    final detail = await openDetail(container);
    await detail.confirmMine();
    expect(repo.confirmCalls, isEmpty);
    expect(
      container.read(matchDetailProvider(fakeMatchId)).error?.code,
      'NOT_A_PARTICIPANT',
    );
  });

  test('操作失敗：保留錯誤碼與訊息，不再忙碌', () async {
    final repo = FakeMatchesRepository(currentUserId: 'u-c')
      ..actionError = const ApiException(
        code: 'MATCH_SEAT_TAKEN',
        message: '座位 2 已經有人',
        statusCode: 409,
      );
    final container = makeContainer(repo, userId: 'u-c');
    final detail = await openDetail(container);
    await detail.joinSelf(seatNumber: 2);
    final state = container.read(matchDetailProvider(fakeMatchId));
    expect(state.error?.code, 'MATCH_SEAT_TAKEN');
    expect(state.error?.message, '座位 2 已經有人');
    expect(state.busy, isFalse);
    expect(state.message, isNull);
  });

  test('操作進行中不接受重複送出', () async {
    final gate = Completer<void>();
    final repo = FakeMatchesRepository(currentUserId: 'u-c')..actionGate = gate;
    final container = makeContainer(repo, userId: 'u-c');
    final detail = await openDetail(container);
    final first = detail.joinSelf();
    await Future<void>.delayed(Duration.zero);
    expect(container.read(matchDetailProvider(fakeMatchId)).busy, isTrue);
    await detail.joinSelf();
    gate.complete();
    await first;
    expect(repo.addCalls, hasLength(1));
  });

  group('依身分與狀態決定按鈕', () {
    Future<List<MatchAction>> actions(
      FakeMatchesRepository repo,
      String? userId,
    ) async {
      final container = makeContainer(repo, userId: userId);
      await openDetail(container);
      return container
          .read(matchDetailProvider(fakeMatchId))
          .actionsFor(userId);
    }

    test('不在這局、進行中：加入', () async {
      expect(await actions(FakeMatchesRepository(), 'u-c'), [MatchAction.join]);
    });

    test('在這局、進行中：新增沒有帳號的人、退出', () async {
      expect(await actions(FakeMatchesRepository(), 'u-player'), [
        MatchAction.addNamed,
        MatchAction.leave,
      ]);
    });

    test('已結束、自己還沒確認：確認', () async {
      final repo = FakeMatchesRepository(match: fakeMatch(status: 'finished'));
      expect(await actions(repo, 'u-b'), [MatchAction.confirm]);
    });

    test('已結束、自己已經確認：沒有按鈕', () async {
      final match = fakeMatch(
        status: 'finished',
        participants: [fakeMatchParticipant(isConfirmed: true)],
      );
      expect(
        await actions(FakeMatchesRepository(match: match), 'u-player'),
        [],
      );
    });

    test('已結束、不在這局：沒有按鈕', () async {
      final repo = FakeMatchesRepository(match: fakeMatch(status: 'finished'));
      expect(await actions(repo, 'u-c'), []);
    });

    test('沒有目前使用者：沒有按鈕', () async {
      expect(await actions(FakeMatchesRepository(), null), []);
    });
  });
}
