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
import '../state/group_clock.dart';
import '../state/group_detail_state.dart';
import '../state/group_form_state.dart';
import '../state/group_labels.dart';
import '../state/group_match_link.dart';
import 'group_form_page.dart';
import 'widgets/group_widgets.dart';

/// 揪團詳細資料（Stitch 版面，docs/ui/stitch/）：
///
/// - 資訊卡：狀態、時數、名稱與分項（聚會時間、桌遊店家、包含桌遊、費用）。
/// - 開團主卡、揪團說明卡（有簡介時）。
/// - 操作台：報名以外的操作（編輯／訂位／填入戰績／確定成團／退出／取消揪團）與我的身分。
/// - 名單：成員與候補分開，自己標「我」，有空位時顯示剩幾個。
/// - 底部固定報名列：還沒報名時才有（報名／加入候補）。
///
/// 木紋背景，文字放在卡片上；手機的浮動導覽列蓋住的高度（MediaQuery 底部 padding）留在畫面最下面。
class GroupDetailPage extends ConsumerWidget {
  const GroupDetailPage({required this.groupId, super.key});

  final String groupId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(groupDetailProvider(groupId));
    final notifier = ref.read(groupDetailProvider(groupId).notifier);
    final userId = ref.watch(currentUserIdProvider);
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    final bottomInset = MediaQuery.paddingOf(context).bottom;

    Widget content(Group group) {
      final actions = state.actionsFor(userId);
      final joinAction = actions
          .where((a) => a == GroupAction.join || a == GroupAction.joinWaitlist)
          .firstOrNull;
      final tiles = actions
          .where((a) => a != GroupAction.join && a != GroupAction.joinWaitlist)
          .toList();
      const gap = SizedBox(height: AppSpacing.medium);
      final list = ListView(
        padding: EdgeInsets.fromLTRB(
          AppSpacing.medium,
          AppSpacing.medium,
          AppSpacing.medium,
          // 有底部報名列時，導覽列的高度由報名列留
          AppSpacing.medium + (joinAction == null ? bottomInset : 0),
        ),
        children: [
          _GroupInfo(group: group),
          gap,
          _Organizer(group: group),
          if (group.description?.trim() case final description?
              when description.isNotEmpty) ...[
            gap,
            _Description(text: description),
          ],
          if (state.message case final message?) ...[
            gap,
            StatusBanner(text: message),
          ],
          if (state.error case final error?) ...[
            gap,
            StatusBanner(text: error, isError: true),
          ],
          if (tiles.isNotEmpty) ...[
            gap,
            _ActionDesk(
              groupId: groupId,
              state: state,
              tiles: tiles,
              role: myGroupRoleLabel(group, userId),
              // 有底部報名列時，處理中的轉圈顯示在報名列
              showBusy: joinAction == null,
            ),
          ],
          gap,
          _Members(group: group, members: state.members, userId: userId),
        ],
      );
      return Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: Column(
            children: [
              Expanded(child: list),
              if (joinAction != null)
                _JoinBar(
                  group: group,
                  waitlist: joinAction == GroupAction.joinWaitlist,
                  busy: state.busy,
                  onJoin: state.busy ? null : notifier.join,
                  bottomInset: bottomInset,
                ),
            ],
          ),
        ),
      );
    }

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
      data: content,
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

/// 有厚度卡片的標準內距。
const _inset = EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall);

/// 卡片標題的樣式。
TextStyle _cardTitle(BuildContext context) => Theme.of(
  context,
).textTheme.headlineSmall!.copyWith(fontWeight: FontWeight.w700);

class _GroupInfo extends ConsumerWidget {
  const _GroupInfo({required this.group});

  final Group group;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final clock = ref.watch(groupClockProvider);
    final day = clock.toLocal(group.startAt);
    final fee = feeLabel(group.fee);
    return ThickCard(
      key: const Key('group-info'),
      child: Padding(
        padding: _inset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: AppSpacing.small,
              runSpacing: AppSpacing.xSmall,
              children: [
                if (isConfirmedOpen(group)) const GroupConfirmedBadge(),
                GroupSlotBadge(group: group),
                PillBadge(
                  label: '${group.memberCount}／${group.capacity} 人',
                  tone: PillTone.players,
                  icon: Icons.group_outlined,
                ),
                PillBadge(
                  label: groupDurationLabel(group),
                  tone: PillTone.duration,
                  icon: Icons.schedule,
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              group.title,
              style: Theme.of(
                context,
              ).textTheme.headlineMedium!.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: AppSpacing.medium),
            // 分項放在米白的小框裡
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
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _InfoItem(
                      icon: Icons.event_outlined,
                      label: '聚會時間',
                      child: _value(
                        context,
                        '${formatDate(day)}（${weekdayLabel(day)}） '
                        '${formatTimeRange(clock, group)}',
                      ),
                    ),
                    _InfoItem(
                      icon: Icons.storefront_outlined,
                      label: '桌遊店家',
                      child: _value(context, group.shop.name),
                    ),
                    if (group.games.isNotEmpty)
                      _InfoItem(
                        icon: Icons.casino_outlined,
                        label: '包含桌遊',
                        child: Wrap(
                          spacing: AppSpacing.small,
                          runSpacing: AppSpacing.xSmall,
                          children: [
                            for (final game in group.games)
                              PillBadge(label: game.name),
                          ],
                        ),
                      ),
                    if (fee != null)
                      _InfoItem(
                        icon: Icons.payments_outlined,
                        label: '費用',
                        child: _value(context, fee),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _value(BuildContext context, String text) => Text(
    text,
    style: Theme.of(
      context,
    ).textTheme.titleSmall!.copyWith(fontWeight: FontWeight.w700),
  );
}

/// 一個分項：左邊圖示方塊，右邊小標與內容。
class _InfoItem extends StatelessWidget {
  const _InfoItem({
    required this.icon,
    required this.label,
    required this.child,
  });

  final IconData icon;
  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xSmall),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: AppSizes.avatar,
            height: AppSizes.avatar,
            decoration: BoxDecoration(
              color: AppColors.primaryTint,
              borderRadius: BorderRadius.circular(AppRadius.button),
            ),
            child: Icon(
              icon,
              size: AppSizes.inlineIcon,
              color: AppColors.primaryText,
            ),
          ),
          const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: AppSpacing.xSmall / 2),
                child,
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 頭像：名字的第一個字。
class _Avatar extends StatelessWidget {
  const _Avatar({required this.name, required this.color});

  final String name;
  final Color color;

  @override
  Widget build(BuildContext context) => CircleAvatar(
    radius: AppSizes.avatar / 2,
    backgroundColor: color,
    foregroundColor: AppColors.surface,
    child: Text(name.isEmpty ? '？' : name.characters.first),
  );
}

class _Organizer extends StatelessWidget {
  const _Organizer({required this.group});

  final Group group;

  @override
  Widget build(BuildContext context) {
    return ThickCard(
      key: const Key('group-organizer'),
      child: Padding(
        padding: _inset,
        child: Row(
          children: [
            _Avatar(
              name: group.organizer.displayName,
              color: AppColors.primaryText,
            ),
            const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
            Expanded(
              child: Text(
                '開團主：${group.organizer.displayName}',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Description extends StatelessWidget {
  const _Description({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return ThickCard(
      key: const Key('group-description'),
      child: Padding(
        padding: _inset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.campaign_outlined,
                  color: AppColors.primaryText,
                ),
                const SizedBox(width: AppSpacing.small),
                Text('揪團說明', style: _cardTitle(context)),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              text,
              style: Theme.of(
                context,
              ).textTheme.bodyLarge!.copyWith(color: AppColors.inkMuted),
            ),
          ],
        ),
      ),
    );
  }
}

/// 操作台：報名以外的操作排成兩欄方塊，標題旁顯示我的身分。
class _ActionDesk extends ConsumerWidget {
  const _ActionDesk({
    required this.groupId,
    required this.state,
    required this.tiles,
    required this.role,
    required this.showBusy,
  });

  final String groupId;
  final GroupDetailState state;
  final List<GroupAction> tiles;
  final String role;
  final bool showBusy;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(groupDetailProvider(groupId).notifier);
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

    ThickButton tile(GroupAction action) => switch (action) {
      GroupAction.edit => ThickButton(
        style: ThickStyle.light,
        onPressed: enabled(edit),
        icon: Icons.edit_outlined,
        label: '編輯',
        subtitle: '修改時間、人數與說明',
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
        subtitle: '帶著揪團資料去訂位',
      ),
      GroupAction.recordMatch => ThickButton(
        style: ThickStyle.light,
        onPressed: enabled(
          () => context.go(groupMatchLink(state.group.value!).toString()),
        ),
        icon: Icons.emoji_events_outlined,
        label: '填入戰績',
        subtitle: '記錄這一局的結果',
      ),
      GroupAction.confirm => ThickButton(
        buttonKey: const Key('group-confirm'),
        style: ThickStyle.dark,
        onPressed: enabled(
          () => confirm('確定成團後會通知所有成員，之後不能取消成團。確定嗎？', notifier.confirm),
        ),
        icon: Icons.check_circle_outline,
        label: '確定成團',
        subtitle: '人夠了就按，大家會收到通知',
      ),
      GroupAction.confirmed => const ThickButton(
        buttonKey: Key('group-confirmed'),
        style: ThickStyle.dark,
        onPressed: null,
        icon: Icons.check_circle,
        label: '已成團',
        subtitle: '成員都收到通知了',
      ),
      GroupAction.leave => ThickButton(
        style: ThickStyle.danger,
        onPressed: enabled(() => confirm('確定要退出這個揪團嗎？', notifier.leave)),
        icon: Icons.logout,
        label: '退出',
        subtitle: '名額會讓給候補',
      ),
      GroupAction.cancel => ThickButton(
        style: ThickStyle.danger,
        onPressed: enabled(
          () => confirm('確定要取消這個揪團嗎？取消後無法復原。', notifier.cancel),
        ),
        icon: Icons.event_busy_outlined,
        label: '取消揪團',
        subtitle: '解散並通知成員與候補',
      ),
      // 報名與加入候補在底部固定列，不會出現在這裡
      GroupAction.join ||
      GroupAction.joinWaitlist => throw StateError('報名不在操作台'),
    };

    final text = Theme.of(context).textTheme;
    const spacing = AppSpacing.small + AppSpacing.xSmall;
    return ThickCard(
      key: const Key('group-actions'),
      child: Padding(
        padding: _inset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(child: Text('團務操作', style: _cardTitle(context))),
                if (showBusy && state.busy) ...[
                  const SizedBox.square(
                    dimension: AppSizes.inlineIcon,
                    child: CircularProgressIndicator(),
                  ),
                  const SizedBox(width: AppSpacing.small),
                ],
                Text(
                  '我的身分：$role',
                  style: text.bodyMedium!.copyWith(color: AppColors.inkMuted),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.medium),
            LayoutBuilder(
              builder: (context, constraints) {
                final width = (constraints.maxWidth - spacing) / 2;
                return Wrap(
                  spacing: spacing,
                  runSpacing: spacing,
                  children: [
                    for (final action in tiles)
                      SizedBox(width: width, child: tile(action)),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

/// 名單：成員與候補分開，自己標「我」，有空位時顯示剩幾個。
class _Members extends StatelessWidget {
  const _Members({
    required this.group,
    required this.members,
    required this.userId,
  });

  final Group group;
  final List<GroupMember> members;
  final String? userId;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final joined = members.where((m) => m.status == 'member').toList();
    final waiting = members.where((m) => m.status != 'member').toList();
    final openSlots = group.status == 'open' ? group.remainingSlots : 0;

    Widget row(GroupMember member) {
      final organizer = member.userId == group.organizer.id;
      return Padding(
        padding: const EdgeInsets.only(
          top: AppSpacing.small + AppSpacing.xSmall,
        ),
        child: Row(
          children: [
            _Avatar(
              name: member.displayName,
              color: organizer
                  ? AppColors.primaryText
                  : member.status == 'member'
                  ? AppColors.sage
                  : AppColors.inkMuted,
            ),
            const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
            Expanded(
              child: Row(
                children: [
                  Flexible(
                    child: Text(member.displayName, style: text.titleSmall),
                  ),
                  if (member.userId == userId) ...[
                    const SizedBox(width: AppSpacing.small),
                    const PillBadge(label: '我', tone: PillTone.accent),
                  ],
                ],
              ),
            ),
            if (member.status == 'member')
              PillBadge(
                label: organizer ? '開團主' : '成員',
                tone: organizer ? PillTone.accent : PillTone.players,
              )
            else
              PillBadge(
                label: '候補第 ${member.waitlistPosition} 位',
                tone: PillTone.duration,
              ),
          ],
        ),
      );
    }

    return ThickCard(
      key: const Key('group-members'),
      child: Padding(
        padding: _inset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('名單（${joined.length} 人）', style: _cardTitle(context)),
            for (final member in joined) row(member),
            if (openSlots > 0) ...[
              const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: AppColors.primaryTint,
                  borderRadius: BorderRadius.circular(AppRadius.button),
                  border: Border.all(color: AppColors.cardEdge),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(
                    AppSpacing.small + AppSpacing.xSmall,
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.event_seat_outlined,
                        color: AppColors.primaryText,
                      ),
                      const SizedBox(width: AppSpacing.small),
                      Text(
                        '尚有 $openSlots 個空位',
                        style: text.titleSmall!.copyWith(
                          color: AppColors.primaryText,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
            if (waiting.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.large),
              Row(
                children: [
                  const Icon(Icons.hourglass_empty, color: AppColors.amberText),
                  const SizedBox(width: AppSpacing.small),
                  Text('候補（${waiting.length} 人等待中）', style: text.titleMedium),
                ],
              ),
              for (final member in waiting) row(member),
            ],
          ],
        ),
      ),
    );
  }
}

/// 底部固定報名列：左邊費用與名額，右邊「報名」或「加入候補」。
class _JoinBar extends StatelessWidget {
  const _JoinBar({
    required this.group,
    required this.waitlist,
    required this.busy,
    required this.onJoin,
    required this.bottomInset,
  });

  final Group group;
  final bool waitlist;
  final bool busy;
  final VoidCallback? onJoin;

  /// 手機浮動導覽列蓋住的高度：報名列要停在它上方。
  final double bottomInset;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final fee = switch (group.fee) {
      null => null,
      0 => '免費參加',
      final fee => '每人 \$$fee',
    };
    return Padding(
      key: const Key('group-join-bar'),
      padding: EdgeInsets.fromLTRB(
        AppSpacing.medium,
        AppSpacing.small,
        AppSpacing.medium,
        AppSpacing.medium + bottomInset,
      ),
      child: ThickCard(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.small + AppSpacing.xSmall),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (fee != null)
                      Text(
                        fee,
                        style: text.titleMedium!.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    Text(
                      waitlist ? '已額滿' : '剩 ${group.remainingSlots} 席',
                      style: text.bodyMedium!.copyWith(
                        color: AppColors.primaryText,
                      ),
                    ),
                  ],
                ),
              ),
              if (busy) ...[
                const CircularProgressIndicator(),
                const SizedBox(width: AppSpacing.small),
              ],
              ThickButton(
                style: ThickStyle.primary,
                onPressed: onJoin,
                label: waitlist ? '加入候補' : '報名',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
