// 情境對應 openspec/changes/add-groups-calendar/specs/groups-calendar-page/spec.md
// 「開團與編輯表單」
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/groups/state/group_detail_state.dart';
import 'package:tabletop_hub/domains/groups/state/group_form_state.dart';
import 'package:tabletop_hub/domains/groups/state/groups_calendar_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

GroupFormData validData({
  String title = '週末輕策略',
  Duration? startTime = const Duration(hours: 19),
  Duration? endTime = const Duration(hours: 22),
  String capacity = '4',
  String fee = '',
  String gameId = '',
}) {
  return GroupFormData(
    shopId: 's-shop',
    title: title,
    date: DateTime(2026, 11, 21),
    startTime: startTime,
    endTime: endTime,
    capacity: capacity,
    fee: fee,
    gameId: gameId,
  );
}

void main() {
  group('前端驗證', () {
    test('合法的資料沒有錯誤', () {
      expect(validateGroupForm(validData()), isEmpty);
    });

    test('缺少必填欄位', () {
      final errors = validateGroupForm(const GroupFormData());
      expect(errors, {
        'shopId': '請選擇店家',
        'title': '請填寫標題',
        'date': '請選擇日期',
        'startTime': '請選擇開始時間',
        'endTime': '請選擇結束時間',
        'capacity': '人數上限至少 2 人',
      });
    });

    test('標題只有空白也算沒填', () {
      expect(validateGroupForm(validData(title: '  '))['title'], '請填寫標題');
    });

    test('結束時間早於或等於開始時間', () {
      expect(
        validateGroupForm(
          validData(endTime: const Duration(hours: 18)),
        )['endTime'],
        '結束時間要晚於開始時間',
      );
      expect(
        validateGroupForm(
          validData(endTime: const Duration(hours: 19)),
        )['endTime'],
        '結束時間要晚於開始時間',
      );
    });

    test('人數、費用、遊戲 ID 的格式', () {
      expect(
        validateGroupForm(validData(capacity: '1'))['capacity'],
        '人數上限至少 2 人',
      );
      expect(
        validateGroupForm(validData(capacity: 'abc'))['capacity'],
        '人數上限至少 2 人',
      );
      expect(validateGroupForm(validData(fee: '-1'))['fee'], '費用要是 0 以上的整數');
      expect(validateGroupForm(validData(fee: '3.5'))['fee'], '費用要是 0 以上的整數');
      expect(validateGroupForm(validData(gameId: 'x'))['gameId'], '遊戲 ID 要是整數');
    });
  });

  test('缺少必填欄位：不呼叫 API，顯示欄位錯誤', () async {
    final repo = FakeGroupsRepository();
    final container = makeContainer(repo);
    final result = await container
        .read(groupFormProvider.notifier)
        .submit(validData(title: ''));
    expect(result, isNull);
    expect(repo.createCalls, isEmpty);
    expect(container.read(groupFormProvider).fieldErrors['title'], '請填寫標題');
  });

  test('開團成功：台灣時間轉成 UTC 送出，月曆跳到該日', () async {
    final repo = FakeGroupsRepository();
    final container = makeContainer(repo);
    final calendar = container.read(groupsCalendarProvider.notifier);
    await calendar.loaded;

    final created = await container
        .read(groupFormProvider.notifier)
        .submit(validData(fee: '300', gameId: '7'));

    expect(created, isNotNull);
    final input = repo.createCalls.single;
    expect(input.startAt, taipei(11, 21, 19));
    expect(input.endAt, taipei(11, 21, 22));
    expect(input.toJson(), {
      'shop_id': 's-shop',
      'title': '週末輕策略',
      'start_at': '2026-11-21T11:00:00.000Z',
      'end_at': '2026-11-21T14:00:00.000Z',
      'capacity': 4,
      'fee': 300,
      'game_id': 7,
      'description': null,
    });
    await calendar.loaded;
    expect(
      container.read(groupsCalendarProvider).selectedDate,
      DateTime(2026, 11, 21),
    );
    expect(container.read(selectedDayGroupsProvider).map((g) => g.id), [
      created!.id,
    ]);
    expect(container.read(groupFormProvider).submitting, isFalse);
  });

  test('後端驗證失敗：回傳 null 並顯示後端訊息', () async {
    final repo = FakeGroupsRepository()
      ..actionError = const ApiException(
        code: 'GROUP_SHOP_NOT_FOUND',
        message: '找不到這間店家',
        statusCode: 404,
      );
    final container = makeContainer(repo);
    final result = await container
        .read(groupFormProvider.notifier)
        .submit(validData());
    expect(result, isNull);
    final state = container.read(groupFormProvider);
    expect(state.error, '找不到這間店家');
    expect(state.submitting, isFalse);
  });

  test('編輯：送出 PATCH，並重新載入詳細資料', () async {
    final repo = FakeGroupsRepository(
      groups: [fakeGroup(startAt: taipei(11, 21, 19), organizerId: 'u-player')],
    );
    final container = makeContainer(repo);
    container.listen(groupDetailProvider('g-1'), (_, _) {});
    await container.read(groupDetailProvider('g-1').notifier).loaded;

    final updated = await container
        .read(groupFormProvider.notifier)
        .submit(validData(title: '改過的標題'), groupId: 'g-1');

    expect(updated?.title, '改過的標題');
    final (id, changes) = repo.updateCalls.single;
    expect(id, 'g-1');
    expect(changes['title'], '改過的標題');
    expect(changes['start_at'], '2026-11-21T11:00:00.000Z');
    expect(changes.containsKey('shop_id'), isFalse);
    expect(
      container.read(groupDetailProvider('g-1')).group.value?.title,
      '改過的標題',
    );
  });

  test('編輯時帶入現有的值', () {
    final group = fakeGroup(
      startAt: taipei(11, 21, 19, 30),
      endAt: taipei(11, 21, 22),
      fee: 300,
      capacity: 6,
    );
    final data = GroupFormData.fromGroup(group, FixedOffsetClock(nowUtc));
    expect(data.date, DateTime(2026, 11, 21));
    expect(data.startTime, const Duration(hours: 19, minutes: 30));
    expect(data.endTime, const Duration(hours: 22));
    expect((data.capacity, data.fee, data.shopId), ('6', '300', 's-shop'));
  });
}
