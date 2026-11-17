import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/layout/breakpoints.dart';
import '../state/group_form_state.dart';
import '../state/group_labels.dart';
import '../state/group_pickers_state.dart';
import 'widgets/game_picker_field.dart';
import 'widgets/group_widgets.dart';

/// 開團／編輯表單。[groupId] 為 null 時是開團。
class GroupFormPage extends ConsumerStatefulWidget {
  const GroupFormPage({required this.initial, this.groupId, super.key});

  final GroupFormData initial;
  final String? groupId;

  @override
  ConsumerState<GroupFormPage> createState() => _GroupFormPageState();
}

class _GroupFormPageState extends ConsumerState<GroupFormPage> {
  late GroupFormData _data = widget.initial;
  late final _title = TextEditingController(text: widget.initial.title);
  late final _capacity = TextEditingController(text: widget.initial.capacity);
  late final _fee = TextEditingController(text: widget.initial.fee);
  late final _description = TextEditingController(
    text: widget.initial.description,
  );

  bool get _editing => widget.groupId != null;

  @override
  void dispose() {
    for (final c in [_title, _capacity, _fee, _description]) {
      c.dispose();
    }
    super.dispose();
  }

  GroupFormData _collect() => _data.copyWith(
    title: _title.text,
    capacity: _capacity.text,
    fee: _fee.text,
    description: _description.text,
  );

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final initial = _data.date ?? today;
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: initial.isBefore(today) ? initial : today,
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

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(groupFormProvider);
    final errors = state.fieldErrors;
    final date = _data.date;
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    const gap = SizedBox(height: AppSpacing.medium);

    return Scaffold(
      key: const Key('group-form-page'),
      appBar: AppBar(title: Text(_editing ? '編輯揪團' : '我要開團')),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.medium),
            children: [
              if (!_editing) ...[
                _ShopField(
                  value: _data.shopId,
                  error: errors['shopId'],
                  onChanged: (id) =>
                      setState(() => _data = _data.copyWith(shopId: id)),
                ),
                gap,
              ],
              TextField(
                controller: _title,
                decoration: InputDecoration(
                  labelText: '標題',
                  errorText: errors['title'],
                ),
              ),
              gap,
              _PickerField(
                label: '日期',
                value: date == null ? null : formatDate(date),
                error: errors['date'],
                icon: Icons.event_outlined,
                onTap: _pickDate,
              ),
              gap,
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: _PickerField(
                      label: '開始時間',
                      value: formatTimeOfDay(_data.startTime),
                      error: errors['startTime'],
                      icon: Icons.schedule,
                      onTap: () => _pickTime(start: true),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.small),
                  Expanded(
                    child: _PickerField(
                      label: '結束時間',
                      value: formatTimeOfDay(_data.endTime),
                      error: errors['endTime'],
                      icon: Icons.schedule,
                      onTap: () => _pickTime(start: false),
                    ),
                  ),
                ],
              ),
              gap,
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: TextField(
                      controller: _capacity,
                      keyboardType: TextInputType.number,
                      decoration: InputDecoration(
                        labelText: '人數上限（含開團主）',
                        errorText: errors['capacity'],
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.small),
                  Expanded(
                    child: TextField(
                      controller: _fee,
                      keyboardType: TextInputType.number,
                      decoration: InputDecoration(
                        labelText: '每人費用（選填）',
                        suffixText: '元',
                        errorText: errors['fee'],
                      ),
                    ),
                  ),
                ],
              ),
              gap,
              GamePickerField(
                selected: _data.games,
                onChanged: (games) =>
                    setState(() => _data = _data.copyWith(games: games)),
              ),
              gap,
              TextField(
                controller: _description,
                maxLines: 3,
                decoration: const InputDecoration(labelText: '簡介（選填）'),
              ),
              gap,
              if (state.error case final error?) ...[
                StatusBanner(text: error, isError: true),
                gap,
              ],
              FilledButton(
                onPressed: state.submitting ? null : _submit,
                child: state.submitting
                    ? const SizedBox.square(
                        dimension: AppSpacing.large,
                        child: CircularProgressIndicator(),
                      )
                    : Text(_editing ? '儲存' : '送出'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 點了會開啟選擇器的欄位（日期、時間），外觀與文字輸入框一致。
class _PickerField extends StatelessWidget {
  const _PickerField({
    required this.label,
    required this.value,
    required this.error,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final String? value;
  final String? error;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.button),
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          errorText: error,
          suffixIcon: Icon(icon),
        ),
        isEmpty: value == null,
        child: Text(value ?? ''),
      ),
    );
  }
}

/// 店家下拉選單：選項來自 `GET /api/v1/shops`。載入失敗時顯示錯誤與「重試」。
class _ShopField extends ConsumerWidget {
  const _ShopField({
    required this.value,
    required this.error,
    required this.onChanged,
  });

  final String value;
  final String? error;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final shops = ref.watch(shopOptionsProvider);
    return shops.when(
      loading: () => const InputDecorator(
        decoration: InputDecoration(labelText: '店家'),
        child: Text('載入店家中…'),
      ),
      error: (err, _) => InputDecorator(
        decoration: InputDecoration(labelText: '店家', errorText: error),
        child: Row(
          children: [
            Expanded(child: Text(err is ApiException ? err.message : '無法載入店家')),
            TextButton(
              onPressed: () => ref.invalidate(shopOptionsProvider),
              child: const Text('重試'),
            ),
          ],
        ),
      ),
      data: (items) => DropdownButtonFormField<String>(
        key: const Key('group-shop-field'),
        initialValue: items.any((s) => s.id == value) ? value : null,
        isExpanded: true,
        decoration: InputDecoration(labelText: '店家', errorText: error),
        hint: const Text('選擇店家'),
        onChanged: (id) => onChanged(id ?? ''),
        items: [
          for (final shop in items)
            DropdownMenuItem(value: shop.id, child: Text(shop.name)),
        ],
      ),
    );
  }
}
