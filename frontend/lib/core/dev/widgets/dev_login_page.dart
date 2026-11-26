import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../layout/breakpoints.dart';
import '../data/dev_user.dart';
import '../state/dev_user_state.dart';

/// 開發用登入畫面：選一個測試帳號 → 登入 → 設定目前身分 → 回首頁。
///
/// **不是真的認證。** 和右上角的 [DevUserSwitcher] 是同一件事的兩個外觀：
/// 一樣讀 `GET /api/v1/dev/users`、一樣寫 [selectedDevUserIdProvider]，
/// 只在 `devUserEnabled` 時註冊路由。真正的帳密登入由 `auth` 完成後替換。
class DevLoginPage extends ConsumerStatefulWidget {
  const DevLoginPage({super.key});

  @override
  ConsumerState<DevLoginPage> createState() => _DevLoginPageState();
}

class _DevLoginPageState extends ConsumerState<DevLoginPage> {
  String? _selectedId;

  void _login() {
    ref.read(selectedDevUserIdProvider.notifier).select(_selectedId);
    context.go('/');
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final users = ref.watch(devUsersProvider);
    return Scaffold(
      key: const Key('dev-login-page'),
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.large),
            child: ConstrainedBox(
              // 桌機也維持手機寬，清單不會拉得太長
              constraints: const BoxConstraints(maxWidth: mobileMaxWidth),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    '遊任有娛',
                    style: textTheme.headlineMedium,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: AppSpacing.small),
                  Text(
                    '選擇要登入的帳號',
                    style: textTheme.bodyMedium!.copyWith(
                      color: AppColors.inkMuted,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: AppSpacing.large),
                  users.when(
                    loading: () => const Center(
                      key: Key('dev-login-loading'),
                      child: CircularProgressIndicator(),
                    ),
                    error: (_, _) => Column(
                      key: const Key('dev-login-error'),
                      children: [
                        Text('無法載入測試帳號', style: textTheme.bodyLarge),
                        const SizedBox(height: AppSpacing.small),
                        TextButton(
                          key: const Key('dev-login-retry'),
                          onPressed: () => ref.invalidate(devUsersProvider),
                          child: const Text('重試'),
                        ),
                      ],
                    ),
                    data: (list) => list.isEmpty
                        ? Text(
                            '尚無測試帳號，請先執行 seed',
                            style: textTheme.bodyLarge,
                            textAlign: TextAlign.center,
                          )
                        : _UserPicker(
                            users: list,
                            selectedId: _selectedId,
                            onSelected: (id) =>
                                setState(() => _selectedId = id),
                            onSubmit: _selectedId == null ? null : _login,
                          ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _UserPicker extends StatelessWidget {
  const _UserPicker({
    required this.users,
    required this.selectedId,
    required this.onSelected,
    required this.onSubmit,
  });

  final List<DevUser> users;
  final String? selectedId;
  final ValueChanged<String?> onSelected;
  final VoidCallback? onSubmit;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: RadioGroup<String>(
            groupValue: selectedId,
            onChanged: onSelected,
            child: Column(
              children: [
                for (final user in users)
                  RadioListTile<String>(
                    key: Key('dev-login-user-${user.id}'),
                    value: user.id,
                    title: Text(user.displayName),
                    subtitle: Text(user.role),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.large),
        FilledButton(
          key: const Key('dev-login-submit'),
          onPressed: onSubmit,
          child: const Text('登入'),
        ),
      ],
    );
  }
}
