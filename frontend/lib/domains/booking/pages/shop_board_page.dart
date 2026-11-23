import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../core/dev/state/dev_user_state.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/booking.dart';
import '../state/board_summary.dart';
import '../state/booking_overtime.dart';
import '../state/booking_state.dart';
import 'widgets/booking_widgets.dart';
import 'widgets/seating_plan.dart';

/// 店家看板正式頁面：店家人員看自己店家某一天的座位圖與訂位，辦理客人到店、離店結帳、取消
/// （`/booking/board`）。管理員要先選店家。
///
/// 已入座且超過結束時間的訂位標示「已超時」，每分鐘重新計算（add-booking-notifications D5）。
///
/// Stitch 版面：木紋背景，店家卡（日期快選、統計）、厚的座位圖卡、訂位列表的標題條與篩選、
/// 厚的訂位卡片（已入座時顯示剩餘分鐘）；手機的浮動導覽列蓋住的高度留在最下面。
class ShopBoardPage extends ConsumerStatefulWidget {
  const ShopBoardPage({super.key});

  @override
  ConsumerState<ShopBoardPage> createState() => _ShopBoardPageState();
}

class _ShopBoardPageState extends ConsumerState<ShopBoardPage> {
  String? _shopId;
  late DateTime _date;
  BoardFilter _filter = BoardFilter.all;

  /// 每分鐘重畫一次，讓超時標示跟著時間更新（不重新查詢）。
  Timer? _minuteTimer;

  BookingNotifier get _n => ref.read(bookingProvider.notifier);

  bool get _allowed {
    final role = ref.read(currentDevUserProvider)?.role;
    return role == 'shop_staff' || role == 'admin';
  }

  String? get _selectedShop =>
      _shopId ?? ref.read(currentDevUserProvider)?.shopId;

  @override
  void initState() {
    super.initState();
    final now = ref.read(bookingClockProvider)().add(taipeiOffset);
    _date = DateTime(now.year, now.month, now.day);
    _minuteTimer = Timer.periodic(const Duration(minutes: 1), (_) {
      if (mounted) setState(() {});
    });
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!_allowed) return;
      if (ref.read(bookingProvider).shops.isEmpty) await _n.loadShops();
      await _search();
    });
  }

  @override
  void dispose() {
    _minuteTimer?.cancel();
    super.dispose();
  }

  Future<void> _search() async {
    final shopId = _selectedShop;
    if (shopId == null) return;
    final day = isoDate(_date);
    final from = '${day}T00:00:00+08:00';
    final to = '${day}T23:59:59+08:00';
    await _n.loadBoard(shopId, from, to);
    // 訂位與座位圖共用 state 的錯誤訊息；訂位失敗時先不查座位圖，以免錯誤被蓋掉
    if (!mounted || ref.read(bookingProvider).isError) return;
    await _n.loadSeatingPlan(shopId, from: from, to: to);
  }

  /// 台灣時間的今天（日期快選用）。
  DateTime get _today {
    final now = ref.read(bookingClockProvider)().add(taipeiOffset);
    return DateTime(now.year, now.month, now.day);
  }

  Future<void> _setDate(DateTime date) async {
    setState(() => _date = date);
    await _search();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: _date.subtract(const Duration(days: 365)),
      lastDate: _date.add(const Duration(days: 365)),
    );
    if (picked == null) return;
    setState(() => _date = picked);
    await _search();
  }

  Future<void> _cancel(Booking b) async {
    final ok = await confirmBookingAction(
      context,
      title: '確定要取消這筆訂位嗎？',
      confirmLabel: '取消訂位',
    );
    if (ok && mounted) await _n.setStatus(b.id, 'cancelled');
  }

  /// 在座位圖上點了一張桌：先顯示定位與換桌資訊請使用者確認，按確認才送請求。
  /// 按「先不要」或關掉視窗只關閉確認視窗，仍停留在選桌模式，可改選別的桌子。
  Future<void> _changeTable(Booking b, SeatGroup seat) async {
    final current = b.tableCodes.isEmpty ? '無' : b.tableCodes.join('、');
    final ok = await confirmBookingAction(
      context,
      title: '確定要換桌嗎？',
      content:
          '訂位代碼 ${b.reservationCode}\n'
          '${formatBookingRange(b.startAt, b.endAt)}\n'
          '定位：$current\n'
          '換桌：${seat.table.tableCode}',
      confirmLabel: '確認換桌',
    );
    if (!ok || !mounted) return;
    await _n.changeTable(b.id, [seat.table.id]);
    // 換桌失敗時保留錯誤訊息，不重新整理；成功才重查座位圖
    if (mounted && !ref.read(bookingProvider).isError) await _search();
  }

  /// 換桌中的那筆訂位。
  Booking? _changeTarget(BookingState state) {
    final id = state.changeTableFor;
    if (id == null) return null;
    for (final b in state.board) {
      if (b.id == id) return b;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bookingProvider);
    final user = ref.watch(currentDevUserProvider);
    final allowed = user?.role == 'shop_staff' || user?.role == 'admin';

    if (!allowed) {
      return _page(
        context,
        wide: false,
        children: [
          ThickCard(
            child: Padding(
              key: const Key('board-no-permission'),
              padding: const EdgeInsets.all(AppSpacing.large),
              child: Text(
                '只有店家人員可以查看店家看板',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
          ),
        ],
        showBoard: false,
      );
    }

    final now = ref.read(bookingClockProvider)();
    final isAdmin = user?.role == 'admin';
    final wide = context.screenSize != ScreenSize.mobile;
    final shopId = _shopId ?? user?.shopId;
    final shopNames = {for (final s in state.shops) s.id: s.name};
    VoidCallback? act(VoidCallback f) => state.loading ? null : f;
    final shown = filterBoard(state.board, _filter, now);
    final text = Theme.of(context).textTheme;

    final list = <Widget>[
      // 列表標題條：今日預約與現場桌況＋筆數
      SectionBar(
        key: const Key('board-list-header'),
        title: '今日預約與現場桌況',
        icon: Icons.event_note_outlined,
        trailing: PillBadge(
          label: '${state.board.length} 筆',
          tone: PillTone.accent,
        ),
      ),
      const SizedBox(height: AppSpacing.small),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            for (final (i, (filter, label)) in const [
              (BoardFilter.all, '全部'),
              (BoardFilter.overtime, '已超時'),
              (BoardFilter.seated, '進行中'),
              (BoardFilter.waiting, '待到店'),
            ].indexed) ...[
              if (i > 0) const SizedBox(width: AppSpacing.small),
              _FilterPill(
                key: Key('board-filter-${filter.name}'),
                label: '$label（${boardCount(state.board, filter, now)}）',
                selected: _filter == filter,
                onTap: () => setState(() => _filter = filter),
              ),
            ],
          ],
        ),
      ),
      const SizedBox(height: AppSpacing.medium),
      if (state.loading && state.board.isEmpty)
        const Padding(
          padding: EdgeInsets.all(AppSpacing.large),
          child: Center(child: CircularProgressIndicator()),
        )
      else if (state.board.isEmpty && !state.isError)
        ThickCard(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.large),
            child: Center(child: Text('這天沒有訂位', style: text.titleMedium)),
          ),
        )
      else if (shown.isEmpty)
        ThickCard(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.large),
            child: Center(child: Text('沒有符合的訂位', style: text.titleMedium)),
          ),
        )
      else
        for (final b in shown)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.medium),
            child: _BoardCard(
              key: Key('board-card-${b.id}'),
              booking: b,
              overtime: overtimeMinutes(b.status, b.endAt, now),
              remaining: remainingMinutes(b.status, b.endAt, now),
              actions: [
                if (b.status == 'confirmed') ...[
                  ThickButton(
                    buttonKey: Key('board-seated-${b.id}'),
                    style: ThickStyle.primary,
                    shadow: AppShadows.soft,
                    onPressed: act(() => _n.setStatus(b.id, 'seated')),
                    icon: Icons.login,
                    label: '客人到店',
                  ),
                  ThickButton(
                    buttonKey: Key('board-change-table-${b.id}'),
                    style: ThickStyle.light,
                    shadow: AppShadows.soft,
                    onPressed: act(() => _n.startChangeTable(b.id)),
                    icon: Icons.swap_horiz,
                    label: '換桌',
                  ),
                  ThickButton(
                    buttonKey: Key('board-cancel-${b.id}'),
                    style: ThickStyle.danger,
                    shadow: AppShadows.soft,
                    onPressed: act(() => _cancel(b)),
                    label: '取消',
                  ),
                ],
                if (b.status == 'seated')
                  ThickButton(
                    buttonKey: Key('board-complete-${b.id}'),
                    style: ThickStyle.dark,
                    shadow: AppShadows.soft,
                    onPressed: act(() => _n.setStatus(b.id, 'completed')),
                    icon: Icons.point_of_sale_outlined,
                    label: '離店結帳',
                  ),
              ],
            ),
          ),
    ];

    final stats = boardStats(state.seatingPlan, state.board, now);
    final header = ThickCard(
      key: const Key('board-header'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Container(
                  width: AppSizes.avatar,
                  height: AppSizes.avatar,
                  decoration: BoxDecoration(
                    color: AppColors.primaryTint,
                    borderRadius: BorderRadius.circular(AppRadius.button),
                  ),
                  child: const Icon(
                    Icons.storefront_outlined,
                    color: AppColors.primaryText,
                  ),
                ),
                const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
                Expanded(
                  child: isAdmin
                      ? KeyedSubtree(
                          key: const Key('booking-shop'),
                          child: DropdownButtonFormField<String>(
                            key: ValueKey((state.shops.length, shopId)),
                            initialValue: shopNames.containsKey(shopId)
                                ? shopId
                                : null,
                            hint: const Text('選擇店家'),
                            items: [
                              for (final s in state.shops)
                                DropdownMenuItem(
                                  value: s.id,
                                  child: Text(s.name),
                                ),
                            ],
                            onChanged: (v) {
                              setState(() => _shopId = v);
                              _search();
                            },
                          ),
                        )
                      : Text(
                          shopNames[shopId] ?? '店家看板',
                          style: text.headlineSmall!.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                ),
                IconButton(
                  key: const Key('board-search'),
                  onPressed: act(_search),
                  icon: const Icon(Icons.refresh),
                  tooltip: '重新整理',
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.medium),
            Row(
              children: [
                for (final (i, (key, label)) in const [
                  ('board-date-today', '今天'),
                  ('board-date-tomorrow', '明天'),
                ].indexed) ...[
                  _FilterPill(
                    key: Key(key),
                    label: label,
                    selected: _date == _today.add(Duration(days: i)),
                    onTap: () => _setDate(_today.add(Duration(days: i))),
                  ),
                  const SizedBox(width: AppSpacing.small),
                ],
                Expanded(
                  child: OutlinedButton.icon(
                    key: const Key('board-date'),
                    onPressed: _pickDate,
                    icon: const Icon(Icons.calendar_month_outlined),
                    label: Text(shortDate(_date)),
                  ),
                ),
              ],
            ),
            if (shopId != null) ...[
              const SizedBox(height: AppSpacing.medium),
              Row(
                key: const Key('board-stats'),
                children: [
                  for (final (i, (value, label, color)) in [
                    (stats.total, '全店桌數', AppColors.ink),
                    (stats.inUse, '使用中', AppColors.amberText),
                    (stats.overtime, '已超時', AppColors.error),
                    (stats.free, '空桌', AppColors.sage),
                  ].indexed) ...[
                    if (i > 0)
                      const SizedBox(
                        height: AppSizes.avatar,
                        child: VerticalDivider(),
                      ),
                    Expanded(
                      child: Column(
                        children: [
                          Text(
                            '$value',
                            style: text.headlineSmall!.copyWith(
                              color: color,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          Text(label, style: text.bodySmall),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ],
        ),
      ),
    );

    return _page(
      context,
      wide: wide,
      showBoard: true,
      children: [
        header,
        const SizedBox(height: AppSpacing.medium),
        if (state.isError && state.message != null) ...[
          BookingErrorBanner(
            message: state.message!,
            onRetry: _search,
            retryKey: const Key('board-retry'),
          ),
          const SizedBox(height: AppSpacing.medium),
        ],
        if (shopId == null)
          ThickCard(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.large),
              child: Center(child: Text('請先選擇店家', style: text.titleMedium)),
            ),
          )
        else if (wide)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: _seatingCard(state, now)),
              const SizedBox(width: AppSpacing.large),
              Expanded(child: Column(children: list)),
            ],
          )
        else ...[
          _seatingCard(state, now),
          const SizedBox(height: AppSpacing.medium),
          ...list,
        ],
      ],
    );
  }

  /// 頁面外框：三個訂位頁共用的 [BookingPageFrame]。
  Widget _page(
    BuildContext context, {
    required bool wide,
    required bool showBoard,
    required List<Widget> children,
  }) {
    return BookingPageFrame(
      pageKey: const Key('shop-board-page'),
      current: 'board',
      showBoard: showBoard,
      children: children,
    );
  }

  /// 座位圖卡片：日期跟著看板，錯誤由上方的錯誤訊息顯示。
  Widget _seatingCard(BookingState state, DateTime now) {
    final changeFor = _changeTarget(state);
    final selecting = state.changeTableFor != null;
    final Widget content;
    if (state.seatingPlan.isNotEmpty) {
      content = SeatingPlanView(
        plans: state.seatingPlan,
        staffView: true,
        now: now,
        selecting: selecting,
        onTapTable: selecting
            ? (seat) {
                if (changeFor != null && !state.loading) {
                  _changeTable(changeFor, seat);
                }
              }
            : null,
      );
    } else if (state.loading) {
      content = const Padding(
        padding: EdgeInsets.all(AppSpacing.large),
        child: Center(child: CircularProgressIndicator()),
      );
    } else if (state.isError) {
      content = const SizedBox.shrink();
    } else {
      content = const Padding(
        padding: EdgeInsets.all(AppSpacing.medium),
        child: Center(child: Text('這間店還沒有座位圖')),
      );
    }
    return ThickCard(
      key: const Key('board-seating'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.table_restaurant_outlined,
                  color: AppColors.primaryText,
                ),
                const SizedBox(width: AppSpacing.small),
                Text(
                  '即時客席狀態圖',
                  style: Theme.of(context).textTheme.titleMedium!.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            if (selecting) ...[
              const SizedBox(height: AppSpacing.small),
              _changeTableHint(),
            ],
            const SizedBox(height: AppSpacing.small),
            content,
          ],
        ),
      ),
    );
  }

  /// 選桌模式中的提示列：告訴使用者要選桌，並提供離開選桌模式的按鈕。
  Widget _changeTableHint() => DecoratedBox(
    key: const Key('board-change-table-hint'),
    decoration: BoxDecoration(
      color: AppColors.amberTint,
      borderRadius: BorderRadius.circular(AppRadius.button),
    ),
    child: Padding(
      padding: const EdgeInsets.only(
        left: AppSpacing.small + AppSpacing.xSmall,
      ),
      child: Row(
        children: [
          const Icon(Icons.touch_app_outlined, color: AppColors.amberText),
          const SizedBox(width: AppSpacing.small),
          Expanded(
            child: Text(
              '請在座位圖點選要換到的桌子',
              style: Theme.of(
                context,
              ).textTheme.bodyMedium!.copyWith(color: AppColors.amberText),
            ),
          ),
          TextButton(
            key: const Key('board-change-table-cancel'),
            onPressed: _n.cancelChangeTable,
            child: const Text('取消選桌'),
          ),
        ],
      ),
    ),
  );
}

/// 篩選或日期快選膠囊：選中的是深炭底白字。
class _FilterPill extends StatelessWidget {
  const _FilterPill({
    required this.label,
    required this.selected,
    required this.onTap,
    super.key,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

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

/// 店家看板上的一筆訂位（Stitch 版面）：狀態（已超時時是橘色「已超時 N 分鐘」）、
/// 時間、人數、桌位、已入座時剩餘分鐘、店家公告、操作按鈕，虛線下方是代碼與費用。
class _BoardCard extends StatelessWidget {
  const _BoardCard({
    required this.booking,
    required this.overtime,
    required this.remaining,
    required this.actions,
    super.key,
  });

  final Booking booking;
  final int? overtime;
  final int? remaining;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final b = booking;
    final text = Theme.of(context).textTheme;
    final (statusText, tone) = bookingStatusLabel(b.status);
    const inset = AppSpacing.medium + AppSpacing.xSmall;
    return ThickCard(
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 超時：左邊一條紅色短線
            Container(
              width: AppSpacing.xSmall,
              color: overtime != null ? AppColors.error : Colors.transparent,
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Padding(
                    padding: const EdgeInsets.all(inset),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Wrap(
                          spacing: AppSpacing.small,
                          runSpacing: AppSpacing.xSmall,
                          children: [
                            if (overtime != null)
                              PillBadge(
                                key: Key('board-overtime-${b.id}'),
                                label: '已超時 $overtime 分鐘',
                                tone: PillTone.accent,
                                icon: Icons.timer_off_outlined,
                              )
                            else
                              PillBadge(label: statusText, tone: tone),
                            if (remaining != null)
                              PillBadge(
                                label: '剩餘 $remaining 分鐘',
                                tone: PillTone.duration,
                                icon: Icons.hourglass_bottom,
                              ),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.small),
                        Text(
                          formatBookingRange(b.startAt, b.endAt),
                          style: text.titleMedium!.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
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
                          const SizedBox(height: AppSpacing.small),
                          DecoratedBox(
                            decoration: BoxDecoration(
                              color: AppColors.amberTint,
                              borderRadius: BorderRadius.circular(
                                AppRadius.button,
                              ),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.all(AppSpacing.small),
                              child: Text(
                                b.notice!,
                                style: text.bodyMedium!.copyWith(
                                  color: AppColors.amberText,
                                ),
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
            ),
          ],
        ),
      ),
    );
  }
}
