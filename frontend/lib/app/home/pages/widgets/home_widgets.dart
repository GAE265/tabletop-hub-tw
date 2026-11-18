import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/api/api_exception.dart';
import '../../../../core/layout/breakpoints.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../../../domains/groups/state/group_clock.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_spacing.dart';
import '../../state/upcoming_state.dart';

/// 入口卡片的內容。
class _Entry {
  const _Entry({
    required this.keyName,
    required this.title,
    required this.body,
    required this.route,
    required this.icon,
    required this.tint,
    required this.ink,
  });

  final String keyName;
  final String title;
  final String body;
  final String route;
  final IconData icon;
  final Color tint;
  final Color ink;
}

const _entries = [
  _Entry(
    keyName: 'home-card-advisor',
    title: '今天玩什麼？',
    body: '跟助理聊聊，幫你挑遊戲',
    route: '/games-advisor',
    icon: Icons.casino_outlined,
    tint: AppColors.primaryTint,
    ink: AppColors.primaryText,
  ),
  _Entry(
    keyName: 'home-card-groups',
    title: '找人一起玩',
    body: '開團或加入，額滿可候補',
    route: '/groups',
    icon: Icons.groups_outlined,
    tint: AppColors.sageTint,
    ink: AppColors.sage,
  ),
  _Entry(
    keyName: 'home-card-booking',
    title: '訂個位子',
    body: '挑桌遊店，直接選座位',
    route: '/booking',
    icon: Icons.event_outlined,
    tint: AppColors.amberTint,
    ink: AppColors.amberText,
  ),
  _Entry(
    keyName: 'home-card-rules',
    title: '這遊戲怎麼玩',
    body: '看教學、隨時問規則',
    route: '/rules',
    icon: Icons.menu_book_outlined,
    tint: AppColors.neutralTint,
    ink: AppColors.ink,
  ),
];

/// 四張入口卡片：手機兩欄兩列；平板以上放得下就排成一列，放不下改成兩欄。
class EntryCards extends StatelessWidget {
  const EntryCards({super.key});

  @override
  Widget build(BuildContext context) {
    final mobile = context.screenSize == ScreenSize.mobile;
    final gap = mobile ? AppSpacing.small : AppSpacing.medium;
    return LayoutBuilder(
      builder: (context, constraints) {
        final fitsFour =
            constraints.maxWidth >= 4 * AppSizes.entryCardMinWidth + 3 * gap;
        final columns = !mobile && fitsFour ? 4 : 2;
        return Column(
          children: [
            for (var start = 0; start < _entries.length; start += columns) ...[
              if (start > 0) SizedBox(height: gap),
              IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (var i = start; i < start + columns; i++) ...[
                      if (i > start) SizedBox(width: gap),
                      Expanded(child: _EntryCard(entry: _entries[i])),
                    ],
                  ],
                ),
              ),
            ],
          ],
        );
      },
    );
  }
}

class _EntryCard extends StatelessWidget {
  const _EntryCard({required this.entry});

  final _Entry entry;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Material(
      key: Key(entry.keyName),
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.card),
        side: const BorderSide(color: AppColors.border),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.go(entry.route),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: AppSizes.entryIconBox,
                height: AppSizes.entryIconBox,
                decoration: BoxDecoration(
                  color: entry.tint,
                  borderRadius: BorderRadius.circular(AppRadius.button),
                ),
                child: Icon(entry.icon, color: entry.ink),
              ),
              const SizedBox(height: AppSpacing.large),
              Text(
                entry.title,
                style: textTheme.titleMedium!.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: AppSpacing.xSmall),
              Text(
                entry.body,
                style: textTheme.bodyMedium!.copyWith(
                  color: AppColors.inkMuted,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 「接下來的行程」：載入中、沒有資料、錯誤都只影響這一區。
class UpcomingSection extends ConsumerWidget {
  const UpcomingSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final upcoming = ref.watch(upcomingProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '接下來的行程',
          style: Theme.of(
            context,
          ).textTheme.titleLarge!.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: AppSpacing.small),
        upcoming.when(
          skipLoadingOnRefresh: false,
          loading: () => const Padding(
            key: Key('home-upcoming-loading'),
            padding: EdgeInsets.all(AppSpacing.large),
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (error, _) => _UpcomingError(
            error: error,
            onRetry: () => ref.invalidate(upcomingProvider),
          ),
          data: (items) => items.isEmpty
              ? const _UpcomingEmpty()
              : Column(
                  children: [
                    for (final (i, item) in items.indexed) ...[
                      if (i > 0) const SizedBox(height: AppSpacing.small),
                      _UpcomingRow(key: Key('home-upcoming-$i'), item: item),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}

class _UpcomingRow extends ConsumerWidget {
  const _UpcomingRow({required this.item, super.key});

  final UpcomingItem item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clock = ref.watch(groupClockProvider);
    final textTheme = Theme.of(context).textTheme;
    final status = upcomingStatus(item);
    final subtitle = upcomingSubtitle(item);
    final (tint, ink) = switch (item) {
      UpcomingBooking() => (AppColors.amberTint, AppColors.amberText),
      UpcomingGroup() => (AppColors.sageTint, AppColors.sage),
    };
    return Material(
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.card),
        side: const BorderSide(color: AppColors.border),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.go(upcomingRoute(item)),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.medium,
            vertical: AppSpacing.small,
          ),
          child: Row(
            children: [
              Container(
                width: AppSizes.dateBadge,
                height: AppSizes.dateBadge,
                decoration: BoxDecoration(
                  color: tint,
                  borderRadius: BorderRadius.circular(AppRadius.button),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      upcomingMonthLabel(clock, item),
                      style: textTheme.labelSmall!.copyWith(color: ink),
                    ),
                    Text(
                      upcomingDayLabel(clock, item),
                      style: textTheme.titleMedium!.copyWith(
                        color: ink,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.medium),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      upcomingTitle(clock, item),
                      style: textTheme.titleSmall!.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (subtitle.isNotEmpty)
                      Text(
                        subtitle,
                        style: textTheme.bodyMedium!.copyWith(
                          color: AppColors.inkMuted,
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.small),
              PillBadge(label: status.label, tone: _tone(status)),
            ],
          ),
        ),
      ),
    );
  }
}

PillTone _tone(UpcomingStatus status) => switch (status) {
  UpcomingStatus.confirmed => PillTone.players,
  UpcomingStatus.recruiting => PillTone.duration,
  UpcomingStatus.full => PillTone.neutral,
  UpcomingStatus.waitlisted => PillTone.accent,
};

class _UpcomingEmpty extends StatelessWidget {
  const _UpcomingEmpty();

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return _Panel(
      key: const Key('home-upcoming-empty'),
      children: [
        Text('還沒有接下來的行程', style: textTheme.titleSmall),
        const SizedBox(height: AppSpacing.xSmall),
        Text(
          '揪個團或訂個位子，行程就會出現在這裡。',
          style: textTheme.bodyMedium!.copyWith(color: AppColors.inkMuted),
        ),
        const SizedBox(height: AppSpacing.medium),
        Wrap(
          spacing: AppSpacing.small,
          runSpacing: AppSpacing.small,
          children: [
            FilledButton.icon(
              key: const Key('home-empty-groups'),
              onPressed: () => context.go('/groups'),
              icon: const Icon(Icons.groups_outlined),
              label: const Text('找人一起玩'),
            ),
            OutlinedButton.icon(
              key: const Key('home-empty-booking'),
              onPressed: () => context.go('/booking'),
              icon: const Icon(Icons.event_outlined),
              label: const Text('訂個位子'),
            ),
          ],
        ),
      ],
    );
  }
}

class _UpcomingError extends StatelessWidget {
  const _UpcomingError({required this.error, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final message = switch (error) {
      ApiException(:final message) => '行程載入失敗：$message',
      _ => '行程載入失敗，請稍後再試',
    };
    return _Panel(
      key: const Key('home-upcoming-error'),
      children: [
        Text(
          message,
          style: Theme.of(
            context,
          ).textTheme.bodyMedium!.copyWith(color: AppColors.error),
        ),
        const SizedBox(height: AppSpacing.small),
        OutlinedButton.icon(
          key: const Key('home-upcoming-retry'),
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('重試'),
        ),
      ],
    );
  }
}

/// 行程區的空狀態與錯誤共用的框。
class _Panel extends StatelessWidget {
  const _Panel({required this.children, super.key});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(AppRadius.card),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: children,
        ),
      ),
    );
  }
}
