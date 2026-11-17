import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/dev/state/dev_user_state.dart';
import '../../../core/layout/breakpoints.dart';
import '../data/booking.dart';
import '../state/booking_state.dart';
import 'widgets/booking_widgets.dart';

/// 我的訂位正式頁面：依狀態篩選，可以取消（`/booking/mine`）。
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
  ('no_show', '未到店'),
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

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bookingProvider);
    final user = ref.watch(currentDevUserProvider);
    final shopNames = {for (final s in state.shops) s.id: s.name};

    return BookingScaffold(
      pageKey: const Key('my-bookings-page'),
      title: '我的訂位',
      current: 'mine',
      showBoard: user?.role == 'shop_staff' || user?.role == 'admin',
      maxWidth: AppSpacing.contentMaxWidth(context.screenSize),
      children: [
        Wrap(
          spacing: AppSpacing.small,
          runSpacing: AppSpacing.small,
          children: [
            for (final (value, label) in _statusFilters)
              ChoiceChip(
                key: Key('booking-status-${value ?? 'all'}'),
                label: Text(label),
                selected: _status == value,
                onSelected: state.loading
                    ? null
                    : (_) {
                        setState(() => _status = value);
                        _search();
                      },
              ),
          ],
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
              child: BookingCard(
                key: Key('booking-card-${b.id}'),
                booking: b,
                shopName: shopNames[b.shopId],
                actions: [
                  if (b.status == 'confirmed')
                    TextButton.icon(
                      key: Key('booking-cancel-${b.id}'),
                      onPressed: state.loading ? null : () => _cancel(b),
                      icon: const Icon(Icons.event_busy_outlined),
                      label: const Text('取消訂位'),
                    ),
                ],
              ),
            ),
      ],
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.filtered});

  final bool filtered;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.large),
      child: Column(
        children: [
          Icon(
            Icons.event_note_outlined,
            size: AppSizes.emptyStateIcon,
            color: scheme.outline,
          ),
          const SizedBox(height: AppSpacing.medium),
          Text(
            filtered ? '沒有符合的訂位' : '還沒有訂位',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.medium),
          FilledButton(
            key: const Key('booking-empty-new'),
            onPressed: () => context.go('/booking'),
            child: const Text('去訂位'),
          ),
        ],
      ),
    );
  }
}
