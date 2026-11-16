import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_message.dart';
import 'package:tabletop_hub/domains/games_advisor/state/game_card_text.dart';

// 推薦卡片的文字放在 state/，參考畫面與正式頁面共用（MR 說明標 ➕ 的情境）。

AdvisorGame game({
  int minPlayers = 2,
  int maxPlayers = 4,
  int minPlaytime = 30,
  int maxPlaytime = 45,
  int minAge = 10,
  double weight = 1.85,
}) => AdvisorGame(
  id: 1,
  name: '範例桌遊甲',
  minPlayers: minPlayers,
  maxPlayers: maxPlayers,
  minPlaytime: minPlaytime,
  maxPlaytime: maxPlaytime,
  minAge: minAge,
  weight: weight,
);

void main() {
  test('人數、時長、年齡、難度組成一行', () {
    expect(gameMetaText(game()), '2–4 人 · 30–45 分鐘 · 10 歲以上 · 難度 1.9 / 5');
  });

  test('最少等於最多：只寫一個數字', () {
    expect(
      gameMetaText(
        game(minPlayers: 4, maxPlayers: 4, minPlaytime: 30, maxPlaytime: 30),
      ),
      '4 人 · 30 分鐘 · 10 歲以上 · 難度 1.9 / 5',
    );
  });

  test('難度四捨五入到小數 1 位，整數也寫到小數 1 位', () {
    expect(gameMetaText(game(weight: 2)), endsWith('難度 2.0 / 5'));
    expect(gameMetaText(game(weight: 1.84)), endsWith('難度 1.8 / 5'));
  });

  test('放寬提示：時長、年齡', () {
    expect(relaxedConstraintText(RelaxedConstraint.playtime), '以下放寬了「時長」條件');
    expect(relaxedConstraintText(RelaxedConstraint.age), '以下放寬了「年齡」條件');
  });

  test('心得片段的語言標記：英文標「英文」，中文不標', () {
    expect(
      excerptLanguageLabel(
        const AdvisorExcerpt(id: 'e1', text: 'Quick and fun.', language: 'en'),
      ),
      '英文',
    );
    expect(
      excerptLanguageLabel(
        const AdvisorExcerpt(id: 'e2', text: '一局節奏很快', language: 'zh-TW'),
      ),
      isNull,
    );
  });
}
