import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/dev/state/dev_user_state.dart';
import '../../domains/booking/data/booking.dart';
import '../../domains/booking/state/booking_state.dart';

/// booking 參考畫面：只用預設元件，不調顏色、字型、間距（AGENTS.md 5.4）。
/// 時間一律以台灣時間（+08:00）送出。
class BookingProtoPage extends ConsumerStatefulWidget {
  const BookingProtoPage({super.key});

  @override
  ConsumerState<BookingProtoPage> createState() => _BookingProtoPageState();
}

class _BookingProtoPageState extends ConsumerState<BookingProtoPage> {
  final _shop = TextEditingController();
  final _date = TextEditingController(text: _defaultDate());
  final _party = TextEditingController(text: '4');
  final _requests = TextEditingController();
  final _slots = <(TextEditingController, TextEditingController)>[
    (TextEditingController(text: '14:00'), TextEditingController(text: '16:00')),
  ];

  static String _defaultDate() {
    final d = DateTime.now().add(const Duration(days: 7));
    String two(int n) => n.toString().padLeft(2, '0');
    return '${d.year}-${two(d.month)}-${two(d.day)}';
  }

  @override
  void dispose() {
    _shop.dispose();
    _date.dispose();
    _party.dispose();
    _requests.dispose();
    for (final (a, b) in _slots) {
      a.dispose();
      b.dispose();
    }
    super.dispose();
  }

  Slot _slot(TextEditingController a, TextEditingController b) => Slot(
    startAt: '${_date.text.trim()}T${a.text.trim()}:00+08:00',
    endAt: '${_date.text.trim()}T${b.text.trim()}:00+08:00',
  );

  List<Slot> get _slotList => [for (final (a, b) in _slots) _slot(a, b)];
  int get _partySize => int.tryParse(_party.text.trim()) ?? 1;
  BookingNotifier get _n => ref.read(bookingProvider.notifier);

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bookingProvider);
    final user = ref.watch(currentDevUserProvider);
    if (_shop.text.isEmpty && user?.shopId != null) _shop.text = user!.shopId!;
    final isStaff = user?.role == 'shop_staff' || user?.role == 'admin';

    return Scaffold(
      key: const Key('booking-proto-page'),
      appBar: AppBar(title: const Text('booking（參考畫面）')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            key: const Key('shop-id'),
            controller: _shop,
            decoration: const InputDecoration(labelText: '店家 shop_id'),
          ),
          TextField(
            key: const Key('date'),
            controller: _date,
            decoration: const InputDecoration(labelText: '日期 YYYY-MM-DD'),
          ),
          TextField(
            key: const Key('party-size'),
            controller: _party,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: '人數'),
          ),
          TextField(
            key: const Key('special-requests'),
            controller: _requests,
            decoration: const InputDecoration(labelText: '特殊需求（選填）'),
          ),
          for (var i = 0; i < _slots.length; i++)
            Row(
              children: [
                Expanded(
                  child: TextField(
                    key: Key('slot-start-$i'),
                    controller: _slots[i].$1,
                    decoration: const InputDecoration(labelText: '開始 HH:mm'),
                  ),
                ),
                Expanded(
                  child: TextField(
                    key: Key('slot-end-$i'),
                    controller: _slots[i].$2,
                    decoration: const InputDecoration(labelText: '結束 HH:mm'),
                  ),
                ),
                if (_slots.length > 1)
                  IconButton(
                    key: Key('slot-remove-$i'),
                    icon: const Icon(Icons.remove_circle_outline),
                    onPressed: () => setState(() => _slots.removeAt(i)),
                  ),
              ],
            ),
          Wrap(
            spacing: 8,
            children: [
              OutlinedButton(
                key: const Key('slot-add'),
                onPressed: () => setState(
                  () => _slots.add((
                    TextEditingController(text: '18:00'),
                    TextEditingController(text: '19:30'),
                  )),
                ),
                child: const Text('新增時段'),
              ),
              ElevatedButton(
                key: const Key('quote'),
                onPressed: state.loading
                    ? null
                    : () => _n.requestQuote(_shop.text.trim(), _partySize, _slotList),
                child: const Text('預估費用'),
              ),
              ElevatedButton(
                key: const Key('create'),
                onPressed: state.loading
                    ? null
                    : () => _n.create(
                        _shop.text.trim(),
                        _partySize,
                        _slotList,
                        _requests.text.trim(),
                      ),
                child: const Text('建立訂位'),
              ),
            ],
          ),
          if (state.loading) const LinearProgressIndicator(),
          if (state.message != null)
            Text(
              state.message!,
              key: const Key('message'),
              style: TextStyle(color: state.isError ? Colors.red : null),
            ),
          for (final q in state.quote)
            Text('預估 ${q.startAt} ~ ${q.endAt}：${q.fee.billableHours} 小時，${q.fee.venueFee} 元'),
          const Divider(),
          Row(
            children: [
              const Text('我的訂位'),
              TextButton(
                key: const Key('load-mine'),
                onPressed: state.loading ? null : _n.loadMine,
                child: const Text('重新整理'),
              ),
            ],
          ),
          if (state.mine.isEmpty && !state.loading) const Text('沒有訂位'),
          for (final b in state.mine) _row(b, state.loading, staff: false),
          if (isStaff) ...[
            const Divider(),
            Row(
              children: [
                const Text('店員看板（依上方日期）'),
                TextButton(
                  key: const Key('load-board'),
                  onPressed: state.loading
                      ? null
                      : () => _n.loadBoard(
                          _shop.text.trim(),
                          '${_date.text.trim()}T00:00:00+08:00',
                          '${_date.text.trim()}T23:59:59+08:00',
                        ),
                  child: const Text('查詢'),
                ),
              ],
            ),
            if (state.board.isEmpty && !state.loading) const Text('沒有訂位'),
            for (final b in state.board) _row(b, state.loading, staff: true),
          ],
        ],
      ),
    );
  }

  Widget _row(Booking b, bool busy, {required bool staff}) {
    final prefix = staff ? 'board' : 'mine';
    VoidCallback? act(VoidCallback f) => busy ? null : f;
    return Card(
      key: Key('$prefix-${b.id}'),
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('#${b.id} ${b.reservationCode}　狀態：${b.status}'),
            Text('${b.startAt} ~ ${b.endAt}　${b.partySize} 人'),
            Text(
              '桌位：${b.tableCodes.join(', ')}　預估 ${b.estimatedFee.venueFee} 元'
              '${b.finalFee == null ? '' : '　結算 ${b.finalFee} 元'}',
            ),
            if (b.notice != null) Text('提醒：${b.notice}'),
            Wrap(
              spacing: 8,
              children: [
                TextButton(
                  key: Key('$prefix-${b.id}-get'),
                  onPressed: act(() => _n.refreshOne(b.id)),
                  child: const Text('查詢'),
                ),
                TextButton(
                  key: Key('$prefix-${b.id}-modify'),
                  onPressed: act(
                    () => _n.modify(
                      b.id,
                      _slot(_slots.first.$1, _slots.first.$2),
                      _partySize,
                    ),
                  ),
                  child: const Text('改成上方第一個時段與人數'),
                ),
                TextButton(
                  key: Key('$prefix-${b.id}-cancel'),
                  onPressed: act(() => _n.setStatus(b.id, 'cancelled')),
                  child: const Text('取消'),
                ),
                if (staff) ...[
                  TextButton(
                    key: Key('$prefix-${b.id}-seated'),
                    onPressed: act(() => _n.setStatus(b.id, 'seated')),
                    child: const Text('入座'),
                  ),
                  TextButton(
                    key: Key('$prefix-${b.id}-completed'),
                    onPressed: act(() => _n.setStatus(b.id, 'completed')),
                    child: const Text('完成結算'),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}
