// 規則教學清單：有 AI 語音主持的遊戲，卡片上多一個「有語音主持」標籤。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/host/state/host_labels.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_models.dart';
import 'package:tabletop_hub/domains/rules_qa/pages/rules_lessons_page.dart';

import '../support.dart';
import 'rules_pages_test.dart' show lessonCards, pumpPage;

void main() {
  testWidgets('血與刃的白薔薇：卡片上有「有語音主持」；其他遊戲沒有', (tester) async {
    final repo = sampleRepo()
      ..lessons = [
        const RulesLessonSummary(
          gameId: 9,
          gameName: hostGameName,
          hasVideo: true,
          hasRulebook: true,
        ),
        ...sampleRepo().lessons,
      ];
    await pumpPage(tester, const RulesLessonsPage(), repo: repo);
    expect(lessonCards, findsNWidgets(3));
    expect(
      find.descendant(of: lessonCards.at(0), matching: find.text('有語音主持')),
      findsOneWidget,
    );
    for (final i in [1, 2]) {
      expect(
        find.descendant(of: lessonCards.at(i), matching: find.text('有語音主持')),
        findsNothing,
      );
    }
  });
}
