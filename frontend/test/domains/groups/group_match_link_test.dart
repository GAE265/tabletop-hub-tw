// 揪團「填入戰績」：產生帶好揪團資料的戰績頁網址。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/state/group_match_link.dart';

import '../../support/fakes.dart';
import 'support.dart';

void main() {
  final clock = FixedOffsetClock(nowUtc);

  test('帶入第一款遊戲、台灣日期、店家與揪團', () {
    final group = fakeGroup(
      id: 'g-9',
      // 台灣 11/22 00:30＝UTC 11/21 16:30，日期要用台灣的 11/22
      startAt: taipei(11, 22, 0, 30),
      shopId: 's-b',
      games: const [
        GameRef(id: 2, name: '阿不思學院'),
        GameRef(id: 3, name: '馬可波羅'),
      ],
    );
    final link = groupMatchLink(clock, group);
    expect(link.path, '/matches');
    expect(link.queryParameters, {
      'game_id': '2',
      'date': '2026-11-22',
      'shop_id': 's-b',
      'group_id': 'g-9',
    });
  });

  test('揪團沒選遊戲：不帶遊戲', () {
    final group = fakeGroup(startAt: taipei(11, 21));
    final query = groupMatchLink(clock, group).queryParameters;
    expect(query.containsKey('game_id'), isFalse);
    expect(query['group_id'], 'g-1');
    expect(query['shop_id'], 's-shop');
  });
}
