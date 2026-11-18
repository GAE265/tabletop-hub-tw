import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/dev/state/dev_user_state.dart';
import '../../domains/booking/data/booking.dart';
import '../../domains/booking/state/booking_state.dart';

/// booking 查詢參考畫面：依狀態與日期時間篩選，下方顯示座位圖。
class BookingListProtoPage extends ConsumerStatefulWidget {
  const BookingListProtoPage({super.key});

  @override
  ConsumerState<BookingListProtoPage> createState() => _BookingListProtoPageState();
}

class _BookingListProtoPageState extends ConsumerState<BookingListProtoPage> {
  String? _status;
  DateTime? _fromDate;
  TimeOfDay? _fromTime;
  DateTime? _toDate;
  TimeOfDay? _toTime;
  String? _shopId;
  int? _seatingFloor;

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
      ref.read(bookingProvider.notifier).loadShops();
    });
  }

  BookingNotifier get _n => ref.read(bookingProvider.notifier);

  String? get _selectedShop {
    final user = ref.read(currentDevUserProvider);
    return _shopId ?? user?.shopId;
  }

  String? _dateTimeStr(DateTime? date, TimeOfDay? time) {
    if (date == null) return null;
    String two(int n) => n.toString().padLeft(2, '0');
    final t = time ?? const TimeOfDay(hour: 0, minute: 0);
    return '${date.year}-${two(date.month)}-${two(date.day)}T${two(t.hour)}:${two(t.minute)}:00+08:00';
  }

  void _search() {
    final from = _dateTimeStr(_fromDate, _fromTime);
    final to = _dateTimeStr(_toDate, _toTime);
    _n.loadMine(status: _status, fromDate: from, toDate: to);
    // 自動載入座位圖：有店家時自動查詢
    final shopId = _selectedShop;
    if (shopId != null) {
      _n.loadSeatingPlan(shopId, from: from, to: to, floor: _seatingFloor);
    }
  }

  Future<void> _pickDate(DateTime? current, ValueChanged<DateTime?> onPicked) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: current ?? now,
      firstDate: DateTime(2024),
      lastDate: DateTime(2030),
    );
    if (picked != null) onPicked(picked);
  }

  Future<void> _pickTime(TimeOfDay? current, ValueChanged<TimeOfDay?> onPicked) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: current ?? const TimeOfDay(hour: 0, minute: 0),
    );
    if (picked != null) onPicked(picked);
  }

  String _fmtDate(DateTime? d) {
    if (d == null) return '';
    String two(int n) => n.toString().padLeft(2, '0');
    return '${d.year}-${two(d.month)}-${two(d.day)}';
  }

  String _fmtTime(TimeOfDay? t) {
    if (t == null) return '';
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(t.hour)}:${two(t.minute)}';
  }

  double _planHeight(List<TableInfo> tables) {
    if (tables.isEmpty) return 200;
    double maxY = 0;
    for (final t in tables) {
      final bottom = t.y + t.height;
      if (bottom > maxY) maxY = bottom.toDouble();
    }
    return maxY + 20;
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bookingProvider);
    final user = ref.watch(currentDevUserProvider);
    final selectedShopId = _shopId ?? user?.shopId;

    return Scaffold(
      key: const Key('booking-list-proto-page'),
      appBar: AppBar(title: const Text('booking 查詢（參考畫面）')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  key: const Key('shop-id'),
                  initialValue: state.shops.any((s) => s.id == selectedShopId)
                      ? selectedShopId
                      : null,
                  decoration: const InputDecoration(labelText: '店家'),
                  items: [
                    for (final shop in state.shops)
                      DropdownMenuItem(value: shop.id, child: Text(shop.name)),
                  ],
                  onChanged: (value) => setState(() => _shopId = value),
                ),
              ),
              TextButton(
                key: const Key('shop-reload'),
                onPressed: state.loading ? null : _n.loadShops,
                child: const Text('重新載入店家'),
              ),
            ],
          ),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String?>(
                  key: const Key('status-filter'),
                  initialValue: _status,
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
                child: InkWell(
                  key: const Key('from-date-picker'),
                  onTap: () => _pickDate(_fromDate, (d) => setState(() => _fromDate = d)),
                  child: InputDecorator(
                    decoration: const InputDecoration(labelText: '開始日期'),
                    child: Text(_fmtDate(_fromDate)),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: InkWell(
                  key: const Key('from-time-picker'),
                  onTap: () => _pickTime(_fromTime, (t) => setState(() => _fromTime = t)),
                  child: InputDecorator(
                    decoration: const InputDecoration(labelText: '開始時間'),
                    child: Text(_fmtTime(_fromTime)),
                  ),
                ),
              ),
            ],
          ),
          Row(
            children: [
              Expanded(
                child: InkWell(
                  key: const Key('to-date-picker'),
                  onTap: () => _pickDate(_toDate, (d) => setState(() => _toDate = d)),
                  child: InputDecorator(
                    decoration: const InputDecoration(labelText: '結束日期'),
                    child: Text(_fmtDate(_toDate)),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: InkWell(
                  key: const Key('to-time-picker'),
                  onTap: () => _pickTime(_toTime, (t) => setState(() => _toTime = t)),
                  child: InputDecorator(
                    decoration: const InputDecoration(labelText: '結束時間'),
                    child: Text(_fmtTime(_toTime)),
                  ),
                ),
              ),
            ],
          ),
          Row(
            children: [
              if (_fromDate != null || _toDate != null || _fromTime != null || _toTime != null)
                TextButton(
                  onPressed: () => setState(() {
                    _fromDate = null;
                    _fromTime = null;
                    _toDate = null;
                    _toTime = null;
                  }),
                  child: const Text('清除'),
                ),
              const Spacer(),
              ElevatedButton(
                key: const Key('search'),
                onPressed: state.loading ? null : _search,
                child: const Text('查詢'),
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
          if (state.mine.isEmpty && !state.loading) const Text('沒有符合的訂位'),
          for (final b in state.mine)
            Card(
              key: Key('booking-${b.id}'),
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${b.shopName.isNotEmpty ? "${b.shopName}　" : ""}#${b.id} ${b.reservationCode}　狀態：${b.status}'),
                    Text('${b.startAt} ~ ${b.endAt}　${b.partySize} 人'),
                    Text(
                      '桌位：${b.tableCodes.join(', ')}　預估 ${b.estimatedFee.venueFee} 元'
                      '${b.finalFee == null ? '' : '　結算 ${b.finalFee} 元'}',
                    ),
                    if (b.notice != null) Text('提醒：${b.notice}'),
                    if (b.status != 'cancelled') ...[
                      const SizedBox(height: 4),
                      TextButton(
                        key: Key('cancel-${b.id}'),
                        onPressed: state.loading
                            ? null
                            : () => ref.read(bookingProvider.notifier).setStatus(b.id, 'cancelled'),
                        child: const Text('取消'),
                      ),
                    ],
                  ],
                ),
              ),
            ),

          // ── 座位圖 ──
          const Divider(),
          Row(
            children: [
              const Text('座位圖'),
              const SizedBox(width: 8),
              DropdownButton<int?>(
                key: const Key('seating-floor'),
                value: _seatingFloor,
                hint: const Text('全部樓層'),
                items: const [
                  DropdownMenuItem(value: null, child: Text('全部樓層')),
                  DropdownMenuItem(value: 1, child: Text('1F')),
                  DropdownMenuItem(value: -1, child: Text('B1')),
                ],
                onChanged: (v) => setState(() => _seatingFloor = v),
              ),
            ],
          ),
          if (state.seatingPlan.isEmpty && !state.loading) const Text('尚未載入座位圖'),
          for (final plan in state.seatingPlan) ...[
            Text('${plan.floor == -1 ? 'B1' : '${plan.floor}F'}　${plan.tables.length} 張桌子'),
            SizedBox(
              height: _planHeight(plan.tables),
              width: double.infinity,
              child: Stack(
                children: [
                  for (final table in plan.tables)
                    Positioned(
                      left: table.x.toDouble(),
                      top: table.y.toDouble(),
                      child: GestureDetector(
                        onTap: () => _n.selectTable(table),
                        child: Container(
                          key: Key('table-${table.id}'),
                          width: table.width.toDouble(),
                          height: table.height.toDouble(),
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: table.isMine
                                  ? Colors.blue
                                  : table.status == 'available'
                                      ? Colors.grey
                                      : Colors.red,
                              width: 2,
                            ),
                            color: table.id == state.selectedTable?.id
                                ? Colors.blue.shade50
                                : null,
                          ),
                          alignment: Alignment.center,
                          child: Text(
                            table.tableCode,
                            style: const TextStyle(fontSize: 11),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
          if (state.selectedTable != null) ...[
            const SizedBox(height: 8),
            _tableDetail(state.selectedTable!),
          ],
        ],
      ),
    );
  }

  Widget _tableDetail(TableInfo table) {
    return Card(
      key: const Key('table-detail'),
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${table.tableCode}（${table.maxCapacity} 人）　${table.status}'),
            Text('座標 (${table.x}, ${table.y})　${table.width}x${table.height}'),
            if (table.name != null) Text('名稱：${table.name}'),
            if (table.booking != null)
              Text(
                '訂位：#${table.booking!.id} ${table.booking!.reservationCode}　'
                '${table.booking!.partySize} 人　${table.booking!.status}',
              ),
          ],
        ),
      ),
    );
  }
}
