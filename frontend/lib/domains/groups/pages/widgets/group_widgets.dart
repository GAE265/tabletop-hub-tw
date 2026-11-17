import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_spacing.dart';
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

/// 當日列表中的一筆揪團。
class GroupCard extends ConsumerWidget {
  const GroupCard({required this.group, required this.onTap, super.key});

  final Group group;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clock = ref.watch(groupClockProvider);
    final text = Theme.of(context).textTheme;
    final fee = feeLabel(group.fee);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: Text(group.title, style: text.titleMedium)),
                  const SizedBox(width: AppSpacing.small),
                  GroupSlotBadge(group: group),
                ],
              ),
              const SizedBox(height: AppSpacing.small),
              Wrap(
                spacing: AppSpacing.small,
                runSpacing: AppSpacing.xSmall,
                children: [
                  PillBadge(
                    label: formatTimeRange(clock, group),
                    tone: PillTone.duration,
                    icon: Icons.schedule,
                  ),
                  for (final game in group.games)
                    PillBadge(label: game.name, icon: Icons.casino_outlined),
                  if (fee != null) PillBadge(label: fee, tone: PillTone.accent),
                ],
              ),
              const SizedBox(height: AppSpacing.small),
              Text(group.shop.name, style: text.bodyMedium),
              Text('開團主：${group.organizer.displayName}', style: text.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}

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
