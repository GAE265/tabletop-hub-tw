import 'package:flutter/material.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../core/widgets/pill_badge.dart';
import '../../data/advisor_message.dart';
import '../../state/game_card_text.dart';

/// 推薦卡片：名稱、資訊行、推薦理由，以及預設摺疊的心得片段。
/// 卡片上的文字一律用 `state/game_card_text.dart` 的函式產生（交接說明第 2 節）。
class GameCard extends StatelessWidget {
  const GameCard(this.recommendation, {super.key});

  final AdvisorRecommendation recommendation;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final text = theme.textTheme;
    final excerpts = recommendation.excerpts;
    return Card(
      key: const Key('advisor-game-card'),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.medium),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(recommendation.game.name, style: text.titleLarge),
                const SizedBox(height: AppSpacing.xSmall),
                Text(gameMetaText(recommendation.game), style: text.bodySmall),
                const SizedBox(height: AppSpacing.small),
                Text(recommendation.reason, style: text.bodyMedium),
              ],
            ),
          ),
          if (excerpts.isNotEmpty)
            Theme(
              // 展開時不要上下多出分隔線
              data: theme.copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                backgroundColor: theme.colorScheme.surfaceContainer,
                collapsedBackgroundColor: theme.colorScheme.surfaceContainer,
                tilePadding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.medium,
                ),
                childrenPadding: const EdgeInsets.fromLTRB(
                  AppSpacing.medium,
                  0,
                  AppSpacing.medium,
                  AppSpacing.medium,
                ),
                title: Text('心得片段（${excerpts.length}）', style: text.titleSmall),
                children: [
                  for (final excerpt in excerpts)
                    Padding(
                      padding: const EdgeInsets.only(top: AppSpacing.small),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(excerpt.text, style: text.bodyMedium),
                          ),
                          if (excerptLanguageLabel(excerpt) case final label?)
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
        ],
      ),
    );
  }
}
