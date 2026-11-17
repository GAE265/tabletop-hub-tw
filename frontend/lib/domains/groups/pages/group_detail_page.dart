import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/group.dart';
import '../state/current_user.dart';
import '../state/group_clock.dart';
import '../state/group_detail_state.dart';
import '../state/group_form_state.dart';
import '../state/group_labels.dart';
import 'group_form_page.dart';
import 'widgets/group_widgets.dart';

/// 揪團詳細資料：資訊、操作按鈕（報名／候補／退出／編輯／取消）與名單。
class GroupDetailPage extends ConsumerWidget {
  const GroupDetailPage({required this.groupId, super.key});

  final String groupId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupDetailProvider(groupId));
    final notifier = ref.read(groupDetailProvider(groupId).notifier);
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    return Scaffold(
      key: const Key('group-detail-page'),
      appBar: AppBar(title: const Text('揪團詳細')),
      body: state.group.when(
        skipLoadingOnRefresh: false,
        loading: () => const LoadingIndicator(),
        error: (error, _) => Center(
          child: LoadError(error: error, onRetry: notifier.reload),
        ),
        data: (group) => Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth),
            child: ListView(
              padding: const EdgeInsets.all(AppSpacing.medium),
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
      ),
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
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(group.title, style: text.headlineSmall),
            const SizedBox(height: AppSpacing.small),
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
            const SizedBox(height: AppSpacing.medium),
            _InfoRow(
              icon: Icons.event_outlined,
              text:
                  '${formatDate(day)}（${weekdayLabel(day)}） '
                  '${formatTimeRange(clock, group)}',
            ),
            _InfoRow(icon: Icons.storefront_outlined, text: group.shop.name),
            _InfoRow(
              icon: Icons.person_outline,
              text: '開團主：${group.organizer.displayName}',
            ),
            if (group.waitlistCount > 0)
              _InfoRow(
                icon: Icons.hourglass_empty,
                text: '候補 ${group.waitlistCount} 人',
              ),
            if (group.game case final game?)
              _InfoRow(icon: Icons.casino_outlined, text: game.name),
            if (group.description case final description?) ...[
              const SizedBox(height: AppSpacing.small),
              Text(description, style: text.bodyMedium),
            ],
          ],
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xSmall),
      child: Row(
        children: [
          Icon(icon, color: Theme.of(context).colorScheme.onSurfaceVariant),
          const SizedBox(width: AppSpacing.small),
          Expanded(child: Text(text)),
        ],
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
      spacing: AppSpacing.small,
      runSpacing: AppSpacing.small,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        for (final action in actions)
          switch (action) {
            GroupAction.join => FilledButton(
              onPressed: enabled(notifier.join),
              child: const Text('報名'),
            ),
            GroupAction.joinWaitlist => FilledButton(
              onPressed: enabled(notifier.join),
              child: const Text('加入候補'),
            ),
            GroupAction.leave => FilledButton(
              onPressed: enabled(() => confirm('確定要退出這個揪團嗎？', notifier.leave)),
              child: const Text('退出'),
            ),
            GroupAction.edit => OutlinedButton.icon(
              onPressed: enabled(edit),
              icon: const Icon(Icons.edit_outlined),
              label: const Text('編輯'),
            ),
            GroupAction.cancel => TextButton(
              onPressed: enabled(
                () => confirm('確定要取消這個揪團嗎？取消後無法復原。', notifier.cancel),
              ),
              child: const Text('取消揪團'),
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
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ListTile(
            title: Text(
              '名單（${members.length} 人）',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          for (final member in members)
            ListTile(
              leading: const Icon(Icons.person_outline),
              title: Text(member.displayName),
              trailing: member.status == 'member'
                  ? PillBadge(
                      label: member.userId == group.organizer.id ? '開團主' : '成員',
                      tone: member.userId == group.organizer.id
                          ? PillTone.accent
                          : PillTone.players,
                    )
                  : PillBadge(
                      label: '候補第 ${member.waitlistPosition} 位',
                      tone: PillTone.duration,
                    ),
            ),
        ],
      ),
    );
  }
}
