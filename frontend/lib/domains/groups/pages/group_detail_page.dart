import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/group.dart';
import '../state/current_user.dart';
import '../state/group_booking_link.dart';
import '../state/group_match_link.dart';
import '../state/group_clock.dart';
import '../state/group_detail_state.dart';
import '../state/group_form_state.dart';
import '../state/group_labels.dart';
import 'group_form_page.dart';
import 'widgets/group_widgets.dart';

/// 揪團詳細資料：資訊、操作按鈕（報名／候補／退出／編輯／訂位／填入戰績／取消）與名單。
///
/// 樣式和揪團月曆相同（Stitch 設計）：木紋背景，文字放在卡片上，按鈕有厚度、按得下去。
/// 手機的浮動導覽列蓋住的高度（MediaQuery 底部 padding）留在捲動內容的最下面。
class GroupDetailPage extends ConsumerWidget {
  const GroupDetailPage({required this.groupId, super.key});

  final String groupId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupDetailProvider(groupId));
    final notifier = ref.read(groupDetailProvider(groupId).notifier);
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    final body = state.group.when(
      skipLoadingOnRefresh: false,
      loading: () => const LoadingIndicator(),
      error: (error, _) => Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: ThickCard(
            child: LoadError(error: error, onRetry: notifier.reload),
          ),
        ),
      ),
      data: (group) => Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: ListView(
            padding: EdgeInsets.fromLTRB(
              AppSpacing.medium,
              AppSpacing.medium,
              AppSpacing.medium,
              AppSpacing.medium + bottomInset,
            ),
            children: [
              _GroupInfo(group: group),
              const SizedBox(height: AppSpacing.medium),
              if (state.message case final message?) ...[
                StatusBanner(text: message),
                const SizedBox(height: AppSpacing.medium),
              ],
              if (state.error case final error?) ...[
                StatusBanner(text: error, isError: true),
                const SizedBox(height: AppSpacing.medium),
              ],
              _Actions(groupId: groupId, state: state),
              const SizedBox(height: AppSpacing.large),
              _Members(group: group, members: state.members),
            ],
          ),
        ),
      ),
    );
    return Scaffold(
      key: const Key('group-detail-page'),
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('揪團詳細'),
        // 放在木紋上，用半透明白底，文字才看得清楚
        backgroundColor: AppColors.headerGlass,
      ),
      body: WoodBackground.isPaintedAbove(context)
          ? body
          : WoodBackground(child: body),
    );
  }
}

class _GroupInfo extends ConsumerWidget {
  const _GroupInfo({required this.group});

  final Group group;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clock = ref.watch(groupClockProvider);
    final day = clock.toLocal(group.startAt);
    final text = Theme.of(context).textTheme;
    final fee = feeLabel(group.fee);
    return ThickCard(
      key: const Key('group-info'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: AppSpacing.small,
              runSpacing: AppSpacing.xSmall,
              children: [
                GroupSlotBadge(group: group),
                PillBadge(
                  label: '${group.memberCount}／${group.capacity} 人',
                  tone: PillTone.players,
                  icon: Icons.group_outlined,
                ),
                if (fee != null) PillBadge(label: fee, tone: PillTone.accent),
              ],
            ),
            if (group.games.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.small),
              Wrap(
                spacing: AppSpacing.small,
                runSpacing: AppSpacing.xSmall,
                children: [
                  for (final game in group.games)
                    PillBadge(label: game.name, icon: Icons.casino_outlined),
                ],
              ),
            ],
            const SizedBox(height: AppSpacing.small),
            Text(
              group.title,
              style: text.headlineMedium!.copyWith(fontWeight: FontWeight.w700),
            ),
            if (group.description case final description?) ...[
              const SizedBox(height: AppSpacing.small),
              Text(
                description,
                style: text.bodyLarge!.copyWith(color: AppColors.inkMuted),
              ),
            ],
            const SizedBox(height: AppSpacing.medium),
            // 時間、店家、開團主、候補放在米白的小框裡
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
                    for (final (i, (icon, label)) in [
                      (
                        Icons.event_outlined,
                        '${formatDate(day)}（${weekdayLabel(day)}） '
                            '${formatTimeRange(clock, group)}',
                      ),
                      (Icons.storefront_outlined, group.shop.name),
                      (
                        Icons.person_outline,
                        '開團主：${group.organizer.displayName}',
                      ),
                      if (group.waitlistCount > 0)
                        (Icons.hourglass_empty, '候補 ${group.waitlistCount} 人'),
                    ].indexed) ...[
                      if (i > 0) const SizedBox(height: AppSpacing.small),
                      IconText(icon: icon, text: label),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Actions extends ConsumerWidget {
  const _Actions({required this.groupId, required this.state});

  final String groupId;
  final GroupDetailState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(groupDetailProvider(groupId).notifier);
    final actions = state.actionsFor(ref.watch(currentUserIdProvider));
    if (actions.isEmpty) return const SizedBox.shrink();
    // 操作進行中：按鈕停用，避免重複送出
    VoidCallback? enabled(VoidCallback action) => state.busy ? null : action;

    Future<void> confirm(String message, Future<void> Function() action) async {
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          content: Text(message),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('確定'),
            ),
          ],
        ),
      );
      if (ok ?? false) await action();
    }

    void edit() {
      ref.read(groupFormProvider.notifier).reset();
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => GroupFormPage(
            groupId: groupId,
            initial: GroupFormData.fromGroup(
              state.group.value!,
              ref.read(groupClockProvider),
            ),
          ),
        ),
      );
    }

    return Wrap(
      spacing: AppSpacing.small + AppSpacing.xSmall,
      runSpacing: AppSpacing.small + AppSpacing.xSmall,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        for (final action in actions)
          switch (action) {
            GroupAction.join => ThickButton(
              style: ThickStyle.primary,
              onPressed: enabled(notifier.join),
              label: '報名',
            ),
            GroupAction.joinWaitlist => ThickButton(
              style: ThickStyle.primary,
              onPressed: enabled(notifier.join),
              label: '加入候補',
            ),
            GroupAction.leave => ThickButton(
              style: ThickStyle.light,
              onPressed: enabled(() => confirm('確定要退出這個揪團嗎？', notifier.leave)),
              label: '退出',
            ),
            GroupAction.edit => ThickButton(
              style: ThickStyle.light,
              onPressed: enabled(edit),
              icon: Icons.edit_outlined,
              label: '編輯',
            ),
            GroupAction.book => ThickButton(
              style: ThickStyle.primary,
              onPressed: enabled(
                () => context.go(
                  groupBookingLink(
                    ref.read(groupClockProvider),
                    state.group.value!,
                  ).toString(),
                ),
              ),
              icon: Icons.event_seat_outlined,
              label: '訂位',
            ),
            GroupAction.recordMatch => ThickButton(
              style: ThickStyle.light,
              onPressed: enabled(
                () => context.go(groupMatchLink(state.group.value!).toString()),
              ),
              icon: Icons.emoji_events_outlined,
              label: '填入戰績',
            ),
            GroupAction.confirm => ThickButton(
              buttonKey: const Key('group-confirm'),
              style: ThickStyle.dark,
              onPressed: enabled(
                () => confirm('確定成團後會通知所有成員，之後不能取消成團。確定嗎？', notifier.confirm),
              ),
              icon: Icons.check_circle_outline,
              label: '確定成團',
            ),
            GroupAction.confirmed => const ThickButton(
              buttonKey: Key('group-confirmed'),
              style: ThickStyle.dark,
              onPressed: null,
              icon: Icons.check_circle,
              label: '已成團',
            ),
            GroupAction.cancel => ThickButton(
              style: ThickStyle.danger,
              onPressed: enabled(
                () => confirm('確定要取消這個揪團嗎？取消後無法復原。', notifier.cancel),
              ),
              label: '取消揪團',
            ),
          },
        if (state.busy) const CircularProgressIndicator(),
      ],
    );
  }
}

class _Members extends StatelessWidget {
  const _Members({required this.group, required this.members});

  final Group group;
  final List<GroupMember> members;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ThickCard(
      key: const Key('group-members'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '名單（${members.length} 人）',
              style: text.headlineSmall!.copyWith(fontWeight: FontWeight.w700),
            ),
            for (final member in members) ...[
              const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
              Row(
                children: [
                  CircleAvatar(
                    radius: AppSizes.avatar / 2,
                    backgroundColor: member.userId == group.organizer.id
                        ? AppColors.primaryText
                        : AppColors.sage,
                    foregroundColor: AppColors.surface,
                    child: Text(
                      member.displayName.isEmpty
                          ? '？'
                          : member.displayName.characters.first,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
                  Expanded(
                    child: Text(member.displayName, style: text.titleSmall),
                  ),
                  if (member.status == 'member')
                    PillBadge(
                      label: member.userId == group.organizer.id ? '開團主' : '成員',
                      tone: member.userId == group.organizer.id
                          ? PillTone.accent
                          : PillTone.players,
                    )
                  else
                    PillBadge(
                      label: '候補第 ${member.waitlistPosition} 位',
                      tone: PillTone.duration,
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
