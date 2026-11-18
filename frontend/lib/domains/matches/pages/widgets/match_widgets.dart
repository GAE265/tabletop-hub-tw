import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../core/api/api_exception.dart';
import '../../data/game_match.dart';
import '../../state/match_labels.dart';

const _weekdays = ['一', '二', '三', '四', '五', '六', '日'];

/// 日曆日期（沒有時區），例如「2026/11/20（五）」。
String formatPlayedOn(DateTime date) =>
    '${date.year}/${date.month}/${date.day}（${_weekdays[date.weekday - 1]}）';

/// 地點：自家，或「桌遊店・<店名>」。
String matchLocationText(GameMatch match) => match.locationType == 'shop'
    ? '${locationLabel('shop')}${match.shop == null ? '' : '・${match.shop!.name}'}'
    : locationLabel(match.locationType);

/// 錯誤只顯示中文說明，不顯示錯誤代碼；座位被回合擋下時附上相關回合、結果少座位時附上缺的座位。
String matchErrorText(Object error) {
  if (error is! ApiException) return '無法連線，請稍後再試';
  final turns = error.details['turn_numbers'];
  final missing = error.details['missing_seat_numbers'];
  return [
    error.message,
    if (turns is List && turns.isNotEmpty) '（相關回合：${turns.join('、')}）',
    if (missing is List && missing.isNotEmpty) '（缺座位：${missing.join('、')}）',
  ].join();
}

/// 回合清單一列的標題，例如「第 1 回合・首家座位 1」；沒有首家時只有「第 1 回合」。
String turnTitle(MatchTurn turn) => [
  '第 ${turn.turnNumber} 回合',
  if (turn.seatNumber case final seat?) '首家座位 $seat',
].join('・');

/// 回合清單一列的內容（白薔薇）：出牌座位、四種數量、有沒有白薔薇。
String turnDetail(Map<String, dynamic> data) {
  final played = (data['played_seat_numbers'] as List?)?.join('、') ?? '-';
  int count(String key) => (data[key] as num?)?.toInt() ?? 0;
  return '出牌座位 $played・雙刃 ${count('double_blade_count')}・'
      '暗刃 ${count('dark_blade_count')}・巨刃 ${count('giant_blade_count')}・'
      '信者 ${count('faithful_count')}・'
      '白薔薇：${data['has_white_rose'] == true ? '有' : '沒有'}';
}

/// 有標題的區塊卡片。
class MatchSection extends StatelessWidget {
  const MatchSection({
    required this.title,
    required this.children,
    this.trailing,
    super.key,
  });

  final String title;
  final List<Widget> children;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                ?trailing,
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            ...children,
          ],
        ),
      ),
    );
  }
}

/// 操作結果的提示：成功（綠）或錯誤（紅）。
class MatchBanner extends StatelessWidget {
  const MatchBanner({required this.text, this.isError = false, super.key});

  final String text;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final background = isError ? scheme.errorContainer : AppColors.sageTint;
    final foreground = isError ? scheme.onErrorContainer : AppColors.sage;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(AppRadius.button),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Row(
          children: [
            Icon(
              isError ? Icons.error_outline : Icons.check_circle_outline,
              color: foreground,
            ),
            const SizedBox(width: AppSpacing.small),
            Expanded(
              child: Text(text, style: TextStyle(color: foreground)),
            ),
          ],
        ),
      ),
    );
  }
}

/// 欄位旁的錯誤訊息（沒有錯誤時不佔空間）。
class FieldError extends StatelessWidget {
  const FieldError(this.message, {super.key});

  final String? message;

  @override
  Widget build(BuildContext context) {
    if (message == null) return const SizedBox.shrink();
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.xSmall),
      child: Text(
        message!,
        style: theme.textTheme.bodySmall!.copyWith(
          color: theme.colorScheme.error,
        ),
      ),
    );
  }
}

/// 「已經有人記錄了，要更新嗎？」：既有紀錄的簡述與「更新」「取消」。
/// [keyPrefix] 例如 `turn-overwrite`，按鈕的 Key 是 `<prefix>-confirm`、`<prefix>-cancel`。
class OverwritePrompt extends StatelessWidget {
  const OverwritePrompt({
    required this.keyPrefix,
    required this.text,
    required this.existing,
    required this.onConfirm,
    required this.onCancel,
    this.busy = false,
    super.key,
  });

  final String keyPrefix;
  final String text;
  final String existing;
  final VoidCallback onConfirm;
  final VoidCallback onCancel;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return DecoratedBox(
      key: Key(keyPrefix),
      decoration: BoxDecoration(
        color: AppColors.amberTint,
        borderRadius: BorderRadius.circular(AppRadius.button),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              text,
              style: textTheme.titleSmall!.copyWith(color: AppColors.amberText),
            ),
            const SizedBox(height: AppSpacing.xSmall),
            Text('既有紀錄：$existing', style: textTheme.bodyMedium),
            const SizedBox(height: AppSpacing.small),
            Wrap(
              spacing: AppSpacing.small,
              children: [
                FilledButton(
                  key: Key('$keyPrefix-confirm'),
                  onPressed: busy ? null : onConfirm,
                  child: const Text('更新'),
                ),
                TextButton(
                  key: Key('$keyPrefix-cancel'),
                  onPressed: busy ? null : onCancel,
                  child: const Text('取消'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// 載入失敗：錯誤說明與「重試」。
class MatchLoadError extends StatelessWidget {
  const MatchLoadError({
    required this.error,
    required this.onRetry,
    required this.retryKey,
    this.prefix = '載入失敗',
    super.key,
  });

  final Object error;
  final VoidCallback onRetry;
  final Key retryKey;
  final String prefix;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: AppSpacing.small,
      children: [
        Text(
          '$prefix：${matchErrorText(error)}',
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
        TextButton.icon(
          key: retryKey,
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('重試'),
        ),
      ],
    );
  }
}
