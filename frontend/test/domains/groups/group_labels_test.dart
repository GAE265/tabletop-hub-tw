// 揪團畫面共用的文字（詳細頁的 Stitch 版面用到的部分）。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/groups/state/group_labels.dart';

import '../../support/fakes.dart';
import 'support.dart';

void main() {
  group('揪團時數', () {
    String duration(Duration length) => groupDurationLabel(
      fakeGroup(
        startAt: taipei(11, 22, 14),
        endAt: taipei(11, 22, 14).add(length),
      ),
    );

    test('整數小時', () {
      expect(duration(const Duration(hours: 4)), '4 小時');
    });

    test('有剩下的分鐘', () {
      expect(duration(const Duration(hours: 1, minutes: 30)), '1 小時 30 分');
    });

    test('不到一小時', () {
      expect(duration(const Duration(minutes: 45)), '45 分鐘');
    });
  });

  group('我在這個揪團的身分', () {
    final base = fakeGroup(startAt: taipei(11, 22), organizerId: 'u-org');

    test('開團主', () {
      expect(myGroupRoleLabel(base, 'u-org'), '開團主');
    });

    test('成員', () {
      expect(myGroupRoleLabel(base.copyWith(myStatus: 'member'), 'u-me'), '成員');
    });

    test('候補', () {
      expect(
        myGroupRoleLabel(base.copyWith(myStatus: 'waitlisted'), 'u-me'),
        '候補',
      );
    });

    test('未報名或沒有登入', () {
      expect(myGroupRoleLabel(base, 'u-me'), '未報名');
      expect(myGroupRoleLabel(base, null), '未報名');
    });
  });
}
