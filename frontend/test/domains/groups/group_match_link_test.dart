// 揪團「填入戰績」：只帶 group_id 到戰績頁，其餘（名稱、店家、遊戲）由戰績頁讀揪團取得。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/groups/data/group.dart';
import 'package:tabletop_hub/domains/groups/state/group_match_link.dart';

import '../../support/fakes.dart';
import 'support.dart';

void main() {
  test('只帶 group_id，不帶遊戲、日期、店家', () {
    final group = fakeGroup(
      id: 'g-9',
      startAt: taipei(11, 22, 0, 30),
      shopId: 's-b',
      games: const [
        GameRef(id: 2, name: '阿不思學院'),
        GameRef(id: 3, name: '馬可波羅'),
      ],
    );
    final link = groupMatchLink(group);
    expect(link.path, '/matches');
    expect(link.queryParameters, {'group_id': 'g-9'});
    expect(link.toString(), '/matches?group_id=g-9');
  });

  test('揪團沒選遊戲也一樣只帶 group_id', () {
    final group = fakeGroup(startAt: taipei(11, 21));
    expect(groupMatchLink(group).queryParameters, {'group_id': 'g-1'});
  });
}
