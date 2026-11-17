import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/dev/state/dev_user_state.dart';

/// 目前使用者的 id，用來判斷「我是不是開團主」與退出揪團。
///
/// 目前取自開發用的身分切換器；`auth` 完成後只要改這一處，改成從登入狀態取得
/// （design.md D11）。沒有可用的身分時為 null。
final currentUserIdProvider = Provider<String?>(
  (ref) => ref.watch(currentDevUserProvider)?.id,
);
