import 'package:flutter/material.dart';

import '../../core/notifications/notification_day.dart';
import '../../core/widgets/pill_badge.dart';
import 'app_colors.dart';
import 'app_spacing.dart';
import 'thick_widgets.dart';

// 通知列表（揪團、訂位）共用的元件（Stitch 版面）。

/// 一則通知：有厚度的卡片，點整張前往；左上是種類標籤，未讀時有橘色短線與圓點、標題加粗。
class NotificationCard extends StatelessWidget {
  const NotificationCard({
    required this.unread,
    required this.unreadDotKey,
    required this.tag,
    required this.title,
    required this.chips,
    required this.footnote,
    required this.onTap,
    super.key,
  });

  final bool unread;

  /// 未讀圓點的 Key（測試用它判斷未讀）。
  final Key unreadDotKey;

  /// 種類標籤：（文字, 色調, 圖示）。
  final (String, PillTone, IconData) tag;
  final String title;

  /// 時間、地點等小標籤：（圖示, 文字）。
  final List<(IconData, String)> chips;

  /// 最下面的小字，例如「通知時間 11/14 11:05」。
  final String footnote;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final (tagLabel, tagTone, tagIcon) = tag;
    return ThickCard(
      onTap: onTap,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 未讀：左邊一條焦糖橘短線
            Container(
              width: AppSpacing.xSmall,
              color: unread ? AppColors.primary : Colors.transparent,
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.medium),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        PillBadge(
                          label: tagLabel,
                          tone: tagTone,
                          icon: tagIcon,
                        ),
                        const Spacer(),
                        if (unread)
                          Container(
                            key: unreadDotKey,
                            width: AppSizes.unreadDot,
                            height: AppSizes.unreadDot,
                            decoration: const BoxDecoration(
                              color: AppColors.primary,
                              shape: BoxShape.circle,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.small),
                    Text(
                      title,
                      style: text.titleMedium!.copyWith(
                        fontWeight: unread ? FontWeight.w700 : FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.small),
                    Wrap(
                      spacing: AppSpacing.small,
                      runSpacing: AppSpacing.xSmall,
                      children: [
                        for (final (icon, label) in chips)
                          PillBadge(label: label, icon: icon),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.small),
                    Text(footnote, style: text.bodySmall),
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

/// 日期分段的標題：左邊深色膠囊（今天／昨天／更早之前），中間細線，右邊「N 則」。
/// 放在白底條上，文字不直接壓在木紋上。
class NotificationDayHeader extends StatelessWidget {
  const NotificationDayHeader({
    required this.day,
    required this.count,
    super.key,
  });

  final NotificationDay day;
  final int count;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Padding(
      key: Key('notification-day-${day.label}'),
      padding: const EdgeInsets.only(bottom: AppSpacing.small),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppColors.surfaceGlass,
          borderRadius: BorderRadius.circular(AppRadius.pill),
          boxShadow: AppShadows.soft,
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xSmall),
          child: Row(
            children: [
              DecoratedBox(
                decoration: BoxDecoration(
                  color: AppColors.ink,
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.small + AppSpacing.xSmall,
                    vertical: AppSpacing.xSmall,
                  ),
                  child: Text(
                    day.label,
                    style: text.labelLarge!.copyWith(color: AppColors.surface),
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.small),
              const Expanded(child: Divider()),
              const SizedBox(width: AppSpacing.small),
              Text('$count 則', style: text.bodySmall),
              const SizedBox(width: AppSpacing.small),
            ],
          ),
        ),
      ),
    );
  }
}

/// 依日期分段排好的通知列表內容：在每一段的第一則前面放 [NotificationDayHeader]。
///
/// [dayOf] 算出每一則屬於哪一段；[itemBuilder] 建出那一則的卡片。
List<Widget> groupNotificationsByDay<T>({
  required List<T> items,
  required NotificationDay Function(T item) dayOf,
  required Widget Function(T item) itemBuilder,
}) {
  final days = [for (final item in items) dayOf(item)];
  final counts = <NotificationDay, int>{};
  for (final day in days) {
    counts[day] = (counts[day] ?? 0) + 1;
  }
  return [
    for (final (i, item) in items.indexed) ...[
      if (i == 0 || days[i] != days[i - 1])
        NotificationDayHeader(day: days[i], count: counts[days[i]]!),
      Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.medium),
        child: itemBuilder(item),
      ),
    ],
  ];
}
