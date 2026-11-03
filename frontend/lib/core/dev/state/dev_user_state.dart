import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/dev_user.dart';
import '../data/dev_users_repository.dart';

/// 從後端取得的測試帳號清單。失敗不自動重試，交給畫面上的「重試」。
final devUsersProvider = FutureProvider<List<DevUser>>(
  (ref) => ref.watch(devUsersRepositoryProvider).list(),
  retry: (_, _) => null,
);

/// 目前選取的測試帳號 id；null 表示用預設（清單中的 player）。
class SelectedDevUserId extends Notifier<String?> {
  @override
  String? build() => null;

  void select(String? id) => state = id;
}

final selectedDevUserIdProvider = NotifierProvider<SelectedDevUserId, String?>(
  SelectedDevUserId.new,
);

/// 目前生效的測試帳號；清單未載入、失敗或為空時為 null。
final currentDevUserProvider = Provider<DevUser?>((ref) {
  final users = ref.watch(devUsersProvider).value;
  if (users == null || users.isEmpty) return null;
  final selectedId = ref.watch(selectedDevUserIdProvider);
  for (final user in users) {
    if (user.id == selectedId) return user;
  }
  for (final user in users) {
    if (user.role == 'player') return user;
  }
  return null;
});

/// `X-Dev-User` 的值：`<user_uuid>:<role>[:<shop_uuid>]`，shop_staff 才帶店家。
String formatDevUserHeader(DevUser user) {
  final base = '${user.id}:${user.role}';
  if (user.role == 'shop_staff' && user.shopId != null) {
    return '$base:${user.shopId}';
  }
  return base;
}

/// 沒有可用身分時為 null（請求不帶標頭，由後端使用預設玩家）。
final devUserHeaderProvider = Provider<String?>((ref) {
  final user = ref.watch(currentDevUserProvider);
  return user == null ? null : formatDevUserHeader(user);
});
