import 'package:flutter/material.dart';

import '../../../../app/theme/app_spacing.dart';

/// 提示條：一般提示用琥珀色淡底，錯誤用錯誤色淡底。
class NoticeBanner extends StatelessWidget {
  const NoticeBanner({required this.text, this.isError = false, super.key});

  final String text;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final background = isError
        ? scheme.errorContainer
        : scheme.tertiaryContainer;
    final foreground = isError
        ? scheme.onErrorContainer
        : scheme.onTertiaryContainer;
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
              isError ? Icons.error_outline : Icons.info_outline,
              color: foreground,
            ),
            const SizedBox(width: AppSpacing.small),
            Expanded(
              child: Text(
                text,
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium!.copyWith(color: foreground),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
