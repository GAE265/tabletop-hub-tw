import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/booking/data/booking.dart';
import '../../domains/booking/state/booking_state.dart';

/// booking 查詢參考畫面：依狀態與日期篩選。
class BookingListProtoPage extends ConsumerStatefulWidget {
  const BookingListProtoPage({super.key});

  @override
  ConsumerState<BookingListProtoPage> createState() => _BookingListProtoPageState();
}

class _BookingListProtoPageState extends ConsumerState<BookingListProtoPage> {
  String? _status;
  final _fromCtrl = TextEditingController();
  final _toCtrl = TextEditingController();

  static final _statusOptions = [
    (null, '全部'),
    ('confirmed', '已確認'),
    ('seated', '已入座'),
    ('completed', '已完成'),
    ('cancelled', '已取消'),
    ('no_show', '未出席'),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _search();
    });
  }

  @override
  void dispose() {
    _fromCtrl.dispose();
    _toCtrl.dispose();
    super.dispose();
  }

  BookingNotifier get _n => ref.read(bookingProvider.notifier);

  void _search() {
    _n.loadMine(
      status: _status,
      fromDate: _fromCtrl.text.trim().isEmpty ? null : _fromCtrl.text.trim(),
      toDate: _toCtrl.text.trim().isEmpty ? null : _toCtrl.text.trim(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bookingProvider);

    return Scaffold(
      key: const Key('booking-list-proto-page'),
      appBar: AppBar(title: const Text('booking 查詢（參考畫面）')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String?>(
                  key: const Key('status-filter'),
                  value: _status,
                  decoration: const InputDecoration(labelText: '狀態'),
                  items: [
                    for (final (value, label) in _statusOptions)
                      DropdownMenuItem(value: value, child: Text(label)),
                  ],
                  onChanged: (v) => setState(() => _status = v),
                ),
              ),
            ],
          ),
          Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('from-date'),
                  controller: _fromCtrl,
                  decoration: const InputDecoration(labelText: '開始日期 YYYY-MM-DD'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  key: const Key('to-date'),
                  controller: _toCtrl,
                  decoration: const InputDecoration(labelText: '結束日期 YYYY-MM-DD'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ElevatedButton(
            key: const Key('search'),
            onPressed: state.loading ? null : _search,
            child: const Text('查詢'),
          ),
          if (state.loading) const LinearProgressIndicator(),
          if (state.message != null)
            Text(
              state.message!,
              key: const Key('message'),
              style: TextStyle(color: state.isError ? Colors.red : null),
            ),
          if (state.mine.isEmpty && !state.loading) const Text('沒有符合的訂位'),
          for (final b in state.mine)
            Card(
              key: Key('booking-${b.id}'),
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
                    const SizedBox(height: 4),
                    TextButton(
                      key: Key('cancel-${b.id}'),
                      onPressed: state.loading
                          ? null
                          : () => ref.read(bookingProvider.notifier).setStatus(b.id, 'cancelled'),
                      child: const Text('取消'),
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
