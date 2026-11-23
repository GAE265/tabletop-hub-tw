import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_spacing.dart';

// 放在木紋上的元件（Stitch 設計）：有厚度的卡片與按鈕、白底條、區塊標題。
// 木紋顏色較深，文字一律放在這些元件裡，不直接壓在木紋上。

/// 有厚度的外框：四邊細線、底部較粗（像木牌的側邊），加上陰影。
BoxDecoration thickDecoration({
  required Color color,
  required Color edge,
  required double radius,
  double thickness = AppSizes.cardThickness,
  List<BoxShadow>? shadow,
}) => BoxDecoration(
  color: color,
  borderRadius: BorderRadius.circular(radius),
  border: Border(
    top: BorderSide(color: edge),
    left: BorderSide(color: edge),
    right: BorderSide(color: edge),
    bottom: BorderSide(color: edge, width: thickness),
  ),
  boxShadow: shadow ?? AppShadows.raised,
);

/// 有厚度、按得下去的外框：[pressed] 時底邊變薄、內容往下沉、陰影變淺。
///
/// 少掉的厚度剛好等於往下沉的距離，整體高度不變，下面的內容不會跟著跳動。
class PressFrame extends StatelessWidget {
  const PressFrame({
    required this.pressed,
    required this.color,
    required this.edge,
    required this.radius,
    required this.child,
    super.key,
  });

  final bool pressed;
  final Color color;
  final Color edge;
  final double radius;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    const sink = AppSizes.cardThickness - AppSizes.pressedThickness;
    final thickness = pressed
        ? AppSizes.pressedThickness
        : AppSizes.cardThickness;
    return AnimatedContainer(
      duration: AppDurations.press,
      // AnimatedContainer 會依邊框粗細自動內縮，內容不會蓋到底邊；
      // 底邊少掉的厚度由上方的 margin 補回，整體高度不變
      margin: EdgeInsets.only(top: pressed ? sink : 0),
      decoration: thickDecoration(
        color: color,
        edge: edge,
        radius: radius,
        thickness: thickness,
        shadow: pressed ? AppShadows.card : AppShadows.raised,
      ),
      child: child,
    );
  }
}

/// 區塊標題：白底條、左邊小圓點，右邊可以放標籤（例如筆數）。
class SectionBar extends StatelessWidget {
  const SectionBar({required this.title, this.trailing, this.icon, super.key});

  final String title;
  final Widget? trailing;

  /// 取代左邊小圓點的圖示。
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return GlassBar(
      child: Row(
        children: [
          if (icon case final icon?)
            Icon(icon, color: AppColors.primaryText)
          else
            Container(
              width: AppSizes.sectionDot,
              height: AppSizes.sectionDot,
              decoration: const BoxDecoration(
                color: AppColors.primary,
                shape: BoxShape.circle,
              ),
            ),
          const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
          Expanded(
            child: Text(
              title,
              style: Theme.of(
                context,
              ).textTheme.headlineSmall!.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}

/// 放在木紋上的半透明白底條。
class GlassBar extends StatelessWidget {
  const GlassBar({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: thickDecoration(
        color: AppColors.surfaceGlass,
        edge: AppColors.cardEdge,
        radius: AppRadius.card,
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.medium,
          vertical: AppSpacing.small,
        ),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: AppSizes.minTouchTarget),
          child: Align(alignment: Alignment.centerLeft, child: child),
        ),
      ),
    );
  }
}

/// 有厚度的卡片：圓角、細邊框、底部較粗的邊（看起來有厚度）、陰影；
/// 有 [onTap] 時可以點，按住時往下沉。
class ThickCard extends StatefulWidget {
  const ThickCard({
    required this.child,
    this.onTap,
    this.color = AppColors.surface,
    this.radius = AppRadius.hero,
    super.key,
  });

  final Widget child;
  final VoidCallback? onTap;
  final Color color;
  final double radius;

  @override
  State<ThickCard> createState() => _ThickCardState();
}

class _ThickCardState extends State<ThickCard> {
  var _pressed = false;

  @override
  Widget build(BuildContext context) {
    final color = widget.color;
    return PressFrame(
      pressed: _pressed,
      color: color,
      edge: color == AppColors.ink ? AppColors.inkEdge : AppColors.cardEdge,
      radius: widget.radius,
      child: Material(
        type: MaterialType.transparency,
        borderRadius: BorderRadius.circular(widget.radius),
        clipBehavior: Clip.antiAlias,
        child: widget.onTap == null
            ? widget.child
            : InkWell(
                onTap: widget.onTap,
                onHighlightChanged: (pressed) =>
                    setState(() => _pressed = pressed),
                child: widget.child,
              ),
      ),
    );
  }
}

/// 有厚度的按鈕配色。
enum ThickStyle {
  /// 焦糖橘：主要操作。
  primary(AppColors.primary, AppColors.primaryText, AppColors.surface),

  /// 深炭色：和主要操作並列的另一個重點操作。
  dark(AppColors.ink, AppColors.inkEdge, AppColors.surface),

  /// 米白：次要操作。
  light(AppColors.background, AppColors.cardEdge, AppColors.ink),

  /// 白底紅字：危險操作（例如取消揪團），按下後一律先確認。
  danger(AppColors.surface, AppColors.error, AppColors.error);

  const ThickStyle(this.color, this.edge, this.foreground);

  final Color color;
  final Color edge;
  final Color foreground;
}

/// 有厚度的按鈕：底部較深的邊與陰影。按住時底邊變薄、往下沉，放開後彈回。
///
/// [onPressed] 為 null 時停用（灰底灰字）。沒有 [icon] 時是一般的 [FilledButton]。
class ThickButton extends StatefulWidget {
  const ThickButton({
    required this.style,
    required this.onPressed,
    required this.label,
    this.icon,
    this.buttonKey,
    this.expand = false,
    super.key,
  });

  /// 掛在按鈕本身的 Key（測試用它找按鈕）。
  final Key? buttonKey;
  final ThickStyle style;
  final VoidCallback? onPressed;
  final IconData? icon;
  final String label;

  /// 撐滿可用寬度（底部兩個大按鈕），否則依文字寬度。
  final bool expand;

  @override
  State<ThickButton> createState() => _ThickButtonState();
}

class _ThickButtonState extends State<ThickButton> {
  final _states = WidgetStatesController();
  var _pressed = false;

  @override
  void initState() {
    super.initState();
    _states.addListener(() {
      final pressed = _states.value.contains(WidgetState.pressed);
      if (pressed != _pressed) setState(() => _pressed = pressed);
    });
  }

  @override
  void dispose() {
    _states.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final style = widget.style;
    final edge = widget.onPressed == null ? AppColors.cardEdge : style.edge;
    const height = AppSizes.minTouchTarget + AppSpacing.small;
    final buttonStyle = FilledButton.styleFrom(
      backgroundColor: style.color,
      foregroundColor: style.foreground,
      disabledBackgroundColor: AppColors.neutralTint,
      disabledForegroundColor: AppColors.inkMuted,
      minimumSize: widget.expand
          ? const Size.fromHeight(height)
          : const Size(AppSizes.minTouchTarget, height),
    );
    return PressFrame(
      pressed: _pressed,
      color: edge,
      edge: edge,
      radius: AppRadius.button,
      child: switch (widget.icon) {
        final icon? => FilledButton.icon(
          key: widget.buttonKey,
          statesController: _states,
          style: buttonStyle,
          onPressed: widget.onPressed,
          icon: Icon(icon),
          label: Text(widget.label),
        ),
        null => FilledButton(
          key: widget.buttonKey,
          statesController: _states,
          style: buttonStyle,
          onPressed: widget.onPressed,
          child: Text(widget.label),
        ),
      },
    );
  }
}

/// 圖示＋粗體文字，例如日期、人數。
class IconText extends StatelessWidget {
  const IconText({required this.icon, required this.text, super.key});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: AppSizes.inlineIcon, color: AppColors.ink),
        const SizedBox(width: AppSpacing.small),
        // 文字太長時換行，不要超出卡片
        Flexible(
          child: Text(
            text,
            style: Theme.of(
              context,
            ).textTheme.titleSmall!.copyWith(fontWeight: FontWeight.w700),
          ),
        ),
      ],
    );
  }
}

/// 卡片內容與底部代碼之間的虛線。
class DashedLine extends StatelessWidget {
  const DashedLine({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: 1,
      width: double.infinity,
      child: CustomPaint(painter: _DashPainter()),
    );
  }
}

class _DashPainter extends CustomPainter {
  const _DashPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.cardEdge
      ..strokeWidth = size.height;
    for (
      var x = 0.0;
      x < size.width;
      x += AppSizes.dashLength + AppSizes.dashGap
    ) {
      canvas.drawLine(Offset(x, 0), Offset(x + AppSizes.dashLength, 0), paint);
    }
  }

  @override
  bool shouldRepaint(_DashPainter oldDelegate) => false;
}
