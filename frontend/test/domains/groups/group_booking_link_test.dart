// 開團主按「訂位」：產生帶好揪團資料的訂位頁網址。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/groups/state/group_booking_link.dart';

import '../../support/fakes.dart';
import 'support.dart';

void main() {
  final clock = FixedOffsetClock(nowUtc);

  test('帶入店家、台灣日期與時間、預計人數與揪團名稱', () {
    final group = fakeGroup(
      title: '123',
      startAt: taipei(11, 21, 19),
      endAt: taipei(11, 21, 23),
      capacity: 2,
      memberCount: 1,
      shopId: 's-b',
    );
    final link = groupBookingLink(clock, group);
    expect(link.path, '/booking');
    expect(link.queryParameters, {
      'shop_id': 's-b',
      'date': '2026-11-21',
      'start': '19:00',
      'end': '23:00',
      'party_size': '2',
      'requests': '揪團：123',
    });
  });

  test('時間不在半點上：開始往前、結束往後取到半點', () {
    final group = fakeGroup(
      startAt: taipei(11, 21, 19, 10),
      endAt: taipei(11, 21, 22, 50),
    );
    final query = groupBookingLink(clock, group).queryParameters;
    expect(query['start'], '19:00');
    expect(query['end'], '23:00');
  });

  test('已經在半點上：時間不變', () {
    final group = fakeGroup(
      startAt: taipei(11, 21, 13, 30),
      endAt: taipei(11, 21, 15, 30),
    );
    final query = groupBookingLink(clock, group).queryParameters;
    expect(query['start'], '13:30');
    expect(query['end'], '15:30');
  });

  test('結束時間超過當天最後一格：取當天最後一格 23:30', () {
    final group = fakeGroup(
      startAt: taipei(11, 21, 21),
      endAt: taipei(11, 21, 23, 45),
    );
    expect(groupBookingLink(clock, group).queryParameters['end'], '23:30');
  });
}
