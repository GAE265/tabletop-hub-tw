import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../domains/groups/data/group.dart';
import '../../domains/groups/state/current_user.dart';
import '../../domains/groups/state/group_clock.dart';
import '../../domains/groups/state/group_detail_state.dart';
import '../../domains/groups/state/group_form_state.dart';
import '../../domains/groups/state/groups_calendar_state.dart';
import 'group_form_proto_page.dart';
import 'groups_proto_page.dart';

/// 揪團詳細資料參考畫面：資訊、名單、報名／候補／退出／編輯／取消。
class GroupDetailProtoPage extends ConsumerWidget {
  const GroupDetailProtoPage({required this.groupId, super.key});

  final String groupId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupDetailProvider(groupId));
    final notifier = ref.read(groupDetailProvider(groupId).notifier);
    return Scaffold(
      appBar: AppBar(title: const Text('揪團詳細（參考畫面）')),
      body: state.group.when(
        skipLoadingOnRefresh: false,
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(error is ApiException ? error.message : '發生未知錯誤'),
              ElevatedButton(
                onPressed: notifier.reload,
                child: const Text('重試'),
              ),
            ],
          ),
        ),
        data: (group) => ListView(
          children: [
            _GroupInfo(group: group),
            if (state.message != null) ListTile(title: Text(state.message!)),
            if (state.error != null)
              ListTile(title: Text('錯誤：${state.error!}')),
            _Actions(groupId: groupId, state: state),
            const Divider(),
            ListTile(title: Text('名單（${state.members.length} 人）')),
            for (final member in state.members)
              ListTile(
                title: Text(member.displayName),
                trailing: Text(
                  member.status == 'member'
                      ? (member.userId == group.organizer.id ? '開團主' : '成員')
                      : '候補第 ${member.waitlistPosition} 位',
                ),
              ),
          ],
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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ListTile(
          title: Text(group.title),
          subtitle: Text(groupSlotLabel(group)),
        ),
        ListTile(
          title: const Text('時間'),
          subtitle: Text(
            '${day.year}/${day.month}/${day.day} ${formatTimeRange(clock, group)}',
          ),
        ),
        ListTile(title: const Text('店家'), subtitle: Text(group.shop.name)),
        ListTile(
          title: const Text('開團主'),
          subtitle: Text(group.organizer.displayName),
        ),
        ListTile(
          title: const Text('人數'),
          subtitle: Text(
            '成員 ${group.memberCount}／${group.capacity}，候補 ${group.waitlistCount}',
          ),
        ),
        if (feeLabel(group.fee) case final fee?)
          ListTile(title: const Text('費用'), subtitle: Text(fee)),
        if (group.game != null)
          ListTile(title: const Text('遊戲'), subtitle: Text(group.game!.name)),
        if (group.description != null)
          ListTile(title: const Text('簡介'), subtitle: Text(group.description!)),
      ],
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
    if (state.busy) {
      return const Center(child: CircularProgressIndicator());
    }

    Future<void> confirm(String text, Future<void> Function() action) async {
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          content: Text(text),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('確定'),
            ),
          ],
        ),
      );
      if (ok ?? false) await action();
    }

    return Wrap(
      children: [
        for (final action in actions)
          switch (action) {
            GroupAction.join => ElevatedButton(
              onPressed: notifier.join,
              child: const Text('報名'),
            ),
            GroupAction.joinWaitlist => ElevatedButton(
              onPressed: notifier.join,
              child: const Text('加入候補'),
            ),
            GroupAction.leave => ElevatedButton(
              onPressed: () => confirm('確定要退出這個揪團嗎？', notifier.leave),
              child: const Text('退出'),
            ),
            GroupAction.edit => ElevatedButton(
              onPressed: () {
                final group = state.group.value!;
                ref.read(groupFormProvider.notifier).reset();
                Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => GroupFormProtoPage(
                      groupId: groupId,
                      initial: GroupFormData.fromGroup(
                        group,
                        ref.read(groupClockProvider),
                      ),
                    ),
                  ),
                );
              },
              child: const Text('編輯'),
            ),
            GroupAction.cancel => ElevatedButton(
              onPressed: () => confirm('確定要取消這個揪團嗎？取消後無法復原。', notifier.cancel),
              child: const Text('取消揪團'),
            ),
          },
      ],
    );
  }
}
