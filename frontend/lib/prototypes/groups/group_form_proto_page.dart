import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/groups/state/group_form_state.dart';
import '../../domains/groups/state/groups_calendar_state.dart';

/// 開團／編輯表單參考畫面。[groupId] 為 null 時是開團。
class GroupFormProtoPage extends ConsumerStatefulWidget {
  const GroupFormProtoPage({required this.initial, this.groupId, super.key});

  final GroupFormData initial;
  final String? groupId;

  @override
  ConsumerState<GroupFormProtoPage> createState() => _GroupFormProtoPageState();
}

class _GroupFormProtoPageState extends ConsumerState<GroupFormProtoPage> {
  late GroupFormData _data = widget.initial;
  late final _shopId = TextEditingController(text: widget.initial.shopId);
  late final _title = TextEditingController(text: widget.initial.title);
  late final _capacity = TextEditingController(text: widget.initial.capacity);
  late final _fee = TextEditingController(text: widget.initial.fee);
  late final _gameId = TextEditingController(text: widget.initial.gameId);
  late final _description = TextEditingController(
    text: widget.initial.description,
  );

  bool get _editing => widget.groupId != null;

  @override
  void dispose() {
    for (final c in [_shopId, _title, _capacity, _fee, _gameId, _description]) {
      c.dispose();
    }
    super.dispose();
  }

  GroupFormData _collect() => _data.copyWith(
    shopId: _shopId.text,
    title: _title.text,
    capacity: _capacity.text,
    fee: _fee.text,
    gameId: _gameId.text,
    description: _description.text,
  );

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _data.date ?? now,
      firstDate: DateTime(now.year, now.month, now.day),
      lastDate: DateTime(now.year + 1, 12, 31),
    );
    if (picked != null) setState(() => _data = _data.copyWith(date: picked));
  }

  Future<void> _pickTime({required bool start}) async {
    final current = start ? _data.startTime : _data.endTime;
    final picked = await showTimePicker(
      context: context,
      initialTime: current == null
          ? const TimeOfDay(hour: 19, minute: 0)
          : TimeOfDay(
              hour: current.inHours,
              minute: current.inMinutes.remainder(60),
            ),
    );
    if (picked == null) return;
    final value = Duration(hours: picked.hour, minutes: picked.minute);
    setState(
      () => _data = start
          ? _data.copyWith(startTime: value)
          : _data.copyWith(endTime: value),
    );
  }

  Future<void> _submit() async {
    _data = _collect();
    final group = await ref
        .read(groupFormProvider.notifier)
        .submit(_data, groupId: widget.groupId);
    if (group != null && mounted) Navigator.of(context).pop();
  }

  String _formatTime(Duration? value) {
    if (value == null) return '未選擇';
    final h = value.inHours.toString().padLeft(2, '0');
    final m = value.inMinutes.remainder(60).toString().padLeft(2, '0');
    return '$h:$m';
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(groupFormProvider);
    final errors = state.fieldErrors;
    final shops = ref.watch(knownShopsProvider);
    final date = _data.date;
    return Scaffold(
      appBar: AppBar(title: Text(_editing ? '編輯揪團（參考畫面）' : '我要開團（參考畫面）')),
      body: ListView(
        children: [
          if (!_editing) ...[
            DropdownButton<String>(
              hint: const Text('選擇店家（當月揪團出現過的店家）'),
              value: shops.any((s) => s.id == _shopId.text)
                  ? _shopId.text
                  : null,
              onChanged: (id) => setState(() => _shopId.text = id ?? ''),
              items: [
                for (final shop in shops)
                  DropdownMenuItem(value: shop.id, child: Text(shop.name)),
              ],
            ),
            TextField(
              controller: _shopId,
              decoration: InputDecoration(
                labelText: '或直接輸入店家 ID（店家清單 API 完成前暫用）',
                errorText: errors['shopId'],
              ),
            ),
          ],
          TextField(
            controller: _title,
            decoration: InputDecoration(
              labelText: '標題',
              errorText: errors['title'],
            ),
          ),
          ListTile(
            title: Text(
              date == null
                  ? '日期：未選擇'
                  : '日期：${date.year}/${date.month}/${date.day}',
            ),
            subtitle: errors['date'] == null ? null : Text(errors['date']!),
            trailing: TextButton(
              onPressed: _pickDate,
              child: const Text('選擇日期'),
            ),
          ),
          ListTile(
            title: Text('開始時間：${_formatTime(_data.startTime)}'),
            subtitle: errors['startTime'] == null
                ? null
                : Text(errors['startTime']!),
            trailing: TextButton(
              onPressed: () => _pickTime(start: true),
              child: const Text('選擇時間'),
            ),
          ),
          ListTile(
            title: Text('結束時間：${_formatTime(_data.endTime)}'),
            subtitle: errors['endTime'] == null
                ? null
                : Text(errors['endTime']!),
            trailing: TextButton(
              onPressed: () => _pickTime(start: false),
              child: const Text('選擇時間'),
            ),
          ),
          TextField(
            controller: _capacity,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              labelText: '人數上限（含開團主）',
              errorText: errors['capacity'],
            ),
          ),
          TextField(
            controller: _fee,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              labelText: '每人費用（選填，元）',
              errorText: errors['fee'],
            ),
          ),
          TextField(
            controller: _gameId,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              labelText: '遊戲 ID（選填）',
              errorText: errors['gameId'],
            ),
          ),
          TextField(
            controller: _description,
            maxLines: 3,
            decoration: const InputDecoration(labelText: '簡介（選填）'),
          ),
          if (state.error != null) ListTile(title: Text('錯誤：${state.error!}')),
          if (state.submitting)
            const Center(child: CircularProgressIndicator())
          else
            ElevatedButton(
              onPressed: _submit,
              child: Text(_editing ? '儲存' : '送出'),
            ),
        ],
      ),
    );
  }
}
