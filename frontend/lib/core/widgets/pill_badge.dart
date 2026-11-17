import 'package:flutter/material.dart';

/// 膠囊標籤的用途。
enum PillTone {
  /// 一般資訊，例如店家、遊戲類型。
  neutral,

  /// 人數、新手友善（鼠尾草綠）。
  players,

  /// 時間、進行中（蜂蜜琥珀）。
  duration,

  /// 需要注意的重點，例如「剩 1 位」（焦糖橘）。
  accent,
}

/// 一種標籤的顏色。
@immutable
class PillColors {
  const PillColors({required this.background, required this.foreground});

  final Color background;
  final Color foreground;

  static PillColors lerp(PillColors a, PillColors b, double t) => PillColors(
    background: Color.lerp(a.background, b.background, t)!,
    foreground: Color.lerp(a.foreground, b.foreground, t)!,
  );
}

/// 膠囊標籤的樣式。這裡只定義欄位，實際的顏色與圓角由 `app/theme/` 提供。
@immutable
class PillBadgeTheme extends ThemeExtension<PillBadgeTheme> {
  const PillBadgeTheme({
    required this.neutral,
    required this.players,
    required this.duration,
    required this.accent,
    required this.radius,
    required this.padding,
    required this.iconGap,
    required this.textStyle,
  });

  final PillColors neutral;
  final PillColors players;
  final PillColors duration;
  final PillColors accent;
  final double radius;
  final EdgeInsetsGeometry padding;

  /// 圖示與文字的間距。
  final double iconGap;
  final TextStyle textStyle;

  PillColors colorsFor(PillTone tone) => switch (tone) {
    PillTone.neutral => neutral,
    PillTone.players => players,
    PillTone.duration => duration,
    PillTone.accent => accent,
  };

  @override
  PillBadgeTheme copyWith({
    PillColors? neutral,
    PillColors? players,
    PillColors? duration,
    PillColors? accent,
    double? radius,
    EdgeInsetsGeometry? padding,
    double? iconGap,
    TextStyle? textStyle,
  }) => PillBadgeTheme(
    neutral: neutral ?? this.neutral,
    players: players ?? this.players,
    duration: duration ?? this.duration,
    accent: accent ?? this.accent,
    radius: radius ?? this.radius,
    padding: padding ?? this.padding,
    iconGap: iconGap ?? this.iconGap,
    textStyle: textStyle ?? this.textStyle,
  );

  @override
  PillBadgeTheme lerp(PillBadgeTheme? other, double t) {
    if (other == null) return this;
    return PillBadgeTheme(
      neutral: PillColors.lerp(neutral, other.neutral, t),
      players: PillColors.lerp(players, other.players, t),
      duration: PillColors.lerp(duration, other.duration, t),
      accent: PillColors.lerp(accent, other.accent, t),
      radius: t < 0.5 ? radius : other.radius,
      padding: EdgeInsetsGeometry.lerp(padding, other.padding, t)!,
      iconGap: iconGap + (other.iconGap - iconGap) * t,
      textStyle: TextStyle.lerp(textStyle, other.textStyle, t)!,
    );
  }
}

/// 膠囊標籤，例如「4 人」「60 分鐘」「新手友善」。
class PillBadge extends StatelessWidget {
  const PillBadge({
    required this.label,
    this.tone = PillTone.neutral,
    this.icon,
    super.key,
  });

  final String label;
  final PillTone tone;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).extension<PillBadgeTheme>()!;
    final colors = theme.colorsFor(tone);
    final style = theme.textStyle.copyWith(color: colors.foreground);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.background,
        borderRadius: BorderRadius.circular(theme.radius),
      ),
      child: Padding(
        padding: theme.padding,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: style.fontSize, color: colors.foreground),
              SizedBox(width: theme.iconGap),
            ],
            Text(label, style: style),
          ],
        ),
      ),
    );
  }
}
