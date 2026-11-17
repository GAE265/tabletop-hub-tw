import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/dev/state/dev_user_state.dart';
import '../../../core/layout/breakpoints.dart';
import '../data/booking.dart';
import '../state/booking_state.dart';
import 'widgets/booking_widgets.dart';

/// 訂位正式頁面：選店家、日期、時段、人數，預估費用後送出（`/booking`）。
class NewBookingPage extends ConsumerStatefulWidget {
  const NewBookingPage({super.key});

  @override
  ConsumerState<NewBookingPage> createState() => _NewBookingPageState();
}

/// 開始與結束時間的選項：每 30 分鐘一格。是否在營業時間內由後端判斷。
final _timeSlots = [
  for (var m = 0; m < 24 * 60; m += 30)
    '${(m ~/ 60).toString().padLeft(2, '0')}:${(m % 60).toString().padLeft(2, '0')}',
];

const _minParty = 1;
const _maxParty = 30;

/// 最多可以訂幾個月後（與後端相同）。
const _maxAdvanceMonths = 3;

class _NewBookingPageState extends ConsumerState<NewBookingPage> {
  String? _shopId;
  bool _shopMissing = false;
  late DateTime _date;
  String _start = '14:00';
  String _end = '16:00';
  int _party = 4;
  final _requests = TextEditingController();

  BookingNotifier get _n => ref.read(bookingProvider.notifier);

  @override
  void initState() {
    super.initState();
    final today = taipeiNow();
    _date = DateTime(
      today.year,
      today.month,
      today.day,
    ).add(const Duration(days: 7));
    WidgetsBinding.instance.addPostFrameCallback((_) => _n.loadShops());
  }

  @override
  void dispose() {
    _requests.dispose();
    super.dispose();
  }

  String? get _selectedShop =>
      _shopId ?? ref.read(currentDevUserProvider)?.shopId;

  String _at(String hm) => '${isoDate(_date)}T$hm:00+08:00';

  /// 沒選店家時在欄位下方提示，不送出。
  String? _requireShop() {
    final shopId = _selectedShop;
    setState(() => _shopMissing = shopId == null);
    return shopId;
  }

  void _quote() {
    final shopId = _requireShop();
    if (shopId == null) return;
    _n.requestQuote(shopId, _party, _at(_start), _at(_end));
  }

  Future<void> _submit() async {
    final shopId = _requireShop();
    if (shopId == null) return;
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    final requests = _requests.text.trim();
    await _n.create(
      shopId,
      _party,
      _at(_start),
      _at(_end),
      requests.isEmpty ? null : requests,
    );
    if (!mounted || ref.read(bookingProvider).isError) return;
    router.go('/booking/mine');
    messenger.showSnackBar(const SnackBar(content: Text('訂位成功')));
  }

  Future<void> _pickDate() async {
    final today = taipeiNow();
    final first = DateTime(today.year, today.month, today.day);
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: first,
      lastDate: DateTime(
        first.year,
        first.month + _maxAdvanceMonths,
        first.day,
      ),
    );
    if (picked != null) setState(() => _date = picked);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bookingProvider);
    final user = ref.watch(currentDevUserProvider);
    final isStaff = user?.role == 'shop_staff' || user?.role == 'admin';
    final wide = context.screenSize != ScreenSize.mobile;

    final form = _BookingForm(
      key: const Key('booking-form'),
      shops: [for (final s in state.shops) (s.id, s.name)],
      selectedShop: _shopId ?? user?.shopId,
      shopMissing: _shopMissing,
      onShop: (v) => setState(() {
        _shopId = v;
        _shopMissing = false;
      }),
      date: _date,
      onPickDate: _pickDate,
      start: _start,
      end: _end,
      onStart: (v) => setState(() => _start = v),
      onEnd: (v) => setState(() => _end = v),
      party: _party,
      onParty: (v) => setState(() => _party = v.clamp(_minParty, _maxParty)),
      requests: _requests,
      busy: state.loading,
      onQuote: _quote,
      onSubmit: _submit,
    );
    final quote = state.quote == null ? null : _QuoteCard(state.quote!);

    return BookingScaffold(
      pageKey: const Key('booking-page'),
      title: '訂位',
      current: 'new',
      showBoard: isStaff,
      maxWidth: wide ? AppSpacing.splitContentMaxWidth : null,
      children: [
        if (state.isError && state.message != null) ...[
          BookingErrorBanner(
            message: state.message!,
            onRetry: state.shops.isEmpty ? _n.loadShops : null,
            retryKey: const Key('booking-retry-shops'),
          ),
          const SizedBox(height: AppSpacing.medium),
        ],
        if (state.loading) ...[
          const LinearProgressIndicator(),
          const SizedBox(height: AppSpacing.small),
        ],
        if (wide)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: form),
              const SizedBox(width: AppSpacing.large),
              Expanded(child: quote ?? const _QuoteHint()),
            ],
          )
        else ...[
          form,
          if (quote != null) ...[
            const SizedBox(height: AppSpacing.medium),
            quote,
          ],
        ],
      ],
    );
  }
}

class _BookingForm extends StatelessWidget {
  const _BookingForm({
    required this.shops,
    required this.selectedShop,
    required this.shopMissing,
    required this.onShop,
    required this.date,
    required this.onPickDate,
    required this.start,
    required this.end,
    required this.onStart,
    required this.onEnd,
    required this.party,
    required this.onParty,
    required this.requests,
    required this.busy,
    required this.onQuote,
    required this.onSubmit,
    super.key,
  });

  final List<(String, String)> shops;
  final String? selectedShop;
  final bool shopMissing;
  final ValueChanged<String?> onShop;
  final DateTime date;
  final VoidCallback onPickDate;
  final String start;
  final String end;
  final ValueChanged<String> onStart;
  final ValueChanged<String> onEnd;
  final int party;
  final ValueChanged<int> onParty;
  final TextEditingController requests;
  final bool busy;
  final VoidCallback onQuote;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final initialShop = shops.any((s) => s.$1 == selectedShop)
        ? selectedShop
        : null;
    Widget timeField(
      String label,
      String key,
      String value,
      ValueChanged<String> onChanged,
    ) => DropdownButtonFormField<String>(
      key: Key(key),
      initialValue: value,
      decoration: InputDecoration(labelText: label),
      items: [
        for (final t in _timeSlots) DropdownMenuItem(value: t, child: Text(t)),
      ],
      onChanged: (v) => v == null ? null : onChanged(v),
    );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            KeyedSubtree(
              key: const Key('booking-shop'),
              child: DropdownButtonFormField<String>(
                // 店家清單載入後重建，才會帶入店家人員所屬的店家
                key: ValueKey((shops.length, initialShop)),
                initialValue: initialShop,
                decoration: InputDecoration(
                  labelText: '店家',
                  prefixIcon: const Icon(Icons.storefront_outlined),
                  errorText: shopMissing ? '請先選擇店家' : null,
                ),
                items: [
                  for (final (id, name) in shops)
                    DropdownMenuItem(value: id, child: Text(name)),
                ],
                onChanged: onShop,
              ),
            ),
            const SizedBox(height: AppSpacing.medium),
            OutlinedButton.icon(
              key: const Key('booking-date'),
              onPressed: onPickDate,
              icon: const Icon(Icons.calendar_today_outlined),
              label: Text('日期：${shortDate(date)}'),
            ),
            const SizedBox(height: AppSpacing.medium),
            Row(
              children: [
                Expanded(
                  child: timeField('開始', 'booking-start', start, onStart),
                ),
                const SizedBox(width: AppSpacing.medium),
                Expanded(child: timeField('結束', 'booking-end', end, onEnd)),
              ],
            ),
            const SizedBox(height: AppSpacing.medium),
            Row(
              children: [
                const Text('人數'),
                const Spacer(),
                IconButton.outlined(
                  key: const Key('booking-party-minus'),
                  onPressed: party > _minParty
                      ? () => onParty(party - 1)
                      : null,
                  icon: const Icon(Icons.remove),
                  tooltip: '減少人數',
                ),
                SizedBox(
                  key: const Key('booking-party-size'),
                  width: AppSizes.minTouchTarget,
                  child: Text(
                    '$party',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                IconButton.outlined(
                  key: const Key('booking-party-plus'),
                  onPressed: party < _maxParty
                      ? () => onParty(party + 1)
                      : null,
                  icon: const Icon(Icons.add),
                  tooltip: '增加人數',
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.medium),
            TextField(
              key: const Key('booking-requests'),
              controller: requests,
              decoration: const InputDecoration(labelText: '特殊需求（選填）'),
              maxLines: 2,
            ),
            const SizedBox(height: AppSpacing.large),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    key: const Key('booking-quote'),
                    onPressed: busy ? null : onQuote,
                    child: const Text('預估費用'),
                  ),
                ),
                const SizedBox(width: AppSpacing.medium),
                Expanded(
                  child: FilledButton(
                    key: const Key('booking-submit'),
                    onPressed: busy ? null : onSubmit,
                    child: const Text('確認訂位'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _QuoteCard extends StatelessWidget {
  const _QuoteCard(this.quote);

  final QuoteResult quote;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Card(
      key: const Key('booking-quote-card'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('預估費用', style: text.titleMedium),
            const SizedBox(height: AppSpacing.small),
            Text(formatBookingRange(quote.startAt, quote.endAt)),
            const SizedBox(height: AppSpacing.small),
            Text(
              '${quote.fee.billableHours} 小時　場地費 ${quote.fee.venueFee} 元',
              style: text.titleLarge,
            ),
            if (quote.tableCodes.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.small),
              Text('安排桌位：${quote.tableCodes.join('、')}'),
            ],
          ],
        ),
      ),
    );
  }
}

class _QuoteHint extends StatelessWidget {
  const _QuoteHint();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.large),
        child: Text(
          '填好店家、時段與人數後，按「預估費用」看看費用與桌位',
          style: Theme.of(context).textTheme.bodyMedium!.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}
