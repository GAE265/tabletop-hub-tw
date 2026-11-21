import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../data/booking.dart';

/// 店家所在地（台灣）與 UTC 的時差；訂位時間一律以台灣時間顯示與送出。
const taipeiOffset = Duration(hours: 8);

const _weekdays = ['一', '二', '三', '四', '五', '六', '日'];

String _two(int n) => n.toString().padLeft(2, '0');

/// 台灣時間的「現在」，只取年月日時分（不帶時區）。
DateTime taipeiNow() => DateTime.now().toUtc().add(taipeiOffset);

/// `2026-11-25`
String isoDate(DateTime d) => '${d.year}-${_two(d.month)}-${_two(d.day)}';

/// `11/25（三）`
String shortDate(DateTime d) =>
    '${d.month}/${d.day}（${_weekdays[d.weekday - 1]}）';

DateTime _toTaipei(String iso) => DateTime.parse(iso).toUtc().add(taipeiOffset);

/// 後端回傳的時間區間，以台灣時間顯示：`11/25（三）14:00–16:00`。
String formatBookingRange(String startAt, String endAt) {
  final start = _toTaipei(startAt);
  final end = _toTaipei(endAt);
  String hm(DateTime d) => '${_two(d.hour)}:${_two(d.minute)}';
  return '${shortDate(start)}${hm(start)}–${hm(end)}';
}

/// state 的錯誤訊息是「錯誤代碼：說明」，畫面只顯示說明。
String bookingErrorText(String message) =>
    message.replaceFirst(RegExp(r'^[A-Z][A-Z0-9_]*：'), '');

/// 訂位狀態的中文與標籤顏色。
(String, PillTone) bookingStatusLabel(String status) => switch (status) {
  'confirmed' => ('已確認', PillTone.players),
  'seated' => ('已入座', PillTone.duration),
  'completed' => ('已完成', PillTone.neutral),
  'cancelled' => ('已取消', PillTone.neutral),
  'no_show' => ('未出席', PillTone.accent),
  _ => (status, PillTone.neutral),
};

/// 訂位頁上方的分頁：訂位／我的訂位／店家看板（店家人員與管理員才有）。
class BookingTabs extends StatelessWidget {
  const BookingTabs({
    required this.current,
    required this.showBoard,
    super.key,
  });

  /// `new`、`mine`、`board`
  final String current;
  final bool showBoard;

  static const _paths = {
    'new': '/booking',
    'mine': '/booking/mine',
    'board': '/booking/board',
  };

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: SegmentedButton<String>(
        showSelectedIcon: false,
        segments: [
          const ButtonSegment(
            value: 'new',
            icon: Icon(Icons.event_available_outlined),
            label: Text('訂位', key: Key('booking-tab-new')),
          ),
          const ButtonSegment(
            value: 'mine',
            icon: Icon(Icons.receipt_long_outlined),
            label: Text('我的訂位', key: Key('booking-tab-mine')),
          ),
          if (showBoard)
            const ButtonSegment(
              value: 'board',
              icon: Icon(Icons.storefront_outlined),
              label: Text('店家看板', key: Key('booking-tab-board')),
            ),
        ],
        selected: {current},
        onSelectionChanged: (s) => context.go(_paths[s.first]!),
      ),
    );
  }
}

/// 錯誤提示列。
class BookingErrorBanner extends StatelessWidget {
  const BookingErrorBanner({
    required this.message,
    this.onRetry,
    this.retryKey,
    super.key,
  });

  final String message;
  final VoidCallback? onRetry;
  final Key? retryKey;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: scheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Row(
          children: [
            Icon(Icons.error_outline, color: scheme.onErrorContainer),
            const SizedBox(width: AppSpacing.small),
            Expanded(
              child: Text(
                bookingErrorText(message),
                style: TextStyle(color: scheme.onErrorContainer),
              ),
            ),
            if (onRetry != null)
              TextButton(
                key: retryKey,
                onPressed: onRetry,
                child: const Text('重試'),
              ),
          ],
        ),
      ),
    );
  }
}

/// 一筆訂位的卡片；按鈕由呼叫的頁面依角色決定。
class BookingCard extends StatelessWidget {
  const BookingCard({
    required this.booking,
    required this.shopName,
    this.actions = const [],
    this.overtimeMinutes,
    super.key,
  });

  final Booking booking;
  final String? shopName;
  final List<Widget> actions;

  /// 已入座且超過結束時間的分鐘數；有值時顯示「已超時 N 分鐘」（店家看板用）。
  final int? overtimeMinutes;

  @override
  Widget build(BuildContext context) {
    final b = booking;
    final text = Theme.of(context).textTheme;
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    final (statusText, tone) = bookingStatusLabel(b.status);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    formatBookingRange(b.startAt, b.endAt),
                    style: text.titleMedium,
                  ),
                ),
                PillBadge(label: statusText, tone: tone),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            Wrap(
              spacing: AppSpacing.small,
              runSpacing: AppSpacing.xSmall,
              children: [
                if (shopName != null)
                  PillBadge(label: shopName!, icon: Icons.storefront_outlined),
                PillBadge(
                  label: '${b.partySize} 人',
                  tone: PillTone.players,
                  icon: Icons.people_outline,
                ),
                if (b.tableCodes.isNotEmpty)
                  PillBadge(
                    label: '桌位 ${b.tableCodes.join('、')}',
                    icon: Icons.table_restaurant_outlined,
                  ),
                if (overtimeMinutes != null)
                  PillBadge(
                    key: Key('board-overtime-${b.id}'),
                    label: '已超時 $overtimeMinutes 分鐘',
                    tone: PillTone.accent,
                    icon: Icons.timer_off_outlined,
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              '訂位代碼 ${b.reservationCode}　預估 ${b.estimatedFee.venueFee} 元'
              '${b.finalFee == null ? '' : '　結算 ${b.finalFee} 元'}',
              style: text.bodyMedium!.copyWith(color: muted),
            ),
            if (b.notice != null) ...[
              const SizedBox(height: AppSpacing.small),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    Icons.info_outline,
                    size: text.bodyMedium!.fontSize,
                    color: muted,
                  ),
                  const SizedBox(width: AppSpacing.xSmall),
                  Expanded(child: Text(b.notice!, style: text.bodyMedium)),
                ],
              ),
            ],
            if (actions.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.small),
              Wrap(
                alignment: WrapAlignment.end,
                spacing: AppSpacing.small,
                children: actions,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 確認視窗；按「確定」回傳 true。[content] 是標題下方的說明文字。
Future<bool> confirmBookingAction(
  BuildContext context, {
  required String title,
  required String confirmLabel,
  String? content,
}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: content == null ? null : Text(content),
      actions: [
        TextButton(
          key: const Key('booking-cancel-dismiss'),
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('先不要'),
        ),
        FilledButton(
          key: const Key('booking-cancel-confirm'),
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
  return ok ?? false;
}

/// 頁面共用的外框：置中、限制最大寬度、上方分頁。
class BookingScaffold extends StatelessWidget {
  const BookingScaffold({
    required this.pageKey,
    required this.title,
    required this.current,
    required this.showBoard,
    required this.children,
    this.maxWidth,
    super.key,
  });

  final Key pageKey;
  final String title;
  final String current;
  final bool showBoard;
  final List<Widget> children;
  final double? maxWidth;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: pageKey,
      appBar: AppBar(title: Text(title)),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth ?? double.infinity),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.medium),
            children: [
              BookingTabs(current: current, showBoard: showBoard),
              const SizedBox(height: AppSpacing.medium),
              ...children,
            ],
          ),
        ),
      ),
    );
  }
}
