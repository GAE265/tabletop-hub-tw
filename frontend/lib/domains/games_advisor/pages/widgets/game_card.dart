import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/thick_widgets.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../data/advisor_message.dart';
import '../../state/game_card_text.dart';

/// 推薦卡片（Stitch 版面）：有厚度的卡片，名稱、資訊行、店家沒有這款時的提示、
/// 「推薦理由」框，以及預設摺疊的心得片段。
/// 卡片上的文字一律用 `state/game_card_text.dart` 的函式產生（交接說明第 2 節）。
class GameCard extends StatelessWidget {
  const GameCard(this.recommendation, {super.key});

  final AdvisorRecommendation recommendation;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final text = theme.textTheme;
    final excerpts = recommendation.excerpts;
    const inset = AppSpacing.medium + AppSpacing.xSmall;
    return ThickCard(
      key: const Key('advisor-game-card'),
      child: Padding(
        padding: const EdgeInsets.all(inset),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Container(
                  width: AppSpacing.xSmall,
                  height: AppSpacing.large,
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(AppRadius.pill),
                  ),
                ),
                const SizedBox(width: AppSpacing.small),
                Expanded(
                  child: Text(
                    recommendation.game.name,
                    style: text.headlineSmall!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            Text(
              gameMetaText(recommendation.game),
              style: text.bodyMedium!.copyWith(
                color: AppColors.inkMuted,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (stockHintText(recommendation) case final hint?) ...[
              const SizedBox(height: AppSpacing.small),
              Align(
                alignment: Alignment.centerLeft,
                child: PillBadge(
                  key: const Key('advisor-stock-hint'),
                  label: hint,
                  tone: PillTone.accent,
                  icon: Icons.storefront_outlined,
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.medium),
            // 推薦理由放在淡色框裡
            DecoratedBox(
              decoration: BoxDecoration(
                color: AppColors.backgroundAlt,
                borderRadius: BorderRadius.circular(AppRadius.button),
                border: Border.all(color: AppColors.border),
              ),
              child: Padding(
                padding: const EdgeInsets.all(
                  AppSpacing.small + AppSpacing.xSmall,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '推薦理由',
                      style: text.labelLarge!.copyWith(
                        color: AppColors.primaryText,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xSmall),
                    Text(recommendation.reason, style: text.bodyMedium),
                  ],
                ),
              ),
            ),
            if (excerpts.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
              ClipRRect(
                borderRadius: BorderRadius.circular(AppRadius.button),
                child: Theme(
                  // 展開時不要上下多出分隔線
                  data: theme.copyWith(dividerColor: Colors.transparent),
                  child: ExpansionTile(
                    backgroundColor: AppColors.neutralTint,
                    collapsedBackgroundColor: AppColors.neutralTint,
                    leading: const Icon(Icons.chat_bubble_outline),
                    tilePadding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.medium,
                    ),
                    childrenPadding: const EdgeInsets.fromLTRB(
                      AppSpacing.medium,
                      0,
                      AppSpacing.medium,
                      AppSpacing.medium,
                    ),
                    title: Text(
                      '心得片段（${excerpts.length}）',
                      style: text.titleSmall,
                    ),
                    children: [
                      for (final excerpt in excerpts)
                        Padding(
                          padding: const EdgeInsets.only(top: AppSpacing.small),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                child: Text(
                                  excerpt.text,
                                  style: text.bodyMedium,
                                ),
                              ),
                              if (excerptLanguageLabel(excerpt)
                                  case final label?)
                                Padding(
                                  padding: const EdgeInsets.only(
                                    left: AppSpacing.small,
                                  ),
                                  child: PillBadge(label: label),
                                ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
