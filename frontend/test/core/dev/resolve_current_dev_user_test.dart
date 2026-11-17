import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';

import '../../support/fakes.dart';

void main() {
  const users = [fakePlayer, fakeStaff, fakeAdmin];

  test('選取的帳號在清單中：用它', () {
    expect(resolveCurrentDevUser(users, fakeAdmin.id), fakeAdmin);
  });

  test('沒有選取：用清單中的 player', () {
    expect(resolveCurrentDevUser(users, null), fakePlayer);
  });

  test('選取的帳號不在清單中：退回 player', () {
    expect(resolveCurrentDevUser(users, 'u-gone'), fakePlayer);
  });

  test('清單中沒有 player 也沒選到：null', () {
    expect(resolveCurrentDevUser(const [fakeStaff], null), isNull);
  });
}
