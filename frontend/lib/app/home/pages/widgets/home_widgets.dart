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

/// 有厚度的外框：四邊細線、底部較粗（像木牌的側邊），加上陰影。
BoxDecoration _thick({
  required Color color,
  required Color edge,
  required double radius,
  double thickness = AppSizes.cardThickness,
  List<BoxShadow>? shadow,
}) => BoxDecoration(
  color: color,
  borderRadius: BorderRadius.circular(radius),
  border: Border(
    top: BorderSide(color: edge),
    left: BorderSide(color: edge),
    right: BorderSide(color: edge),
    bottom: BorderSide(color: edge, width: thickness),
  ),
  boxShadow: shadow ?? AppShadows.raised,
);

/// 有厚度、按得下去的外框：[pressed] 時底邊變薄、內容往下沉、陰影變淺。
///
/// 少掉的厚度剛好等於往下沉的距離，整體高度不變，下面的內容不會跟著跳動。
class _PressFrame extends StatelessWidget {
  const _PressFrame({
    required this.pressed,
    required this.color,
    required this.edge,
    required this.radius,
    required this.child,
  });

  final bool pressed;
  final Color color;
  final Color edge;
  final double radius;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    const sink = AppSizes.cardThickness - AppSizes.pressedThickness;
    final thickness = pressed
        ? AppSizes.pressedThickness
        : AppSizes.cardThickness;
    return AnimatedContainer(
      duration: AppDurations.press,
      // AnimatedContainer 會依邊框粗細自動內縮，內容不會蓋到底邊；
      // 底邊少掉的厚度由上方的 margin 補回，整體高度不變
      margin: EdgeInsets.only(top: pressed ? sink : 0),
      decoration: _thick(
        color: color,
        edge: edge,
        radius: radius,
        thickness: thickness,
        shadow: pressed ? AppShadows.card : AppShadows.raised,
      ),
      child: child,
    );
  }
}

/// 深色大標題卡：「今天想怎麼玩？」。
class HomeHero extends StatelessWidget {
  const HomeHero({super.key = const Key('home-hero')});

  @override
  Widget build(BuildContext context) {
    final mobile = context.screenSize == ScreenSize.mobile;
    final textTheme = Theme.of(context).textTheme;
    return DecoratedBox(
      decoration: _thick(
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

/// 區塊標題：白底條、左邊小圓點，右邊可以放標籤（例如筆數）。
class SectionBar extends StatelessWidget {
  const SectionBar({required this.title, this.trailing, this.icon, super.key});

  final String title;
  final Widget? trailing;

  /// 取代左邊小圓點的圖示。
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return _GlassBar(
      child: Row(
        children: [
          if (icon case final icon?)
            Icon(icon, color: AppColors.primaryText)
          else
            Container(
              width: AppSizes.sectionDot,
              height: AppSizes.sectionDot,
              decoration: const BoxDecoration(
                color: AppColors.primary,
                shape: BoxShape.circle,
              ),
            ),
          const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
          Expanded(
            child: Text(
              title,
              style: Theme.of(
                context,
              ).textTheme.headlineSmall!.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}

/// 放在木紋上的半透明白底條。
class _GlassBar extends StatelessWidget {
  const _GlassBar({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: _thick(
        color: AppColors.surfaceGlass,
        edge: AppColors.cardEdge,
        radius: AppRadius.card,
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.medium,
          vertical: AppSpacing.small,
        ),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: AppSizes.minTouchTarget),
          child: Align(alignment: Alignment.centerLeft, child: child),
        ),
      ),
    );
  }
}

/// 首頁的卡片：圓角、細邊框、底部較粗的邊（看起來有厚度）、陰影；
/// 有 [onTap] 時可以點，按住時往下沉。
class _CardShell extends StatefulWidget {
  const _CardShell({
    required this.child,
    this.onTap,
    this.color = AppColors.surface,
    super.key,
  });

  final Widget child;
  final VoidCallback? onTap;
  final Color color;

  @override
  State<_CardShell> createState() => _CardShellState();
}

class _CardShellState extends State<_CardShell> {
  var _pressed = false;

  @override
  Widget build(BuildContext context) {
    final color = widget.color;
    return _PressFrame(
      pressed: _pressed,
      color: color,
      edge: color == AppColors.ink ? AppColors.inkEdge : AppColors.cardEdge,
      radius: AppRadius.hero,
      child: Material(
        type: MaterialType.transparency,
        borderRadius: BorderRadius.circular(AppRadius.hero),
        clipBehavior: Clip.antiAlias,
        child: widget.onTap == null
            ? widget.child
            : InkWell(
                onTap: widget.onTap,
                onHighlightChanged: (pressed) =>
                    setState(() => _pressed = pressed),
                child: widget.child,
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

/// 四張入口卡片：手機兩欄兩列；平板以上放得下就排成一列，放不下改成兩欄。
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
    final style = entry.style;
    return _CardShell(
      key: Key(entry.keyName),
      color: style.background,
      onTap: () => context.go(entry.route),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall),
        child: Column(
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
            const Spacer(),
            const SizedBox(height: AppSpacing.medium),
            Row(
              children: [
                DecoratedBox(
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
                      style: textTheme.labelMedium!.copyWith(
                        color: style.pillText,
                      ),
                    ),
                  ),
                ),
                const Spacer(),
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
          child: _ThickButton(
            buttonKey: const Key('home-cta-groups'),
            style: _ThickStyle.dark,
            expand: true,
            onPressed: () => context.go('/groups'),
            icon: Icons.group_add_outlined,
            label: '我要揪團',
          ),
        ),
        const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
        Expanded(
          child: _ThickButton(
            buttonKey: const Key('home-cta-booking'),
            style: _ThickStyle.primary,
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

/// 有厚度的按鈕配色。
enum _ThickStyle {
  /// 焦糖橘：主要操作。
  primary(AppColors.primary, AppColors.primaryText, AppColors.surface),

  /// 深炭色：和主要操作並列的另一個重點操作。
  dark(AppColors.ink, AppColors.inkEdge, AppColors.surface),

  /// 米白：次要操作。
  light(AppColors.background, AppColors.cardEdge, AppColors.ink);

  const _ThickStyle(this.color, this.edge, this.foreground);

  final Color color;
  final Color edge;
  final Color foreground;
}

/// 有厚度的按鈕：底部較深的邊與陰影。按住時底邊變薄、往下沉，放開後彈回。
class _ThickButton extends StatefulWidget {
  const _ThickButton({
    required this.buttonKey,
    required this.style,
    required this.onPressed,
    required this.icon,
    required this.label,
    this.expand = false,
  });

  /// 掛在按鈕本身的 Key（測試用它找按鈕）。
  final Key buttonKey;
  final _ThickStyle style;
  final VoidCallback onPressed;
  final IconData icon;
  final String label;

  /// 撐滿可用寬度（底部兩個大按鈕），否則依文字寬度。
  final bool expand;

  @override
  State<_ThickButton> createState() => _ThickButtonState();
}

class _ThickButtonState extends State<_ThickButton> {
  final _states = WidgetStatesController();
  var _pressed = false;

  @override
  void initState() {
    super.initState();
    _states.addListener(() {
      final pressed = _states.value.contains(WidgetState.pressed);
      if (pressed != _pressed) setState(() => _pressed = pressed);
    });
  }

  @override
  void dispose() {
    _states.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final style = widget.style;
    const height = AppSizes.minTouchTarget + AppSpacing.small;
    return _PressFrame(
      pressed: _pressed,
      color: style.edge,
      edge: style.edge,
      radius: AppRadius.button,
      child: FilledButton.icon(
        key: widget.buttonKey,
        statesController: _states,
        style: FilledButton.styleFrom(
          backgroundColor: style.color,
          foregroundColor: style.foreground,
          minimumSize: widget.expand
              ? const Size.fromHeight(height)
              : const Size(AppSizes.minTouchTarget, height),
        ),
        onPressed: widget.onPressed,
        icon: Icon(widget.icon),
        label: Text(widget.label),
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
          loading: () => const _CardShell(
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
    return _CardShell(
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
                    _IconText(
                      icon: Icons.calendar_today_outlined,
                      text: card.when,
                    ),
                    _IconText(
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
          const _DashedLine(),
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

/// 圖示＋粗體文字，例如日期、人數。
class _IconText extends StatelessWidget {
  const _IconText({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: AppSizes.inlineIcon, color: AppColors.ink),
        const SizedBox(width: AppSpacing.small),
        Text(
          text,
          style: Theme.of(
            context,
          ).textTheme.titleSmall!.copyWith(fontWeight: FontWeight.w700),
        ),
      ],
    );
  }
}

/// 卡片內容與底部代碼之間的虛線。
class _DashedLine extends StatelessWidget {
  const _DashedLine();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: 1,
      width: double.infinity,
      child: CustomPaint(painter: _DashPainter()),
    );
  }
}

class _DashPainter extends CustomPainter {
  const _DashPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.cardEdge
      ..strokeWidth = size.height;
    for (
      var x = 0.0;
      x < size.width;
      x += AppSizes.dashLength + AppSizes.dashGap
    ) {
      canvas.drawLine(Offset(x, 0), Offset(x + AppSizes.dashLength, 0), paint);
    }
  }

  @override
  bool shouldRepaint(_DashPainter oldDelegate) => false;
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
            _ThickButton(
              buttonKey: const Key('home-empty-groups'),
              style: _ThickStyle.primary,
              onPressed: () => context.go('/groups'),
              icon: Icons.groups_outlined,
              label: '找人一起玩',
            ),
            _ThickButton(
              buttonKey: const Key('home-empty-booking'),
              style: _ThickStyle.light,
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
        _ThickButton(
          buttonKey: const Key('home-upcoming-retry'),
          style: _ThickStyle.light,
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
    return _CardShell(
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
