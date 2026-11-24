import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/api/api_exception.dart';
import '../../../../core/layout/breakpoints.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../../../domains/groups/state/group_clock.dart';
import '../../../theme/app_colors.dart';
import '../../../theme/app_spacing.dart';
import '../../../theme/thick_widgets.dart';
import '../../state/upcoming_state.dart';

/// 深色大標題卡：「今天想怎麼玩？」。
class HomeHero extends StatelessWidget {
  const HomeHero({super.key = const Key('home-hero')});

  @override
  Widget build(BuildContext context) {
    final mobile = context.screenSize == ScreenSize.mobile;
    final textTheme = Theme.of(context).textTheme;
    return DecoratedBox(
      decoration: thickDecoration(
        color: AppColors.ink,
        edge: AppColors.inkEdge,
        radius: AppRadius.hero,
      ),
      child: Padding(
        padding: EdgeInsets.all(mobile ? AppSpacing.large : AppSpacing.xLarge),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '今天想怎麼玩？',
              style: (mobile ? textTheme.displaySmall : textTheme.displayLarge)!
                  .copyWith(color: AppColors.surface),
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              '找遊戲、揪人、訂位、學規則，一個地方搞定。',
              style: (mobile ? textTheme.bodyLarge : textTheme.titleMedium)!
                  .copyWith(color: AppColors.onInkMuted),
            ),
          ],
        ),
      ),
    );
  }
}

/// 入口卡片的配色：四張各不相同（Stitch 設計）。
class _CardStyle {
  const _CardStyle({
    required this.background,
    required this.title,
    required this.body,
    required this.iconBox,
    required this.iconColor,
    required this.pill,
    required this.pillText,
    required this.arrow,
  });

  final Color background;
  final Color title;
  final Color body;
  final Color iconBox;
  final Color iconColor;
  final Color pill;
  final Color pillText;
  final Color arrow;
}

/// 入口卡片的內容。
class _Entry {
  const _Entry({
    required this.keyName,
    required this.title,
    required this.body,
    required this.route,
    required this.icon,
    required this.goLabel,
    required this.style,
  });

  final String keyName;
  final String title;
  final String body;
  final String route;
  final IconData icon;

  /// 卡片下方的標籤，例如「前往推薦」。
  final String goLabel;
  final _CardStyle style;
}

const _entries = [
  _Entry(
    keyName: 'home-card-advisor',
    title: '今天玩什麼？',
    body: '跟助理聊聊，幫你挑遊戲',
    route: '/games-advisor',
    icon: Icons.casino_outlined,
    goLabel: '前往推薦',
    style: _CardStyle(
      background: AppColors.surface,
      title: AppColors.ink,
      body: AppColors.inkMuted,
      iconBox: AppColors.ink,
      iconColor: AppColors.surface,
      pill: AppColors.primaryTint,
      pillText: AppColors.primaryText,
      arrow: AppColors.primaryText,
    ),
  ),
  _Entry(
    keyName: 'home-card-groups',
    title: '找人一起玩',
    body: '開團或加入，額滿可候補',
    route: '/groups',
    icon: Icons.groups_outlined,
    goLabel: '前往揪團',
    style: _CardStyle(
      background: AppColors.ink,
      title: AppColors.surface,
      body: AppColors.onInkMuted,
      iconBox: AppColors.amber,
      iconColor: AppColors.ink,
      pill: AppColors.amber,
      pillText: AppColors.ink,
      arrow: AppColors.surface,
    ),
  ),
  _Entry(
    keyName: 'home-card-booking',
    title: '訂個位子',
    body: '挑桌遊店，直接選座位',
    route: '/booking',
    icon: Icons.event_seat_outlined,
    goLabel: '前往訂位',
    style: _CardStyle(
      background: AppColors.neutralTint,
      title: AppColors.ink,
      body: AppColors.inkMuted,
      iconBox: AppColors.sage,
      iconColor: AppColors.surface,
      pill: AppColors.surface,
      pillText: AppColors.ink,
      arrow: AppColors.ink,
    ),
  ),
  _Entry(
    keyName: 'home-card-rules',
    title: '這遊戲怎麼玩',
    body: '看教學、隨時問規則',
    route: '/rules',
    icon: Icons.menu_book_outlined,
    goLabel: '前往規則',
    style: _CardStyle(
      background: AppColors.surface,
      title: AppColors.ink,
      body: AppColors.inkMuted,
      iconBox: AppColors.neutralTint,
      iconColor: AppColors.ink,
      pill: AppColors.sageTint,
      pillText: AppColors.sage,
      arrow: AppColors.ink,
    ),
  ),
];

/// 四張入口卡片：手機兩欄兩列、寬窄交錯（第一排左寬右窄，第二排左窄右寬）；
/// 平板以上放得下就排成一列（同寬），放不下改成兩欄。
class EntryCards extends StatelessWidget {
  const EntryCards({super.key});

  @override
  Widget build(BuildContext context) {
    final mobile = context.screenSize == ScreenSize.mobile;
    final gap = mobile
        ? AppSpacing.small + AppSpacing.xSmall
        : AppSpacing.medium;
    return LayoutBuilder(
      builder: (context, constraints) {
        final fitsFour =
            constraints.maxWidth >= 4 * AppSizes.entryCardMinWidth + 3 * gap;
        final columns = !mobile && fitsFour ? 4 : 2;
        return Column(
          children: [
            for (var start = 0; start < _entries.length; start += columns) ...[
              if (start > 0) SizedBox(height: gap),
              _EqualHeightRow(
                gap: gap,
                flexes: [
                  for (var i = start; i < start + columns; i++)
                    mobile ? _mobileFlex[i] : 1,
                ],
                children: [
                  for (var i = start; i < start + columns; i++)
                    _EntryCard(entry: _entries[i]),
                ],
              ),
            ],
          ],
        );
      },
    );
  }
}

/// 手機版每張卡片的寬度比例：第一排 3:2，第二排 2:3。
const _mobileFlex = [3, 2, 2, 3];

/// 一排卡片，寬度依 [flexes] 分配，高度都等於最高的那張。
///
/// 不用 IntrinsicHeight 估高度：網頁的中文字型比畫面晚到，估的時候還是系統字，
/// 字型到了之後說明變成兩行，卡片高度卻沒跟著變，內容就超出卡片。
/// 這裡每次都先實際排一次、取最高的高度，再把每張卡片排成這個高度。
class _EqualHeightRow extends MultiChildRenderObjectWidget {
  const _EqualHeightRow({
    required this.gap,
    required this.flexes,
    required super.children,
  });

  final double gap;
  final List<int> flexes;

  @override
  RenderObject createRenderObject(BuildContext context) =>
      _RenderEqualHeightRow(gap: gap, flexes: flexes);

  @override
  void updateRenderObject(
    BuildContext context,
    _RenderEqualHeightRow renderObject,
  ) {
    renderObject
      ..gap = gap
      ..flexes = flexes;
  }
}

class _EqualHeightRowParentData extends ContainerBoxParentData<RenderBox> {}

class _RenderEqualHeightRow extends RenderBox
    with
        ContainerRenderObjectMixin<RenderBox, _EqualHeightRowParentData>,
        RenderBoxContainerDefaultsMixin<RenderBox, _EqualHeightRowParentData> {
  _RenderEqualHeightRow({required double gap, required List<int> flexes})
    : _gap = gap,
      _flexes = flexes;

  double _gap;
  set gap(double value) {
    if (value == _gap) return;
    _gap = value;
    markNeedsLayout();
  }

  List<int> _flexes;
  set flexes(List<int> value) {
    if (listEquals(value, _flexes)) return;
    _flexes = value;
    markNeedsLayout();
  }

  @override
  void setupParentData(RenderBox child) {
    if (child.parentData is! _EqualHeightRowParentData) {
      child.parentData = _EqualHeightRowParentData();
    }
  }

  /// 每張卡片的寬度。
  List<double> _widths(double maxWidth) {
    final total = _flexes.fold<int>(0, (sum, flex) => sum + flex);
    final space = math.max(0.0, maxWidth - _gap * (childCount - 1));
    return [for (final flex in _flexes) space * flex / total];
  }

  @override
  void performLayout() {
    final widths = _widths(constraints.maxWidth);
    // 第一次：寬度固定、高度不限，量出每張卡片需要的高度
    var height = 0.0;
    var child = firstChild;
    for (var i = 0; child != null; i++) {
      child.layout(
        BoxConstraints.tightFor(width: widths[i]),
        parentUsesSize: true,
      );
      height = math.max(height, child.size.height);
      child = childAfter(child);
    }
    // 第二次：每張卡片都排成最高的高度。
    // 只給最小高度、不給上限（不是固定尺寸），卡片才不會變成 relayout boundary：
    // 卡片裡的字變了（字型晚到、字放大），這一排會跟著重新量高度
    var x = 0.0;
    child = firstChild;
    for (var i = 0; child != null; i++) {
      child.layout(
        BoxConstraints(
          minWidth: widths[i],
          maxWidth: widths[i],
          minHeight: height,
        ),
        parentUsesSize: true,
      );
      (child.parentData! as _EqualHeightRowParentData).offset = Offset(x, 0);
      x += widths[i] + _gap;
      child = childAfter(child);
    }
    size = constraints.constrain(Size(constraints.maxWidth, height));
  }

  @override
  bool hitTestChildren(BoxHitTestResult result, {required Offset position}) =>
      defaultHitTestChildren(result, position: position);

  @override
  void paint(PaintingContext context, Offset offset) =>
      defaultPaint(context, offset);
}

class _EntryCard extends StatelessWidget {
  const _EntryCard({required this.entry});

  final _Entry entry;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final style = entry.style;
    return ThickCard(
      key: Key(entry.keyName),
      color: style.background,
      onTap: () => context.go(entry.route),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall),
        // 高度固定時（同一排比較矮的卡片）「前往…」那一列推到最下面；
        // 量高度時（高度不限）就照內容的高度，不能用 Spacer
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: AppSizes.entryIconBox,
                  height: AppSizes.entryIconBox,
                  decoration: BoxDecoration(
                    color: style.iconBox,
                    borderRadius: BorderRadius.circular(AppRadius.button),
                  ),
                  child: Icon(entry.icon, color: style.iconColor),
                ),
                const SizedBox(height: AppSpacing.medium),
                Text(
                  entry.title,
                  style: textTheme.headlineSmall!.copyWith(
                    color: style.title,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: AppSpacing.xSmall),
                Text(
                  entry.body,
                  style: textTheme.bodyMedium!.copyWith(color: style.body),
                ),
                const SizedBox(height: AppSpacing.medium),
              ],
            ),
            Row(
              children: [
                // 窄螢幕或字放大時，標籤縮短並加「…」，箭頭固定在右邊
                Expanded(
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: style.pill,
                        borderRadius: BorderRadius.circular(AppRadius.pill),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.small + AppSpacing.xSmall / 2,
                          vertical: AppSpacing.xSmall,
                        ),
                        child: Text(
                          entry.goLabel,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: textTheme.labelMedium!.copyWith(
                            color: style.pillText,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.small),
                Icon(Icons.arrow_forward, color: style.arrow),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// 頁面底部的兩個主要按鈕：揪團、訂位。
class HomeActions extends StatelessWidget {
  const HomeActions({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: ThickButton(
            buttonKey: const Key('home-cta-groups'),
            shadow: AppShadows.soft,
            style: ThickStyle.dark,
            expand: true,
            onPressed: () => context.go('/groups'),
            icon: Icons.group_add_outlined,
            label: '我要揪團',
          ),
        ),
        const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
        Expanded(
          child: ThickButton(
            buttonKey: const Key('home-cta-booking'),
            shadow: AppShadows.soft,
            style: ThickStyle.primary,
            expand: true,
            onPressed: () => context.go('/booking'),
            icon: Icons.event_seat_outlined,
            label: '直接訂位',
          ),
        ),
      ],
    );
  }
}

/// 「接下來的行程」：載入中、沒有資料、錯誤都只影響這一區。
class UpcomingSection extends ConsumerWidget {
  const UpcomingSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final upcoming = ref.watch(upcomingProvider);
    final count = upcoming.whenOrNull(data: (items) => items.length) ?? 0;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionBar(
          key: const Key('home-section-upcoming'),
          title: '接下來的行程',
          icon: Icons.confirmation_number_outlined,
          trailing: count == 0
              ? null
              : PillBadge(
                  key: const Key('home-upcoming-count'),
                  label: '$count 筆已排定',
                  tone: PillTone.accent,
                ),
        ),
        const SizedBox(height: AppSpacing.small),
        upcoming.when(
          skipLoadingOnRefresh: false,
          loading: () => const ThickCard(
            key: Key('home-upcoming-loading'),
            child: Padding(
              padding: EdgeInsets.all(AppSpacing.large),
              child: Center(child: CircularProgressIndicator()),
            ),
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
                      if (i > 0)
                        const SizedBox(
                          height: AppSpacing.small + AppSpacing.xSmall,
                        ),
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
    final card = upcomingCard(ref.watch(groupClockProvider), item);
    final textTheme = Theme.of(context).textTheme;
    final status = upcomingStatus(item);
    final kindColor = switch (item) {
      UpcomingBooking() => AppColors.sage,
      UpcomingGroup() => AppColors.primaryText,
    };
    const inset = AppSpacing.medium + AppSpacing.xSmall;
    return ThickCard(
      onTap: () => context.go(upcomingRoute(item)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(inset, inset, inset, inset),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: AppSizes.sectionDot,
                      height: AppSizes.sectionDot,
                      decoration: BoxDecoration(
                        color: kindColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.small),
                    Expanded(
                      child: Text(
                        card.kind,
                        style: textTheme.labelLarge!.copyWith(color: kindColor),
                      ),
                    ),
                    PillBadge(label: status.label, tone: _tone(status)),
                  ],
                ),
                const SizedBox(height: AppSpacing.small),
                Text(
                  card.title,
                  style: textTheme.headlineSmall!.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (card.subtitle.isNotEmpty)
                  Text(
                    card.subtitle,
                    style: textTheme.bodyLarge!.copyWith(
                      color: AppColors.inkMuted,
                    ),
                  ),
                const SizedBox(height: AppSpacing.medium),
                Wrap(
                  spacing: AppSpacing.large,
                  runSpacing: AppSpacing.small,
                  children: [
                    IconText(
                      icon: Icons.calendar_today_outlined,
                      text: card.when,
                    ),
                    IconText(
                      icon: switch (item) {
                        UpcomingBooking() => Icons.person_outline,
                        UpcomingGroup() => Icons.group_add_outlined,
                      },
                      text: card.people,
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
                children: [
                  Expanded(
                    child: Text(
                      card.footer,
                      style: textTheme.bodyMedium!.copyWith(
                        color: AppColors.inkMuted,
                      ),
                    ),
                  ),
                  Text(
                    card.action,
                    style: textTheme.labelLarge!.copyWith(
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
        Text('還沒有接下來的行程', style: textTheme.titleMedium),
        const SizedBox(height: AppSpacing.xSmall),
        Text(
          '揪個團或訂個位子，行程就會出現在這裡。',
          style: textTheme.bodyMedium!.copyWith(color: AppColors.inkMuted),
        ),
        const SizedBox(height: AppSpacing.medium),
        Wrap(
          spacing: AppSpacing.small + AppSpacing.xSmall,
          runSpacing: AppSpacing.small + AppSpacing.xSmall,
          children: [
            ThickButton(
              buttonKey: const Key('home-empty-groups'),
              style: ThickStyle.primary,
              onPressed: () => context.go('/groups'),
              icon: Icons.groups_outlined,
              label: '找人一起玩',
            ),
            ThickButton(
              buttonKey: const Key('home-empty-booking'),
              style: ThickStyle.light,
              onPressed: () => context.go('/booking'),
              icon: Icons.event_outlined,
              label: '訂個位子',
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
        ThickButton(
          buttonKey: const Key('home-upcoming-retry'),
          style: ThickStyle.light,
          onPressed: onRetry,
          icon: Icons.refresh,
          label: '重試',
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
    return ThickCard(
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
