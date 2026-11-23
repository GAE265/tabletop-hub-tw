import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../state/group_clock.dart';
import '../state/group_form_state.dart';
import '../state/group_labels.dart';
import '../state/group_pickers_state.dart';
import 'widgets/game_picker_field.dart';
import 'widgets/group_widgets.dart';

/// 開團／編輯表單。[groupId] 為 null 時是開團。
///
/// Stitch 版面（docs/ui/stitch/）：木紋背景，每個欄位各一張有厚度的卡片；
/// 人數用加減按鈕（最少 2 人，新開團沒填時預設 4 人）。
class GroupFormPage extends ConsumerStatefulWidget {
  const GroupFormPage({required this.initial, this.groupId, super.key});

  final GroupFormData initial;
  final String? groupId;

  @override
  ConsumerState<GroupFormPage> createState() => _GroupFormPageState();
}

class _GroupFormPageState extends ConsumerState<GroupFormPage> {
  late GroupFormData _data = widget.initial;
  late final _title = TextEditingController(text: widget.initial.title)
    ..addListener(_refresh);
  late final _fee = TextEditingController(text: widget.initial.fee);
  late final _description = TextEditingController(
    text: widget.initial.description,
  )..addListener(_refresh);

  /// 人數上限（含開團主）。沒填或填錯時從預設人數開始。
  late int _capacity =
      int.tryParse(widget.initial.capacity.trim()) ?? _defaultCapacity;

  bool get _editing => widget.groupId != null;

  /// 字數跟著輸入更新。
  void _refresh() => setState(() {});

  @override
  void dispose() {
    for (final c in [_title, _fee, _description]) {
      c.dispose();
    }
    super.dispose();
  }

  GroupFormData _collect() => _data.copyWith(
    title: _title.text,
    capacity: '$_capacity',
    fee: _fee.text,
    description: _description.text,
  );

  Future<void> _pickDate() async {
    final clock = ref.read(groupClockProvider);
    final today = dateOnly(clock.toLocal(clock.now()));
    final current = _data.date ?? today;
    // 只能選今天以後；編輯日期已過的揪團時，從今天開始選
    final initial = current.isBefore(today) ? today : current;
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: today,
      lastDate: DateTime(today.year + 1, 12, 31),
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
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    final text = Theme.of(context).textTheme;
    const gap = SizedBox(height: AppSpacing.medium);
    final start = _data.startTime;
    final end = _data.endTime;
    final length = start != null && end != null && end > start
        ? durationLabel(end - start)
        : null;

    final body = Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        // 欄位不多，一次全部建立（ListView 只建畫面上看得到的部分，送出按鈕會找不到）
        child: SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(
            AppSpacing.medium,
            AppSpacing.medium,
            AppSpacing.medium,
            AppSpacing.medium + bottomInset,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (!_editing) ...[const _Intro(), gap],
              if (!_editing) ...[
                _FieldCard(
                  key: const Key('group-form-shop'),
                  title: '聚會店家',
                  required: true,
                  child: _ShopField(
                    value: _data.shopId,
                    error: errors['shopId'],
                    onChanged: (id) =>
                        setState(() => _data = _data.copyWith(shopId: id)),
                  ),
                ),
                gap,
              ],
              _FieldCard(
                key: const Key('group-form-title'),
                title: '揪團標題',
                required: true,
                trailing: _Counter(
                  length: _title.text.characters.length,
                  max: _titleMax,
                ),
                child: TextField(
                  controller: _title,
                  maxLength: _titleMax,
                  decoration: InputDecoration(
                    hintText: '例如：卡坦島新手教學團',
                    errorText: errors['title'],
                    counterText: '',
                  ),
                ),
              ),
              gap,
              _FieldCard(
                key: const Key('group-form-time'),
                title: '日期與時段',
                required: true,
                trailing: length == null
                    ? null
                    : PillBadge(
                        label: length,
                        tone: PillTone.duration,
                        icon: Icons.schedule,
                      ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
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
                  ],
                ),
              ),
              gap,
              _FieldCard(
                key: const Key('group-form-capacity'),
                title: '人數上限（含開團主）',
                required: true,
                helper: errors['capacity'],
                helperIsError: true,
                child: _CapacityStepper(
                  value: _capacity,
                  onChanged: (value) => setState(() => _capacity = value),
                ),
              ),
              gap,
              _FieldCard(
                key: const Key('group-form-fee'),
                title: '每人費用（選填）',
                helper: '填 0 代表免費；不填就不顯示費用。',
                child: TextField(
                  controller: _fee,
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(
                    hintText: '例如：250',
                    suffixText: '元',
                    errorText: errors['fee'],
                  ),
                ),
              ),
              gap,
              _FieldCard(
                key: const Key('group-form-games'),
                title: '要玩的桌遊（選填，可複選）',
                trailing: _data.games.isEmpty
                    ? null
                    : PillBadge(
                        label: '已選 ${_data.games.length} 款',
                        tone: PillTone.accent,
                      ),
                child: GamePickerField(
                  selected: _data.games,
                  onChanged: (games) =>
                      setState(() => _data = _data.copyWith(games: games)),
                ),
              ),
              gap,
              _FieldCard(
                key: const Key('group-form-description'),
                title: '揪團說明（選填）',
                trailing: _Counter(
                  length: _description.text.characters.length,
                  max: _descriptionMax,
                ),
                child: TextField(
                  controller: _description,
                  maxLines: 4,
                  maxLength: _descriptionMax,
                  decoration: const InputDecoration(
                    hintText: '介紹這團的玩法、適合誰、要準備什麼',
                    counterText: '',
                  ),
                ),
              ),
              gap,
              if (state.error case final error?) ...[
                StatusBanner(text: error, isError: true),
                gap,
              ],
              ThickButton(
                style: ThickStyle.primary,
                expand: true,
                onPressed: state.submitting ? null : _submit,
                icon: _editing ? Icons.save_outlined : Icons.send_outlined,
                label: _editing ? '儲存' : '送出',
              ),
              if (state.submitting) ...[
                const SizedBox(height: AppSpacing.small),
                const Center(child: CircularProgressIndicator()),
              ],
              if (!_editing) ...[
                const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
                // 放在白底條上，文字才不會直接壓在木紋上
                GlassBar(
                  child: Text('送出後可以在揪團詳細頁修改或取消揪團', style: text.bodySmall),
                ),
              ],
            ],
          ),
        ),
      ),
    );

    return Scaffold(
      key: const Key('group-form-page'),
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: Text(_editing ? '編輯揪團' : '我要揪團'),
        // 放在木紋上，用半透明白底，文字才看得清楚
        backgroundColor: AppColors.headerGlass,
      ),
      body: WoodBackground.isPaintedAbove(context)
          ? body
          : WoodBackground(child: body),
    );
  }
}

/// 標題與說明的長度上限（和後端一致）。
const _titleMax = 100;
const _descriptionMax = 2000;

/// 新開團沒填人數時的預設人數。
const _defaultCapacity = 4;

/// 人數上限的最小值（和 validateGroupForm 一致）。
const _minCapacity = 2;

/// 開團說明卡：實際的流程，不提沒有的功能（自動訂位、自動成團）。
class _Intro extends StatelessWidget {
  const _Intro();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ThickCard(
      key: const Key('group-form-intro'),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '發起一場揪團',
              style: text.headlineMedium!.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              '填寫聚會資訊，送出後會出現在揪團月曆，其他玩家就能報名。',
              style: text.bodyLarge!.copyWith(color: AppColors.inkMuted),
            ),
            const SizedBox(height: AppSpacing.medium),
            DecoratedBox(
              decoration: BoxDecoration(
                color: AppColors.amberTint,
                borderRadius: BorderRadius.circular(AppRadius.button),
              ),
              child: Padding(
                padding: const EdgeInsets.all(
                  AppSpacing.small + AppSpacing.xSmall,
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.lightbulb_outline,
                      color: AppColors.amberText,
                    ),
                    const SizedBox(width: AppSpacing.small),
                    Expanded(
                      child: Text(
                        '開團後可以在揪團詳細頁的「團務操作」編輯、訂位、確定成團或取消揪團。',
                        style: text.bodyMedium!.copyWith(
                          color: AppColors.amberText,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 一個欄位的卡片：標題（必填加 ＊）、右上角的補充（字數、時數）、欄位與下方說明。
class _FieldCard extends StatelessWidget {
  const _FieldCard({
    required this.title,
    required this.child,
    this.required = false,
    this.trailing,
    this.helper,
    this.helperIsError = false,
    super.key,
  });

  final String title;
  final Widget child;
  final bool required;
  final Widget? trailing;
  final String? helper;
  final bool helperIsError;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ThickCard(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text.rich(
                    TextSpan(
                      text: title,
                      children: [
                        if (required)
                          const TextSpan(
                            text: ' ＊',
                            style: TextStyle(color: AppColors.primaryText),
                          ),
                      ],
                    ),
                    style: text.titleMedium!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                ?trailing,
              ],
            ),
            const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
            child,
            if (helper case final helper?) ...[
              const SizedBox(height: AppSpacing.small),
              Text(
                helper,
                style: text.bodySmall!.copyWith(
                  color: helperIsError ? AppColors.error : AppColors.inkMuted,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 字數，例如「17／100 字」。
class _Counter extends StatelessWidget {
  const _Counter({required this.length, required this.max});

  final int length;
  final int max;

  @override
  Widget build(BuildContext context) =>
      Text('$length／$max 字', style: Theme.of(context).textTheme.bodySmall);
}

/// 人數加減按鈕：中間是人數與「開團主 1 人＋募集 N 人」，最少 [_minCapacity] 人。
class _CapacityStepper extends StatelessWidget {
  const _CapacityStepper({required this.value, required this.onChanged});

  final int value;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.backgroundAlt,
        borderRadius: BorderRadius.circular(AppRadius.button),
        border: Border.all(color: AppColors.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.small),
        child: Row(
          children: [
            IconButton.outlined(
              key: const Key('group-capacity-minus'),
              tooltip: '減少一人',
              onPressed: value > _minCapacity
                  ? () => onChanged(value - 1)
                  : null,
              icon: const Icon(Icons.remove),
            ),
            Expanded(
              child: Column(
                children: [
                  Text(
                    '$value 人',
                    style: text.headlineSmall!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text('開團主 1 人＋募集 ${value - 1} 人', style: text.bodySmall),
                ],
              ),
            ),
            IconButton.outlined(
              key: const Key('group-capacity-plus'),
              tooltip: '增加一人',
              onPressed: () => onChanged(value + 1),
              icon: const Icon(Icons.add),
            ),
          ],
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
        decoration: InputDecoration(),
        child: Text('載入店家中…'),
      ),
      error: (err, _) => InputDecorator(
        decoration: InputDecoration(errorText: error),
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
        decoration: InputDecoration(
          errorText: error,
          prefixIcon: const Icon(Icons.storefront_outlined),
        ),
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
