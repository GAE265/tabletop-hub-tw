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
  String? _shopId;
  final _date = TextEditingController(text: _defaultDate());
  final _party = TextEditingController(text: '4');
  final _requests = TextEditingController();
  final _startCtrl = TextEditingController(text: '14:00');
  final _endCtrl = TextEditingController(text: '16:00');
  int? _seatingFloor;

  static String _defaultDate() {
    final d = DateTime.now().add(const Duration(days: 7));
    String two(int n) => n.toString().padLeft(2, '0');
    return '${d.year}-${two(d.month)}-${two(d.day)}';
  }

  @override
  void initState() {
    super.initState();
    for (final ctrl in [_date, _startCtrl, _endCtrl]) {
      ctrl.addListener(_onDateTimeChanged);
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(bookingProvider.notifier).loadShops().then((_) => _loadSeating());
    });
  }

  void _onDateTimeChanged() => _loadSeating();

  @override
  void dispose() {
    _date.dispose();
    _party.dispose();
    _requests.dispose();
    _startCtrl.dispose();
    _endCtrl.dispose();
    super.dispose();
  }

  String _startAt(TextEditingController c) =>
      '${_date.text.trim()}T${c.text.trim()}:00+08:00';
  String _endAt(TextEditingController c) =>
      '${_date.text.trim()}T${c.text.trim()}:00+08:00';

  String get _start => _startAt(_startCtrl);
  String get _end => _endAt(_endCtrl);
  int get _partySize => int.tryParse(_party.text.trim()) ?? 1;
  BookingNotifier get _n => ref.read(bookingProvider.notifier);

  String? get _selectedShop {
    final user = ref.read(currentDevUserProvider);
    return _shopId ?? user?.shopId;
  }

  void _requireShop(void Function(String shopId) run) {
    final shopId = _selectedShop;
    if (shopId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('請先選擇店家')),
      );
      return;
    }
    run(shopId);
  }

  void _loadSeating() {
    final shopId = _selectedShop;
    if (shopId == null) return;
    _n.loadSeatingPlan(shopId, from: _start, to: _end, floor: _seatingFloor);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bookingProvider);
    final user = ref.watch(currentDevUserProvider);
    final isStaff = user?.role == 'shop_staff' || user?.role == 'admin';
    final selectedShopId = _shopId ?? user?.shopId;

    return Scaffold(
      key: const Key('booking-proto-page'),
      appBar: AppBar(title: const Text('booking（參考畫面）')),
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
                  onChanged: (value) {
                    setState(() => _shopId = value);
                    _loadSeating();
                  },
                ),
              ),
              TextButton(
                key: const Key('shop-reload'),
                onPressed: state.loading ? null : _n.loadShops,
                child: const Text('重新載入店家'),
              ),
            ],
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
          Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('slot-start'),
                  controller: _startCtrl,
                  decoration: const InputDecoration(labelText: '開始 HH:mm'),
                ),
              ),
              Expanded(
                child: TextField(
                  key: const Key('slot-end'),
                  controller: _endCtrl,
                  decoration: const InputDecoration(labelText: '結束 HH:mm'),
                ),
              ),
            ],
          ),
          Wrap(
            spacing: 8,
            children: [
              ElevatedButton(
                key: const Key('quote'),
                onPressed: state.loading
                    ? null
                    : () => _requireShop(
                        (shopId) => _n.requestQuote(shopId, _partySize, _start, _end),
                      ),
                child: const Text('預估費用'),
              ),
              ElevatedButton(
                key: const Key('create'),
                onPressed: state.loading
                    ? null
                    : () => _requireShop(
                        (shopId) => _n.create(
                          shopId,
                          _partySize,
                          _start,
                          _end,
                          _requests.text.trim(),
                        ),
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
          if (state.quote != null)
            Text('預估 ${state.quote!.startAt} ~ ${state.quote!.endAt}：${state.quote!.fee.billableHours} 小時，${state.quote!.fee.venueFee} 元'
                '${state.quote!.tableCodes.isEmpty ? "" : "　桌位：${state.quote!.tableCodes.join(", ")}"}'),

          if (isStaff) ...[
            const Divider(),
            Row(
              children: [
                const Text('店員看板（依上方日期）'),
                TextButton(
                  key: const Key('load-board'),
                  onPressed: state.loading
                      ? null
                      : () => _requireShop(
                          (shopId) => _n.loadBoard(
                            shopId,
                            '${_date.text.trim()}T00:00:00+08:00',
                            '${_date.text.trim()}T23:59:59+08:00',
                          ),
                        ),
                  child: const Text('查詢'),
                ),
              ],
            ),
            if (state.board.isEmpty && !state.loading) const Text('沒有訂位'),
            for (final b in state.board) _row(b, state.loading, staff: true),
          ],

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
                onChanged: (v) {
                  setState(() => _seatingFloor = v);
                  _loadSeating();
                },
              ),
            ],
          ),
          if (state.seatingPlan.isEmpty && !state.loading) const Text('尚未載入座位圖'),
          for (final plan in state.seatingPlan) ...[
            Text('${plan.floor}F　${plan.tables.length} 張桌子'),
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

  double _planHeight(List<TableInfo> tables) {
    if (tables.isEmpty) return 200;
    double maxY = 0;
    for (final t in tables) {
      final bottom = t.y + t.height;
      if (bottom > maxY) maxY = bottom.toDouble();
    }
    return maxY + 20;
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
            Text('${b.shopName.isNotEmpty ? "${b.shopName}　" : ""}#${b.id} ${b.reservationCode}　狀態：${b.status}'),
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
