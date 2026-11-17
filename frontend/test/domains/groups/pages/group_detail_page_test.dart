// 正式揪團詳細頁（spec：groups-calendar-page 的「報名、候補與退出」）。
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/pages/group_detail_page.dart';

import '../../../support/fakes.dart';
import '../support.dart';
import 'page_support.dart';

FakeGroupsRepository repoWith({
  int memberCount = 1,
  int waitlistCount = 0,
  String status = 'open',
  String? myStatus,
}) => FakeGroupsRepository(
  groups: [
    fakeGroup(
      id: 'g-1',
      title: '週末輕策略',
      startAt: taipei(11, 14, 19),
      memberCount: memberCount,
      waitlistCount: waitlistCount,
      status: status,
      myStatus: myStatus,
      fee: 150,
    ),
  ],
);

Finder button(String label) =>
    find.ancestor(of: find.text(label), matching: find.byType(FilledButton));

void main() {
  testWidgets('顯示揪團資訊', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(),
    );
    expect(find.byKey(const Key('group-detail-page')), findsOneWidget);
    expect(find.text('週末輕策略'), findsWidgets);
    expect(find.text('測試桌遊店'), findsOneWidget);
    expect(find.text('開團主：開團主'), findsOneWidget);
    expect(find.text('\$150／人'), findsOneWidget);
    expect(find.text('剩 3 位'), findsOneWidget);
  });

  testWidgets('報名成功：顯示「報名成功」，按鈕變成「退出」', (tester) async {
    final repo = repoWith();
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('報名'));
    await tester.pumpAndSettle();
    expect(repo.joinCalls, ['g-1']);
    expect(find.text('報名成功'), findsOneWidget);
    expect(button('退出'), findsOneWidget);
  });

  testWidgets('額滿：按「加入候補」，顯示候補順位', (tester) async {
    final repo = repoWith(memberCount: 4, waitlistCount: 1)
      ..joinResult = const JoinResult(
        userId: 'u-player',
        status: 'waitlisted',
        waitlistPosition: 2,
      );
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('加入候補'));
    await tester.pumpAndSettle();
    expect(find.text('已加入候補，目前第 2 位'), findsOneWidget);
    expect(button('退出'), findsOneWidget);
  });

  testWidgets('退出：確認後呼叫 API，按鈕變回「報名」', (tester) async {
    final repo = repoWith(memberCount: 2, myStatus: 'member');
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('退出'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('確定'));
    await tester.pumpAndSettle();
    expect(repo.removeCalls, [('g-1', 'u-player')]);
    expect(button('報名'), findsOneWidget);
  });

  testWidgets('操作失敗：顯示後端訊息，按鈕恢復可按', (tester) async {
    final repo = repoWith()
      ..actionError = const ApiException(
        code: 'GROUP_CLOSED',
        message: '這個揪團已經結束或取消',
        statusCode: 409,
      );
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('報名'));
    await tester.pumpAndSettle();
    expect(find.text('這個揪團已經結束或取消'), findsOneWidget);
    expect(tester.widget<FilledButton>(button('報名')).onPressed, isNotNull);
  });

  testWidgets('操作進行中：按鈕停用，不能重複送出', (tester) async {
    final repo = repoWith()..actionGate = Completer<void>();
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
    );
    await tester.tap(button('報名'));
    await tester.pump();
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(tester.widget<FilledButton>(button('報名')).onPressed, isNull);
    await tester.tap(button('報名'), warnIfMissed: false);
    expect(repo.joinCalls, ['g-1']);

    repo.actionGate!.complete();
    await tester.pumpAndSettle();
  });

  testWidgets('開團主只看到「編輯」與「取消揪團」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(myStatus: 'member'),
      userId: 'u-org',
    );
    expect(find.text('編輯'), findsOneWidget);
    expect(find.text('取消揪團'), findsOneWidget);
    expect(find.text('報名'), findsNothing);
    expect(find.text('退出'), findsNothing);
  });

  testWidgets('開團主取消揪團：確認後送出 cancelled', (tester) async {
    final repo = repoWith(myStatus: 'member');
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repo,
      userId: 'u-org',
    );
    await tester.tap(find.text('取消揪團'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('確定'));
    await tester.pumpAndSettle();
    expect(repo.updateCalls, [
      ('g-1', {'status': 'cancelled'}),
    ]);
    expect(find.text('已取消'), findsOneWidget);
  });

  testWidgets('已結束：顯示「已結束」，沒有報名按鈕', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-1'),
      repo: repoWith(status: 'ended'),
    );
    expect(find.text('已結束'), findsOneWidget);
    expect(find.text('報名'), findsNothing);
  });

  testWidgets('載入失敗：顯示錯誤與「重試」', (tester) async {
    await pumpGroupsWidget(
      tester,
      const GroupDetailPage(groupId: 'g-missing'),
      repo: repoWith(),
    );
    expect(find.text('找不到這個揪團'), findsOneWidget);
    expect(find.text('重試'), findsOneWidget);
  });
}
