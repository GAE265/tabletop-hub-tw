import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/thick_widgets.dart';
import '../../../../core/api/api_exception.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../data/group.dart';
import '../../state/group_clock.dart';
import '../../state/group_labels.dart';
import '../../state/groups_calendar_state.dart';

/// 名額狀態的膠囊標籤：有空位用綠色、額滿用琥珀色、已取消或已結束用灰色。
class GroupSlotBadge extends StatelessWidget {
  const GroupSlotBadge({required this.group, super.key});

  final Group group;

  @override
  Widget build(BuildContext context) {
    final tone = switch (group) {
      Group(status: 'cancelled' || 'ended') => PillTone.neutral,
      Group(remainingSlots: <= 0) => PillTone.duration,
      _ => PillTone.players,
    };
    return PillBadge(label: groupSlotLabel(group), tone: tone);
  }
}

/// 「已成團」標籤：開放中且開團主已確定成團時顯示（add-groups-notifications）。
class GroupConfirmedBadge extends StatelessWidget {
  const GroupConfirmedBadge({super.key});

  @override
  Widget build(BuildContext context) => const PillBadge(
    label: '已成團',
    tone: PillTone.players,
    icon: Icons.check_circle_outline,
  );
}

/// 當日列表中的一筆揪團（Stitch 版面）：有厚度的卡片，點整張進詳細頁，按住時往下沉。
class GroupCard extends ConsumerWidget {
  const GroupCard({required this.group, required this.onTap, super.key});

  final Group group;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clock = ref.watch(groupClockProvider);
    final text = Theme.of(context).textTheme;
    final fee = feeLabel(group.fee);
    final description = group.description?.trim() ?? '';
    final muted = text.bodyMedium!.copyWith(color: AppColors.inkMuted);
    const inset = AppSpacing.medium + AppSpacing.xSmall;
    return ThickCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(inset),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    if (isConfirmedOpen(group)) const GroupConfirmedBadge(),
                    const Spacer(),
                    GroupSlotBadge(group: group),
                  ],
                ),
                if (group.games.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.small),
                  Wrap(
                    spacing: AppSpacing.small,
                    runSpacing: AppSpacing.xSmall,
                    children: [
                      for (final game in group.games)
                        PillBadge(
                          label: game.name,
                          icon: Icons.casino_outlined,
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: AppSpacing.small),
                Text(
                  group.title,
                  style: text.headlineSmall!.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (description.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.xSmall),
                  Text(
                    description,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: muted,
                  ),
                ],
                const SizedBox(height: AppSpacing.medium),
                // 時間與店家放在米白的小框裡
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: AppColors.backgroundAlt,
                    borderRadius: BorderRadius.circular(AppRadius.button),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(
                      AppSpacing.small + AppSpacing.xSmall,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        IconText(
                          icon: Icons.schedule,
                          text: formatTimeRange(clock, group),
                        ),
                        const SizedBox(height: AppSpacing.small),
                        IconText(
                          icon: Icons.storefront_outlined,
                          text: group.shop.name,
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.medium),
                Row(
                  children: [
                    CircleAvatar(
                      radius: AppSizes.avatar / 2,
                      backgroundColor: AppColors.sage,
                      foregroundColor: AppColors.surface,
                      child: Text(_initial(group.organizer.displayName)),
                    ),
                    const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
                    Expanded(
                      child: Text(
                        '開團主：${group.organizer.displayName}',
                        style: text.titleSmall,
                      ),
                    ),
                    if (fee != null)
                      Text(
                        fee,
                        style: text.titleMedium!.copyWith(
                          color: AppColors.primaryText,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
          const DashedLine(),
          ColoredBox(
            color: AppColors.backgroundAlt,
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: inset,
                vertical: AppSpacing.small + AppSpacing.xSmall,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(
                    '查看詳情',
                    style: text.labelLarge!.copyWith(
                      color: AppColors.primaryText,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.xSmall),
                  const Icon(
                    Icons.arrow_forward,
                    size: AppSizes.inlineIcon,
                    color: AppColors.primaryText,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 頭像上的字：名字的第一個字。
String _initial(String name) => name.isEmpty ? '？' : name.characters.first;

/// 操作結果或錯誤訊息的提示條。
class StatusBanner extends StatelessWidget {
  const StatusBanner({required this.text, this.isError = false, super.key});

  final String text;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final background = isError
        ? scheme.errorContainer
        : scheme.secondaryContainer;
    final foreground = isError
        ? scheme.onErrorContainer
        : scheme.onSecondaryContainer;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(AppRadius.button),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Row(
          children: [
            Icon(
              isError ? Icons.error_outline : Icons.check_circle_outline,
              color: foreground,
            ),
            const SizedBox(width: AppSpacing.small),
            Expanded(
              child: Text(
                text,
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium!.copyWith(color: foreground),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 載入失敗：錯誤訊息與「重試」按鈕。
class LoadError extends StatelessWidget {
  const LoadError({required this.error, required this.onRetry, super.key});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.large),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            error is ApiException ? (error as ApiException).message : '發生未知錯誤',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.medium),
          FilledButton(onPressed: onRetry, child: const Text('重試')),
        ],
      ),
    );
  }
}

/// 載入中。
class LoadingIndicator extends StatelessWidget {
  const LoadingIndicator({super.key});

  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.all(AppSpacing.large),
    child: Center(child: CircularProgressIndicator()),
  );
}
