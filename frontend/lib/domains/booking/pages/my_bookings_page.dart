import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/dev/state/dev_user_state.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/booking.dart';
import '../state/booking_state.dart';
import 'widgets/booking_widgets.dart';
import 'widgets/seating_plan.dart';

/// 我的訂位正式頁面：依狀態篩選，可以取消（`/booking/mine`）。
///
/// Stitch 版面：木紋背景，分段切換的分頁、篩選膠囊、有厚度的訂位卡片與按鈕；
/// 手機的浮動導覽列蓋住的高度留在最下面。
class MyBookingsPage extends ConsumerStatefulWidget {
  const MyBookingsPage({super.key});

  @override
  ConsumerState<MyBookingsPage> createState() => _MyBookingsPageState();
}

const _statusFilters = [
  (null, '全部'),
  ('confirmed', '已確認'),
  ('seated', '已入座'),
  ('completed', '已完成'),
  ('cancelled', '已取消'),
  ('no_show', '未出席'),
];

class _MyBookingsPageState extends ConsumerState<MyBookingsPage> {
  String? _status;

  BookingNotifier get _n => ref.read(bookingProvider.notifier);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      // 卡片要顯示店家名稱
      if (ref.read(bookingProvider).shops.isEmpty) await _n.loadShops();
      await _search();
    });
  }

  Future<void> _search() => _n.loadMine(status: _status);

  Future<void> _cancel(Booking b) async {
    final ok = await confirmBookingAction(
      context,
      title: '確定要取消這筆訂位嗎？',
      confirmLabel: '取消訂位',
    );
    if (!ok || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    await _n.setStatus(b.id, 'cancelled');
    if (!mounted || ref.read(bookingProvider).isError) return;
    messenger.showSnackBar(const SnackBar(content: Text('已取消訂位')));
  }

  /// 打開這筆訂位的店家在訂位時段的座位圖，自己的桌另外標示。
  Future<void> _showSeats(Booking b, String? shopName) {
    Future<void> load() =>
        _n.loadSeatingPlan(b.shopId, from: b.startAt, to: b.endAt);
    load();
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => _SeatsSheet(
        key: const Key('booking-seats-sheet'),
        title: '${shopName ?? '店家'}的座位',
        range: formatBookingRange(b.startAt, b.endAt),
        onRetry: load,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bookingProvider);
    final user = ref.watch(currentDevUserProvider);
    final shopNames = {for (final s in state.shops) s.id: s.name};

    final isStaff = user?.role == 'shop_staff' || user?.role == 'admin';
    final children = <Widget>[
      ThickCard(
        radius: AppRadius.card,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.small),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              BookingTabs(current: 'mine', showBoard: isStaff),
              const SizedBox(height: AppSpacing.small),
              // 狀態篩選：一排可以左右滑的膠囊
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    for (final (i, (value, label))
                        in _statusFilters.indexed) ...[
                      if (i > 0) const SizedBox(width: AppSpacing.small),
                      _FilterPill(
                        key: Key('booking-status-${value ?? 'all'}'),
                        label: label,
                        selected: _status == value,
                        onTap: state.loading
                            ? null
                            : () {
                                setState(() => _status = value);
                                _search();
                              },
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      const SizedBox(height: AppSpacing.medium),
      if (state.isError && state.message != null) ...[
        BookingErrorBanner(message: state.message!, onRetry: _search),
        const SizedBox(height: AppSpacing.medium),
      ],
      if (state.loading && state.mine.isEmpty)
        const Padding(
          padding: EdgeInsets.all(AppSpacing.large),
          child: Center(child: CircularProgressIndicator()),
        )
      else if (state.mine.isEmpty && !state.isError)
        _Empty(filtered: _status != null)
      else
        for (final b in state.mine)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.medium),
            child: _MyBookingCard(
              key: Key('booking-card-${b.id}'),
              booking: b,
              shopName: shopNames[b.shopId],
              actions: [
                if (b.status == 'confirmed' || b.status == 'seated')
                  ThickButton(
                    buttonKey: Key('booking-seats-${b.id}'),
                    style: ThickStyle.light,
                    shadow: AppShadows.soft,
                    onPressed: () => _showSeats(b, shopNames[b.shopId]),
                    icon: Icons.table_restaurant_outlined,
                    label: '看座位',
                  ),
                if (b.status == 'confirmed')
                  ThickButton(
                    buttonKey: Key('booking-cancel-${b.id}'),
                    style: ThickStyle.danger,
                    shadow: AppShadows.soft,
                    onPressed: state.loading ? null : () => _cancel(b),
                    icon: Icons.event_busy_outlined,
                    label: '取消訂位',
                  ),
              ],
            ),
          ),
    ];

    final body = Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth:
              AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity,
        ),
        child: ListView(
          padding: EdgeInsets.fromLTRB(
            AppSpacing.medium,
            AppSpacing.medium,
            AppSpacing.medium,
            AppSpacing.medium + MediaQuery.paddingOf(context).bottom,
          ),
          children: children,
        ),
      ),
    );
    return Scaffold(
      key: const Key('my-bookings-page'),
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: WoodBackground.isPaintedAbove(context)
            ? body
            : WoodBackground(child: body),
      ),
    );
  }
}

/// 狀態篩選膠囊：選中的是深炭底白字。
class _FilterPill extends StatelessWidget {
  const _FilterPill({
    required this.label,
    required this.selected,
    required this.onTap,
    super.key,
  });

  final String label;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      selected: selected,
      button: true,
      child: Material(
        color: selected ? AppColors.ink : AppColors.surface,
        shape: StadiumBorder(
          side: BorderSide(color: selected ? AppColors.ink : AppColors.border),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.medium,
              vertical: AppSpacing.small,
            ),
            child: Text(
              label,
              style: Theme.of(context).textTheme.labelLarge!.copyWith(
                color: selected ? AppColors.surface : AppColors.ink,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 一筆訂位（Stitch 版面）：店名當標題、右上狀態，時間、人數、桌位、注意事項，
/// 虛線下方是訂位代碼與預估費用，最下面是操作按鈕。
class _MyBookingCard extends StatelessWidget {
  const _MyBookingCard({
    required this.booking,
    required this.shopName,
    required this.actions,
    super.key,
  });

  final Booking booking;
  final String? shopName;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final b = booking;
    final text = Theme.of(context).textTheme;
    final (statusText, tone) = bookingStatusLabel(b.status);
    const inset = AppSpacing.medium + AppSpacing.xSmall;
    return ThickCard(
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
                    Expanded(
                      child: Text(
                        shopName ?? '訂位',
                        style: text.headlineSmall!.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    PillBadge(label: statusText, tone: tone),
                  ],
                ),
                const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
                IconText(
                  icon: Icons.calendar_today_outlined,
                  text: formatBookingRange(b.startAt, b.endAt),
                ),
                const SizedBox(height: AppSpacing.small),
                Wrap(
                  spacing: AppSpacing.large,
                  runSpacing: AppSpacing.small,
                  children: [
                    IconText(
                      icon: Icons.people_outline,
                      text: '${b.partySize} 人',
                    ),
                    if (b.tableCodes.isNotEmpty)
                      IconText(
                        icon: Icons.table_restaurant_outlined,
                        text: '桌位 ${b.tableCodes.join('、')}',
                      ),
                  ],
                ),
                if (b.notice != null) ...[
                  const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
                  DecoratedBox(
                    decoration: BoxDecoration(
                      color: AppColors.amberTint,
                      borderRadius: BorderRadius.circular(AppRadius.button),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.small),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(
                            Icons.info_outline,
                            size: AppSizes.inlineIcon,
                            color: AppColors.amberText,
                          ),
                          const SizedBox(width: AppSpacing.small),
                          Expanded(
                            child: Text(
                              b.notice!,
                              style: text.bodyMedium!.copyWith(
                                color: AppColors.amberText,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
                if (actions.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.medium),
                  Wrap(
                    spacing: AppSpacing.small,
                    runSpacing: AppSpacing.small,
                    children: actions,
                  ),
                ],
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
                      '訂位代碼 ${b.reservationCode}',
                      style: text.bodyMedium!.copyWith(
                        color: AppColors.inkMuted,
                      ),
                    ),
                  ),
                  Text(
                    b.finalFee == null
                        ? '預估 ${bookingMoney(b.estimatedFee.venueFee)} 元'
                        : '結算 ${bookingMoney(b.finalFee!)} 元',
                    style: text.titleSmall!.copyWith(
                      color: AppColors.primaryText,
                    ),
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

class _Empty extends StatelessWidget {
  const _Empty({required this.filtered});

  final bool filtered;

  @override
  Widget build(BuildContext context) {
    return ThickCard(
      key: const Key('booking-empty'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.large),
        child: Column(
          children: [
            const Icon(
              Icons.event_note_outlined,
              size: AppSizes.emptyStateIcon,
              color: AppColors.cardEdge,
            ),
            const SizedBox(height: AppSpacing.medium),
            Text(
              filtered ? '沒有符合的訂位' : '還沒有訂位',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.medium),
            ThickButton(
              buttonKey: const Key('booking-empty-new'),
              style: ThickStyle.primary,
              onPressed: () => context.go('/booking'),
              icon: Icons.event_seat_outlined,
              label: '去訂位',
            ),
          ],
        ),
      ),
    );
  }
}

/// 「看座位」的下方面板：載入中、錯誤與重試、沒有座位圖、座位圖。
class _SeatsSheet extends ConsumerWidget {
  const _SeatsSheet({
    required this.title,
    required this.range,
    required this.onRetry,
    super.key,
  });

  final String title;
  final String range;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(bookingProvider);
    final text = Theme.of(context).textTheme;
    final Widget content;
    if (state.loading) {
      content = const Padding(
        padding: EdgeInsets.all(AppSpacing.large),
        child: Center(child: CircularProgressIndicator()),
      );
    } else if (state.isError && state.message != null) {
      content = BookingErrorBanner(
        message: state.message!,
        onRetry: onRetry,
        retryKey: const Key('seating-retry'),
      );
    } else if (state.seatingPlan.isEmpty) {
      content = const Padding(
        padding: EdgeInsets.all(AppSpacing.large),
        child: Center(child: Text('這間店還沒有座位圖')),
      );
    } else {
      content = SeatingPlanView(plans: state.seatingPlan, staffView: false);
    }
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.large,
          0,
          AppSpacing.large,
          AppSpacing.large,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: text.titleLarge),
            Text(
              range,
              style: text.bodyMedium!.copyWith(color: AppColors.inkMuted),
            ),
            const SizedBox(height: AppSpacing.medium),
            content,
          ],
        ),
      ),
    );
  }
}
