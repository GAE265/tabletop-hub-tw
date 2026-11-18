import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/dev/state/dev_user_state.dart';

/// 目前使用者的 id，用來找出「哪一位參加者是我」（確認、退出、顯示按鈕）。
///
/// 目前取自開發用的身分切換器；`auth` 完成後只要改這一處，改成從登入狀態取得。
/// 沒有可用的身分時為 null。
final matchUserIdProvider = Provider<String?>(
  (ref) => ref.watch(currentDevUserProvider)?.id,
);
