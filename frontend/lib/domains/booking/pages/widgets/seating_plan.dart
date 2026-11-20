import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../data/booking.dart';
import '../../state/booking_overtime.dart';
import 'booking_widgets.dart';

/// 桌子在座位圖上的分類，決定顏色與圖例。
enum SeatTone {
  /// 這段時間沒有訂位。
  available,

  /// 這段時間已被訂走（店員看到的所有訂位、玩家看到的別人的訂位）。
  occupied,

  /// 玩家自己的訂位。
  mine,

  /// 客人已入座、超過結束時間還沒離店（只在店員看板出現，add-booking-notifications）。
  overtime,
}

/// 一張桌子與它在這段時間內的訂位。
///
/// 後端每筆訂位回傳一列，同一張桌在查詢時段有多筆訂位時會出現多次；
/// 畫面上一張桌只畫一次，訂位合併在 [bookings]。
class SeatGroup {
  const SeatGroup({
    required this.table,
    required this.bookings,
    required this.unavailable,
  });

  final TableInfo table;
  final List<BookingSummary> bookings;
  final bool unavailable;
}

/// 依桌子合併後端回傳的列，保留第一次出現的順序。
List<SeatGroup> groupSeats(List<TableInfo> tables) {
  final order = <int>[];
  final first = <int, TableInfo>{};
  final bookings = <int, List<BookingSummary>>{};
  final unavailable = <int, bool>{};
  for (final t in tables) {
    if (!first.containsKey(t.id)) {
      order.add(t.id);
      first[t.id] = t;
      bookings[t.id] = [];
      unavailable[t.id] = false;
    }
    if (t.booking != null) bookings[t.id]!.add(t.booking!);
    if (t.status != 'available') unavailable[t.id] = true;
  }
  return [
    for (final id in order)
      SeatGroup(
        table: first[id]!,
        bookings: bookings[id]!,
        unavailable: unavailable[id]!,
      ),
  ];
}

/// 桌子的分類。
///
/// 店員與管理員看得到所有訂位，所以有訂位一律是「已訂」；
/// 玩家只會拿到自己的訂位資料，有訂位資料就是「你的訂位」。
///
/// 店員看板傳入 [now] 時，桌上有超時的訂位就是「已超時」。
SeatTone seatTone(SeatGroup seat, {required bool staffView, DateTime? now}) {
  if (!staffView && seat.bookings.isNotEmpty) return SeatTone.mine;
  if (staffView &&
      now != null &&
      seat.bookings.any(
        (b) => overtimeMinutes(b.status, b.endAt, now) != null,
      )) {
    return SeatTone.overtime;
  }
  if (seat.unavailable || seat.bookings.isNotEmpty) return SeatTone.occupied;
  return SeatTone.available;
}

/// 樓層名稱：`1` → `1F`、`-1` → `B1`。
String floorLabel(int floor) => floor < 0 ? 'B${-floor}' : '${floor}F';

({Color background, Color border, Color text}) _colorsFor(SeatTone tone) =>
    switch (tone) {
      // 空桌：白底綠框，最醒目的是「可以坐」
      SeatTone.available => (
        background: AppColors.surface,
        border: AppColors.sage,
        text: AppColors.sage,
      ),
      // 已訂：灰色實心，退到背景
      SeatTone.occupied => (
        background: AppColors.border,
        border: AppColors.border,
        text: AppColors.inkMuted,
      ),
      // 你的訂位：主色實心
      SeatTone.mine => (
        background: AppColors.primary,
        border: AppColors.primary,
        text: AppColors.surface,
      ),
      // 已超時：錯誤色實心，店員一眼看得到
      SeatTone.overtime => (
        background: AppColors.error,
        border: AppColors.error,
        text: AppColors.surface,
      ),
    };

String _toneLabel(SeatTone tone) => switch (tone) {
  SeatTone.available => '空桌',
  SeatTone.occupied => '已訂',
  SeatTone.mine => '你的訂位',
  SeatTone.overtime => '已超時',
};

/// 依可用寬度放大座位圖的上限：桌子很少時不會被放得太誇張。
const _maxFitScale = 2.0;

/// 座位圖：樓層切換、圖例，以及依寬度等比例縮放、置中的桌子配置。
/// 點桌子會從下方滑出詳情；可以再用手勢放大、拖曳。
///
/// [staffView] 為 true 時是店員看板（所有訂位都是「已訂」，點桌子看訂位內容）；
/// false 時是玩家（自己的桌另外標示，別人的訂位不顯示內容）。
class SeatingPlanView extends StatefulWidget {
  const SeatingPlanView({
    required this.plans,
    required this.staffView,
    this.now,
    super.key,
  });

  final List<SeatingPlan> plans;
  final bool staffView;

  /// 用來判斷超時的「現在」（UTC）；只有店員看板會用到，null 時不標示超時。
  final DateTime? now;

  @override
  State<SeatingPlanView> createState() => _SeatingPlanViewState();
}

class _SeatingPlanViewState extends State<SeatingPlanView> {
  int? _floor;

  @override
  Widget build(BuildContext context) {
    // 樓層由高到低（2F、1F、B1）；沒選過時預設 1F，沒有 1F 就用最高的樓層
    final plans = [...widget.plans]..sort((a, b) => b.floor.compareTo(a.floor));
    final plan = plans.firstWhere(
      (p) => p.floor == (_floor ?? 1),
      orElse: () => plans.first,
    );
    final seats = groupSeats(plan.tables);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: AppSpacing.medium,
          runSpacing: AppSpacing.small,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            if (plans.length > 1)
              SegmentedButton<int>(
                showSelectedIcon: false,
                segments: [
                  for (final p in plans)
                    ButtonSegment(
                      value: p.floor,
                      label: Text(
                        floorLabel(p.floor),
                        key: Key('seating-floor-${floorLabel(p.floor)}'),
                      ),
                    ),
                ],
                selected: {plan.floor},
                onSelectionChanged: (v) => setState(() => _floor = v.first),
              ),
            _Legend(staffView: widget.staffView),
          ],
        ),
        const SizedBox(height: AppSpacing.medium),
        DecoratedBox(
          // 外框：放在面板裡時底色相近，靠框線看出座位圖的範圍
          position: DecorationPosition.foreground,
          decoration: BoxDecoration(
            border: Border.all(color: AppColors.border),
            borderRadius: BorderRadius.circular(AppRadius.button),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.button),
            child: ColoredBox(
              color: AppColors.backgroundAlt,
              child: LayoutBuilder(
                builder: (context, constraints) =>
                    _canvas(context, seats, plan.floor, constraints.maxWidth),
              ),
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.xSmall),
        Text(
          '點桌子看詳情，雙指可以放大',
          style: Theme.of(
            context,
          ).textTheme.bodySmall!.copyWith(color: AppColors.inkMuted),
        ),
      ],
    );
  }

  /// 依可用寬度與最大高度算出比例，讓整層桌子剛好放進畫面並置中。
  Widget _canvas(
    BuildContext context,
    List<SeatGroup> seats,
    int floor,
    double availableWidth,
  ) {
    const pad = AppSpacing.medium;
    var width = 1.0;
    var height = 1.0;
    for (final s in seats) {
      final t = s.table;
      if (t.x + t.width > width) width = (t.x + t.width).toDouble();
      if (t.y + t.height > height) height = (t.y + t.height).toDouble();
    }
    final byWidth = (availableWidth - pad * 2) / width;
    final byHeight = (AppSizes.seatingPlanHeight - pad * 2) / height;
    final scale = [
      byWidth,
      byHeight,
      _maxFitScale,
    ].reduce((a, b) => a < b ? a : b);
    final left = (availableWidth - width * scale) / 2;
    const gap = AppSizes.seatGap;

    return SizedBox(
      width: availableWidth,
      height: height * scale + pad * 2,
      child: InteractiveViewer(
        key: ValueKey(floor),
        maxScale: 3,
        child: Stack(
          children: [
            for (final s in seats)
              Positioned(
                left: left + (s.table.x + gap) * scale,
                top: pad + (s.table.y + gap) * scale,
                width: (s.table.width - gap * 2) * scale,
                height: (s.table.height - gap * 2) * scale,
                child: SeatTable(
                  key: Key('seat-table-${s.table.id}'),
                  seat: s,
                  tone: seatTone(
                    s,
                    staffView: widget.staffView,
                    now: widget.now,
                  ),
                  onTap: () => _showDetail(context, s),
                ),
              ),
          ],
        ),
      ),
    );
  }

  void _showDetail(BuildContext context, SeatGroup seat) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SeatDetail(
        key: const Key('seat-detail'),
        seat: seat,
        tone: seatTone(seat, staffView: widget.staffView, now: widget.now),
      ),
    );
  }
}

/// 座位圖上的一張桌子：桌號與人數上限，字級固定，桌子太小時才縮小。
class SeatTable extends StatelessWidget {
  const SeatTable({
    required this.seat,
    required this.tone,
    required this.onTap,
    super.key,
  });

  final SeatGroup seat;
  final SeatTone tone;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = seat.table;
    final colors = _colorsFor(tone);
    final text = Theme.of(context).textTheme;
    final shape = RoundedRectangleBorder(
      side: BorderSide(color: colors.border, width: AppSizes.seatTableBorder),
      borderRadius: BorderRadius.circular(AppRadius.seatTable),
    );
    return Semantics(
      button: true,
      label: '${t.tableCode} 桌，${_toneLabel(tone)}',
      child: Material(
        color: colors.background,
        shape: shape,
        child: InkWell(
          onTap: onTap,
          customBorder: shape,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.xSmall),
            child: Center(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      t.tableCode,
                      style: text.titleMedium!.copyWith(
                        color: colors.text,
                        fontWeight: FontWeight.w700,
                        height: 1.1,
                      ),
                    ),
                    Text(
                      '${t.maxCapacity} 人',
                      style: text.labelSmall!.copyWith(
                        color: colors.text,
                        height: 1.1,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend({required this.staffView});

  /// 店員看板有「已超時」，玩家有「你的訂位」。
  final bool staffView;

  @override
  Widget build(BuildContext context) {
    final tones = [
      SeatTone.available,
      SeatTone.occupied,
      staffView ? SeatTone.overtime : SeatTone.mine,
    ];
    return Wrap(
      key: const Key('seating-legend'),
      spacing: AppSpacing.medium,
      runSpacing: AppSpacing.xSmall,
      children: [
        for (final tone in tones)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: AppSizes.legendSwatch,
                height: AppSizes.legendSwatch,
                decoration: BoxDecoration(
                  color: _colorsFor(tone).background,
                  border: Border.all(
                    color: _colorsFor(tone).border,
                    width: AppSizes.seatTableBorder,
                  ),
                  borderRadius: BorderRadius.circular(AppRadius.seatTable),
                ),
              ),
              const SizedBox(width: AppSpacing.xSmall),
              Text(
                _toneLabel(tone),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
      ],
    );
  }
}

/// 點桌子後滑出的詳情。
class SeatDetail extends StatelessWidget {
  const SeatDetail({required this.seat, required this.tone, super.key});

  final SeatGroup seat;
  final SeatTone tone;

  @override
  Widget build(BuildContext context) {
    final t = seat.table;
    final text = Theme.of(context).textTheme;
    final muted = text.bodyMedium!.copyWith(color: AppColors.inkMuted);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.large,
          0,
          AppSpacing.large,
          AppSpacing.large,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text('${t.tableCode} 桌', style: text.titleLarge),
                ),
                PillBadge(
                  label: '最多 ${t.maxCapacity} 人',
                  tone: PillTone.players,
                  icon: Icons.people_outline,
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.medium),
            if (tone == SeatTone.mine) ...[
              Text('你的訂位', style: text.titleSmall),
              const SizedBox(height: AppSpacing.small),
            ],
            if (seat.bookings.isNotEmpty)
              for (final b in seat.bookings) _BookingLine(b)
            else if (tone == SeatTone.occupied)
              Text('此時段已被預訂', style: muted)
            else
              Text('這段時間沒有訂位', style: muted),
          ],
        ),
      ),
    );
  }
}

class _BookingLine extends StatelessWidget {
  const _BookingLine(this.booking);

  final BookingSummary booking;

  @override
  Widget build(BuildContext context) {
    final b = booking;
    final text = Theme.of(context).textTheme;
    final (statusText, tone) = bookingStatusLabel(b.status);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.small),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  formatBookingRange(b.startAt, b.endAt),
                  style: text.titleSmall,
                ),
              ),
              PillBadge(label: statusText, tone: tone),
            ],
          ),
          Text(
            '訂位代碼 ${b.reservationCode}・${b.partySize} 人',
            style: text.bodyMedium!.copyWith(color: AppColors.inkMuted),
          ),
        ],
      ),
    );
  }
}
