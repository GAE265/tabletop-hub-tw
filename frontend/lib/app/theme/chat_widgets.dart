import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_spacing.dart';
import 'thick_widgets.dart';

// 對話畫面（桌遊推薦、規則問答）共用的元件：放在木紋上，都有厚度與陰影（Stitch 設計）。

/// 對話泡泡的外框：四邊細線、底部較粗（厚度），加上陰影；圓角可以每個角不同。
BoxDecoration chatBubbleDecoration({
  required Color color,
  required Color edge,
  required BorderRadius radius,
  double thickness = AppSizes.cardThickness,
  List<BoxShadow>? shadow,
}) => BoxDecoration(
  color: color,
  borderRadius: radius,
  border: Border(
    top: BorderSide(color: edge),
    left: BorderSide(color: edge),
    right: BorderSide(color: edge),
    bottom: BorderSide(color: edge, width: thickness),
  ),
  boxShadow: shadow ?? AppShadows.raised,
);

/// 使用者的訊息：靠右、焦糖橘泡泡，最寬到可用寬度的 80%。
class UserBubble extends StatelessWidget {
  const UserBubble({required this.text, super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerRight,
      child: FractionallySizedBox(
        widthFactor: 0.8,
        alignment: Alignment.centerRight,
        child: Align(
          alignment: Alignment.centerRight,
          child: DecoratedBox(
            decoration: chatBubbleDecoration(
              color: scheme.primary,
              edge: AppColors.primaryText,
              radius: const BorderRadius.only(
                topLeft: Radius.circular(AppRadius.card),
                topRight: Radius.circular(AppRadius.card),
                bottomLeft: Radius.circular(AppRadius.card),
                bottomRight: Radius.circular(AppSpacing.xSmall),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.medium,
                vertical: AppSpacing.small,
              ),
              child: Text(
                text,
                style: Theme.of(
                  context,
                ).textTheme.bodyLarge!.copyWith(color: scheme.onPrimary),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 助理那一側：上面是頭像與名字（例如「推薦助理」），下面是白色泡泡。
class AssistantMessage extends StatelessWidget {
  const AssistantMessage({
    required this.name,
    required this.child,
    this.bubbleKey,
    super.key,
  });

  final String name;
  final Widget child;

  /// 掛在白色泡泡外面的 Key。
  final Key? bubbleKey;

  @override
  Widget build(BuildContext context) {
    final small = BorderRadius.circular(AppRadius.pill);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            DecoratedBox(
              decoration: chatBubbleDecoration(
                color: AppColors.primaryTint,
                edge: AppColors.cardEdge,
                radius: small,
                thickness: AppSizes.smallThickness,
                shadow: AppShadows.soft,
              ),
              child: const SizedBox.square(
                dimension: AppSizes.avatar,
                child: Icon(Icons.auto_awesome, color: AppColors.primaryText),
              ),
            ),
            const SizedBox(width: AppSpacing.small),
            // 名字放在白底膠囊裡，不直接壓在木紋上
            DecoratedBox(
              decoration: chatBubbleDecoration(
                color: AppColors.surface,
                edge: AppColors.cardEdge,
                radius: small,
                thickness: AppSizes.smallThickness,
                shadow: AppShadows.soft,
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.small + AppSpacing.xSmall,
                  vertical: AppSpacing.xSmall,
                ),
                child: Text(
                  name,
                  style: Theme.of(context).textTheme.labelLarge,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.small),
        KeyedSubtree(
          key: bubbleKey,
          child: DecoratedBox(
            decoration: chatBubbleDecoration(
              color: AppColors.surface,
              edge: AppColors.cardEdge,
              radius: const BorderRadius.only(
                topLeft: Radius.circular(AppSpacing.xSmall),
                topRight: Radius.circular(AppRadius.card),
                bottomLeft: Radius.circular(AppRadius.card),
                bottomRight: Radius.circular(AppRadius.card),
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.medium,
                vertical: AppSpacing.small + AppSpacing.xSmall,
              ),
              child: child,
            ),
          ),
        ),
      ],
    );
  }
}

/// 建議問題的小膠囊：白底、薄厚邊、淡陰影，按住時往下沉。
class SuggestionChip extends StatefulWidget {
  const SuggestionChip({required this.label, required this.onTap, super.key});

  final String label;
  final VoidCallback onTap;

  @override
  State<SuggestionChip> createState() => _SuggestionChipState();
}

class _SuggestionChipState extends State<SuggestionChip> {
  var _pressed = false;

  @override
  Widget build(BuildContext context) {
    return PressFrame(
      pressed: _pressed,
      color: AppColors.surface,
      edge: AppColors.cardEdge,
      radius: AppRadius.pill,
      thickness: AppSizes.smallThickness,
      shadow: AppShadows.soft,
      child: Material(
        type: MaterialType.transparency,
        shape: const StadiumBorder(),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: widget.onTap,
          onHighlightChanged: (pressed) => setState(() => _pressed = pressed),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.medium,
              vertical: AppSpacing.small,
            ),
            child: Text(
              widget.label,
              style: Theme.of(
                context,
              ).textTheme.labelLarge!.copyWith(color: AppColors.ink),
            ),
          ),
        ),
      ),
    );
  }
}

/// 助理正在回覆：白底小膠囊裡一個轉圈和一句話（例如「正在找桌遊…」）。
class ThinkingPill extends StatelessWidget {
  const ThinkingPill({required this.text, super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      // 放在白底膠囊裡，文字才不會直接壓在木紋上
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppColors.surfaceGlass,
          borderRadius: BorderRadius.circular(AppRadius.pill),
          border: Border.all(color: AppColors.border),
          boxShadow: AppShadows.soft,
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.medium,
            vertical: AppSpacing.small,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox.square(
                dimension: AppSpacing.medium,
                child: CircularProgressIndicator(),
              ),
              const SizedBox(width: AppSpacing.small),
              Flexible(child: Text(text)),
            ],
          ),
        ),
      ),
    );
  }
}

/// 捲動區上緣淡出：內容捲到頁首下面時慢慢消失在木紋裡，不會被切成一條直線。
/// 下緣不用淡出：內容會從浮在上面的輸入區後面滑過去。
class TopEdgeFade extends StatelessWidget {
  const TopEdgeFade({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      blendMode: BlendMode.dstIn,
      shaderCallback: (bounds) {
        final edge = bounds.height == 0
            ? 0.0
            : (AppSizes.scrollFade / bounds.height).clamp(0.0, 1.0);
        return LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: const [Colors.transparent, Colors.black, Colors.black],
          stops: [0, edge, 1],
        ).createShader(bounds);
      },
      child: child,
    );
  }
}
