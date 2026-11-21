import '../data/advisor_message.dart';

// 推薦卡片上的文字。參考畫面與正式頁面共用，規則只寫這一次（spec §14.3）。

/// 最少等於最多時只寫一個數字，例如 `4`；不同時寫 `2–4`。
String _range(int min, int max) => min == max ? '$min' : '$min–$max';

/// 卡片的資訊行，例如 `2–4 人 · 30–45 分鐘 · 10 歲以上 · 難度 1.9 / 5`。
/// 難度四捨五入到小數 1 位，整數也寫成 `2.0`。
String gameMetaText(AdvisorGame game) => [
  '${_range(game.minPlayers, game.maxPlayers)} 人',
  '${_range(game.minPlaytime, game.maxPlaytime)} 分鐘',
  '${game.minAge} 歲以上',
  '難度 ${game.weight.toStringAsFixed(1)} / 5',
].join(' · ');

/// 卡片上方的放寬提示，整則訊息顯示一次。
String relaxedConstraintText(RelaxedConstraint constraint) =>
    switch (constraint) {
      RelaxedConstraint.playtime => '以下放寬了「時長」條件',
      RelaxedConstraint.age => '以下放寬了「年齡」條件',
    };

/// 卡片上「店家沒有這款」的提示：只有確定那間店沒有（`inStock` 是 false）才有文字；
/// 店裡有、或這次沒有帶店家（null）都不提示（回 null）。
String? stockHintText(AdvisorRecommendation recommendation) =>
    recommendation.inStock == false ? '這間店目前沒有這款桌遊' : null;

/// 心得片段旁的語言標記：英文標「英文」，中文不標（回 null）。
String? excerptLanguageLabel(AdvisorExcerpt excerpt) =>
    excerpt.language == 'en' ? '英文' : null;
