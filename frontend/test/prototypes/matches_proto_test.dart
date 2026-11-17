// 參考畫面（spec：matches-record-prototype 的「參考畫面」）。
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/booking/data/booking_repository.dart';
import 'package:tabletop_hub/domains/matches/data/game_match.dart';
import 'package:tabletop_hub/domains/matches/data/matches_repository.dart';
import 'package:tabletop_hub/domains/matches/state/match_current_user.dart';
import 'package:tabletop_hub/prototypes/matches/match_detail_proto_page.dart';

import '../support/fakes.dart';

Future<void> pumpDetail(
  WidgetTester tester,
  FakeMatchesRepository repo, {
  String? userId = 'u-player',
}) async {
  tester.view.physicalSize = const Size(900, 3000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        matchesRepositoryProvider.overrideWithValue(repo),
        bookingRepositoryProvider.overrideWithValue(FakeBookingRepository()),
        matchUserIdProvider.overrideWithValue(userId),
      ],
      child: const MaterialApp(
        home: MatchDetailProtoPage(matchId: fakeMatchId),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Finder key(String value) => find.byKey(Key(value));

void main() {
  testWidgets('顯示 N 人參加、M 人有帳號、K 人已確認與是否有效', (tester) async {
    await pumpDetail(tester, FakeMatchesRepository());
    expect(find.text('3 人參加、2 人有帳號、0 人已確認'), findsOneWidget);
    expect(find.text('尚未成為有效紀錄'), findsOneWidget);
    expect(find.textContaining('玩家乙'), findsWidgets);
    expect(key('turns-empty'), findsOneWidget);
  });

  testWidgets('載入中：顯示載入中文字', (tester) async {
    final repo = FakeMatchesRepository();
    final gate = Completer<void>();
    // get 還沒回來之前畫面應該顯示載入中
    final slow = _SlowRepository(repo, gate.future);
    tester.view.physicalSize = const Size(900, 3000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          matchesRepositoryProvider.overrideWithValue(slow),
          matchUserIdProvider.overrideWithValue('u-player'),
        ],
        child: const MaterialApp(
          home: MatchDetailProtoPage(matchId: fakeMatchId),
        ),
      ),
    );
    await tester.pump();
    await tester.pump();
    expect(find.text('載入中…'), findsOneWidget);
    gate.complete();
    await tester.pumpAndSettle();
    expect(find.text('載入中…'), findsNothing);
  });

  testWidgets('載入失敗：顯示後端的訊息與重試', (tester) async {
    final repo = FakeMatchesRepository()
      ..error = const ApiException(
        code: 'MATCH_NOT_FOUND',
        message: '找不到這一局',
        statusCode: 404,
      );
    await pumpDetail(tester, repo);
    expect(find.textContaining('找不到這一局'), findsOneWidget);
    expect(key('retry'), findsOneWidget);
  });

  testWidgets('刷新：按重新整理取得別人剛記錄的回合', (tester) async {
    final repo = FakeMatchesRepository();
    await pumpDetail(tester, repo);
    expect(key('turn-1'), findsNothing);
    repo.match = repo.match.copyWith(turns: [fakeMatchTurn(seatNumber: 2)]);
    await tester.tap(key('refresh'));
    await tester.pumpAndSettle();
    expect(key('turn-1'), findsOneWidget);
  });

  testWidgets('不在這局的人：看到加入，沒有記錄回合的表單', (tester) async {
    await pumpDetail(tester, FakeMatchesRepository(), userId: 'u-outsider');
    expect(key('join'), findsOneWidget);
    expect(key('turn-form'), findsNothing);
    expect(key('result-readonly'), findsOneWidget);
  });

  testWidgets('記錄回合遇到已有紀錄：顯示「已經有人記錄了，要更新嗎？」，確認後更新', (tester) async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(turns: [fakeMatchTurn(seatNumber: 1)]),
    );
    await pumpDetail(tester, repo);
    await tester.ensureVisible(key('turn-leader'));
    await tester.tap(key('turn-leader'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('2 玩家乙').last);
    await tester.pumpAndSettle();
    await tester.tap(key('turn-seat-1'));
    await tester.pump();
    await tester.ensureVisible(key('turn-submit'));
    await tester.tap(key('turn-submit'));
    await tester.pumpAndSettle();

    expect(find.text('已經有人記錄了，要更新嗎？'), findsOneWidget);
    expect(key('overwrite-confirm'), findsOneWidget);
    expect(key('overwrite-cancel'), findsOneWidget);
    expect(repo.turnCalls, hasLength(1));

    await tester.tap(key('overwrite-confirm'));
    await tester.pumpAndSettle();
    expect(repo.turnCalls.last.overwrite, isTrue);
    expect(find.text('已經有人記錄了，要更新嗎？'), findsNothing);
    expect(find.textContaining('第 1 回合已更新'), findsOneWidget);
  });

  testWidgets('取消覆蓋：提示消失，不再送出', (tester) async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(turns: [fakeMatchTurn(seatNumber: 1)]),
    );
    await pumpDetail(tester, repo);
    await tester.ensureVisible(key('turn-leader'));
    await tester.tap(key('turn-leader'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('1 測試玩家').last);
    await tester.pumpAndSettle();
    await tester.tap(key('turn-seat-1'));
    await tester.pump();
    await tester.ensureVisible(key('turn-submit'));
    await tester.tap(key('turn-submit'));
    await tester.pumpAndSettle();
    await tester.tap(key('overwrite-cancel'));
    await tester.pumpAndSettle();
    expect(find.text('已經有人記錄了，要更新嗎？'), findsNothing);
    expect(repo.turnCalls, hasLength(1));
  });

  testWidgets('已結束、自己還沒確認：有確認按鈕，按下去後人數更新', (tester) async {
    final repo = FakeMatchesRepository(match: fakeMatch(status: 'finished'));
    await pumpDetail(tester, repo);
    expect(key('confirm'), findsOneWidget);
    await tester.ensureVisible(key('confirm'));
    await tester.tap(key('confirm'));
    await tester.pumpAndSettle();
    expect(find.text('3 人參加、2 人有帳號、1 人已確認'), findsOneWidget);
    expect(key('confirm'), findsNothing);
  });

  testWidgets('移除參加者：先跳確認；被回合擋下時顯示相關回合', (tester) async {
    final repo = FakeMatchesRepository(
      match: fakeMatch(turns: [fakeMatchTurn(seatNumber: 2)]),
    );
    await pumpDetail(tester, repo);
    await tester.ensureVisible(key('remove-p-2'));
    await tester.tap(key('remove-p-2'));
    await tester.pumpAndSettle();
    expect(find.textContaining('要移除座位 2'), findsOneWidget);
    await tester.tap(key('remove-confirm'));
    await tester.pumpAndSettle();
    expect(find.textContaining('MATCH_PARTICIPANT_HAS_TURNS'), findsOneWidget);
    expect(find.textContaining('相關回合：1'), findsOneWidget);
  });
}

/// get 要等 [gate] 才回應的 repository（模擬載入中）；其餘都轉給 [inner]。
class _SlowRepository extends FakeMatchesRepository {
  _SlowRepository(FakeMatchesRepository inner, this.gate)
    : super(match: inner.match);

  final Future<void> gate;

  @override
  Future<GameMatch> get(String id) async {
    await gate;
    return super.get(id);
  }
}
