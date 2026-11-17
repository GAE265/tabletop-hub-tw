// 正式開團／編輯表單（spec：groups-calendar-page 的「開團與編輯表單」）。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/pages/group_form_page.dart';
import 'package:tabletop_hub/domains/groups/state/group_form_state.dart';

import '../../../support/fakes.dart';
import '../support.dart';
import 'page_support.dart';

final day = DateTime(2026, 11, 20);

GroupFormData valid({Duration end = const Duration(hours: 21)}) =>
    GroupFormData(
      shopId: 's-shop',
      title: '新手教學團',
      date: day,
      startTime: const Duration(hours: 19),
      endTime: end,
      capacity: '4',
    );

/// 從一個首頁 push 表單，才能確認送出成功後有關閉表單。
Widget launcher(GroupFormData initial, {String? groupId}) => Builder(
  builder: (context) => Scaffold(
    body: TextButton(
      onPressed: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => GroupFormPage(initial: initial, groupId: groupId),
        ),
      ),
      child: const Text('open'),
    ),
  ),
);

Future<void> openForm(
  WidgetTester tester,
  FakeGroupsRepository repo,
  GroupFormData initial, {
  String? groupId,
}) async {
  await pumpGroupsWidget(
    tester,
    launcher(initial, groupId: groupId),
    repo: repo,
  );
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

Future<void> submit(WidgetTester tester, String label) async {
  await tester.ensureVisible(find.text(label));
  await tester.tap(find.text(label));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('開團成功：呼叫 API 並關閉表單', (tester) async {
    final repo = FakeGroupsRepository();
    await openForm(tester, repo, valid());
    expect(find.byKey(const Key('group-form-page')), findsOneWidget);
    expect(find.text('2026/11/20'), findsOneWidget);

    await submit(tester, '送出');
    expect(repo.createCalls.single.title, '新手教學團');
    expect(find.byKey(const Key('group-form-page')), findsNothing);
  });

  testWidgets('缺少標題：顯示「請填寫標題」，不呼叫 API', (tester) async {
    final repo = FakeGroupsRepository();
    await openForm(tester, repo, GroupFormData(date: day));
    await submit(tester, '送出');
    expect(find.text('請填寫標題'), findsOneWidget);
    expect(repo.createCalls, isEmpty);
  });

  testWidgets('結束時間早於開始時間：顯示錯誤，不呼叫 API', (tester) async {
    final repo = FakeGroupsRepository();
    await openForm(tester, repo, valid(end: const Duration(hours: 18)));
    await submit(tester, '送出');
    expect(find.text('結束時間要晚於開始時間'), findsOneWidget);
    expect(repo.createCalls, isEmpty);
  });

  testWidgets('後端驗證失敗：保留輸入內容，顯示後端訊息', (tester) async {
    final repo = FakeGroupsRepository()
      ..actionError = const ApiException(
        code: 'SHOP_NOT_FOUND',
        message: '找不到這間店家',
        statusCode: 404,
      );
    await openForm(tester, repo, valid());
    await submit(tester, '送出');
    expect(find.text('找不到這間店家'), findsOneWidget);
    expect(find.text('新手教學團'), findsOneWidget);
    expect(find.byKey(const Key('group-form-page')), findsOneWidget);
  });

  testWidgets('編輯：帶入現有值，按「儲存」', (tester) async {
    final repo = FakeGroupsRepository(
      groups: [fakeGroup(id: 'g-1', startAt: taipei(11, 20, 19))],
    );
    await openForm(
      tester,
      repo,
      valid().copyWith(title: '週末輕策略'),
      groupId: 'g-1',
    );
    expect(find.text('週末輕策略'), findsOneWidget);
    await submit(tester, '儲存');
    expect(repo.updateCalls.single.$1, 'g-1');
  });
}
