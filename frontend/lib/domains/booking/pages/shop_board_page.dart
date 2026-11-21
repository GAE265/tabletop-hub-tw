import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/dev/state/dev_user_state.dart';
import '../../../core/layout/breakpoints.dart';
import '../data/booking.dart';
import '../state/booking_overtime.dart';
import '../state/booking_state.dart';
import 'widgets/booking_widgets.dart';
import 'widgets/seating_plan.dart';

/// 店家看板正式頁面：店家人員看自己店家某一天的座位圖與訂位，辦理客人到店、離店結帳、取消
/// （`/booking/board`）。管理員要先選店家。
///
/// 已入座且超過結束時間的訂位標示「已超時」，每分鐘重新計算（add-booking-notifications D5）。
class ShopBoardPage extends ConsumerStatefulWidget {
  const ShopBoardPage({super.key});

  @override
  ConsumerState<ShopBoardPage> createState() => _ShopBoardPageState();
}

class _ShopBoardPageState extends ConsumerState<ShopBoardPage> {
  String? _shopId;
  late DateTime _date;

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
      return BookingScaffold(
        pageKey: const Key('shop-board-page'),
        title: '店家看板',
        current: 'board',
        showBoard: false,
        children: [
          Padding(
            key: const Key('board-no-permission'),
            padding: const EdgeInsets.all(AppSpacing.large),
            child: Text(
              '只有店家人員可以查看店家看板',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
        ],
      );
    }

    final now = ref.read(bookingClockProvider)();
    final isAdmin = user?.role == 'admin';
    final wide = context.screenSize != ScreenSize.mobile;
    final shopId = _shopId ?? user?.shopId;
    final shopNames = {for (final s in state.shops) s.id: s.name};
    VoidCallback? act(VoidCallback f) => state.loading ? null : f;
    final list = <Widget>[
      if (state.loading && state.board.isEmpty)
        const Padding(
          padding: EdgeInsets.all(AppSpacing.large),
          child: Center(child: CircularProgressIndicator()),
        )
      else if (state.board.isEmpty && !state.isError)
        const Padding(
          padding: EdgeInsets.all(AppSpacing.large),
          child: Center(child: Text('這天沒有訂位')),
        )
      else
        for (final b in state.board)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.medium),
            child: BookingCard(
              key: Key('board-card-${b.id}'),
              booking: b,
              shopName: null,
              overtimeMinutes: overtimeMinutes(b.status, b.endAt, now),
              actions: [
                if (b.status == 'confirmed') ...[
                  TextButton(
                    key: Key('board-cancel-${b.id}'),
                    onPressed: act(() => _cancel(b)),
                    child: const Text('取消'),
                  ),
                  OutlinedButton(
                    key: Key('board-change-table-${b.id}'),
                    onPressed: act(() => _n.startChangeTable(b.id)),
                    child: const Text('換桌'),
                  ),
                  FilledButton(
                    key: Key('board-seated-${b.id}'),
                    onPressed: act(() => _n.setStatus(b.id, 'seated')),
                    child: const Text('客人到店'),
                  ),
                ],
                if (b.status == 'seated')
                  FilledButton(
                    key: Key('board-complete-${b.id}'),
                    onPressed: act(() => _n.setStatus(b.id, 'completed')),
                    child: const Text('離店結帳'),
                  ),
              ],
            ),
          ),
    ];

    return BookingScaffold(
      pageKey: const Key('shop-board-page'),
      title: '店家看板',
      current: 'board',
      showBoard: true,
      maxWidth: wide
          ? AppSpacing.splitContentMaxWidth
          : AppSpacing.contentMaxWidth(context.screenSize),
      children: [
        if (isAdmin) ...[
          KeyedSubtree(
            key: const Key('booking-shop'),
            child: DropdownButtonFormField<String>(
              key: ValueKey((state.shops.length, shopId)),
              initialValue: shopNames.containsKey(shopId) ? shopId : null,
              decoration: const InputDecoration(
                labelText: '店家',
                prefixIcon: Icon(Icons.storefront_outlined),
              ),
              items: [
                for (final s in state.shops)
                  DropdownMenuItem(value: s.id, child: Text(s.name)),
              ],
              onChanged: (v) {
                setState(() => _shopId = v);
                _search();
              },
            ),
          ),
          const SizedBox(height: AppSpacing.medium),
        ] else if (shopNames[shopId] != null) ...[
          Text(
            shopNames[shopId]!,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: AppSpacing.medium),
        ],
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                key: const Key('board-date'),
                onPressed: _pickDate,
                icon: const Icon(Icons.calendar_today_outlined),
                label: Text(shortDate(_date)),
              ),
            ),
            const SizedBox(width: AppSpacing.small),
            IconButton(
              key: const Key('board-search'),
              onPressed: act(_search),
              icon: const Icon(Icons.refresh),
              tooltip: '重新整理',
            ),
          ],
        ),
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
          const Padding(
            padding: EdgeInsets.all(AppSpacing.large),
            child: Center(child: Text('請先選擇店家')),
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
    return Card(
      key: const Key('board-seating'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('座位圖', style: Theme.of(context).textTheme.titleMedium),
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
  Widget _changeTableHint() => Row(
    key: const Key('board-change-table-hint'),
    children: [
      Expanded(
        child: Text(
          '請在座位圖點選要換到的桌子',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ),
      TextButton(
        key: const Key('board-change-table-cancel'),
        onPressed: _n.cancelChangeTable,
        child: const Text('取消選桌'),
      ),
    ],
  );
}
