import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/dev/state/dev_user_state.dart';
import '../../../core/layout/breakpoints.dart';
import '../data/booking.dart';
import '../state/booking_state.dart';
import 'widgets/booking_widgets.dart';

/// 店家看板正式頁面：店家人員看自己店家某一天的訂位，辦理入座、完成結算、取消
/// （`/booking/board`）。管理員要先選店家。
class ShopBoardPage extends ConsumerStatefulWidget {
  const ShopBoardPage({super.key});

  @override
  ConsumerState<ShopBoardPage> createState() => _ShopBoardPageState();
}

class _ShopBoardPageState extends ConsumerState<ShopBoardPage> {
  String? _shopId;
  late DateTime _date;

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
    final now = taipeiNow();
    _date = DateTime(now.year, now.month, now.day);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!_allowed) return;
      if (ref.read(bookingProvider).shops.isEmpty) await _n.loadShops();
      await _search();
    });
  }

  Future<void> _search() async {
    final shopId = _selectedShop;
    if (shopId == null) return;
    final day = isoDate(_date);
    await _n.loadBoard(
      shopId,
      '${day}T00:00:00+08:00',
      '${day}T23:59:59+08:00',
    );
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

    final isAdmin = user?.role == 'admin';
    final shopId = _shopId ?? user?.shopId;
    final shopNames = {for (final s in state.shops) s.id: s.name};
    VoidCallback? act(VoidCallback f) => state.loading ? null : f;

    return BookingScaffold(
      pageKey: const Key('shop-board-page'),
      title: '店家看板',
      current: 'board',
      showBoard: true,
      maxWidth: AppSpacing.contentMaxWidth(context.screenSize),
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
          BookingErrorBanner(message: state.message!, onRetry: _search),
          const SizedBox(height: AppSpacing.medium),
        ],
        if (shopId == null)
          const Padding(
            padding: EdgeInsets.all(AppSpacing.large),
            child: Center(child: Text('請先選擇店家')),
          )
        else if (state.loading && state.board.isEmpty)
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
                actions: [
                  if (b.status == 'confirmed') ...[
                    TextButton(
                      key: Key('board-cancel-${b.id}'),
                      onPressed: act(() => _cancel(b)),
                      child: const Text('取消'),
                    ),
                    FilledButton(
                      key: Key('board-seated-${b.id}'),
                      onPressed: act(() => _n.setStatus(b.id, 'seated')),
                      child: const Text('入座'),
                    ),
                  ],
                  if (b.status == 'seated')
                    FilledButton(
                      key: Key('board-complete-${b.id}'),
                      onPressed: act(() => _n.setStatus(b.id, 'completed')),
                      child: const Text('完成結算'),
                    ),
                ],
              ),
            ),
      ],
    );
  }
}
