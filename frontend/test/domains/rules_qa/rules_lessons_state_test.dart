// 遊戲清單與教學頁（spec：rules-qa-page 的「遊戲清單」「教學頁」）。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/state/rules_lesson_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/rules_lessons_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

const notFound = ApiException(
  code: 'RULES_LESSON_NOT_FOUND',
  message: '這款遊戲還沒有教材',
  statusCode: 404,
);

void main() {
  group('遊戲清單', () {
    test('載入清單，有影片的遊戲 hasVideo=true', () async {
      final container = makeContainer(sampleRepo());
      final items = await container.read(rulesLessonsProvider.future);
      expect(items.map((e) => e.gameName), ['有影片的桌遊', '只有規則書的桌遊']);
      expect(items.first.hasVideo, isTrue);
    });

    test('沒有任何教材：空清單', () async {
      final container = makeContainer(sampleRepo()..lessons = []);
      expect(await container.read(rulesLessonsProvider.future), isEmpty);
    });

    test('載入失敗：錯誤；重試後恢復', () async {
      final repo = sampleRepo()
        ..listError = const ApiException(
          code: 'NETWORK_ERROR',
          message: '無法連線',
        );
      final container = makeContainer(repo);
      container.listen(rulesLessonsProvider, (_, _) {});
      await expectLater(
        container.read(rulesLessonsProvider.future),
        throwsA(isA<ApiException>()),
      );

      repo.listError = null;
      await container.read(rulesLessonsProvider.notifier).reload();
      expect(container.read(rulesLessonsProvider).value, hasLength(2));
    });
  });

  group('教學頁', () {
    Future<RulesLessonState> load(FakeRulesQaRepository repo, int id) async {
      final container = makeContainer(repo);
      container.listen(rulesLessonProvider(id), (_, _) {});
      await container.read(rulesLessonProvider(id).notifier).loaded;
      return container.read(rulesLessonProvider(id));
    }

    test('有影片：先看影片，問答區尚未開放', () async {
      final state = await load(sampleRepo(), 1);
      expect(state.lesson.value!.video, isNotNull);
      expect(state.chat, ChatAvailability.waitingForVideo);
    });

    test('按「看完了，開始提問」：問答區開放', () async {
      final container = makeContainer(sampleRepo());
      container.listen(rulesLessonProvider(1), (_, _) {});
      final notifier = container.read(rulesLessonProvider(1).notifier);
      await notifier.loaded;
      notifier.startAsking();
      expect(
        container.read(rulesLessonProvider(1)).chat,
        ChatAvailability.open,
      );
    });

    test('沒有影片：直接開放問答', () async {
      final state = await load(sampleRepo(), 2);
      expect(state.lesson.value!.video, isNull);
      expect(state.chat, ChatAvailability.open);
    });

    test('只有影片、沒有規則書：不能提問', () async {
      final container = makeContainer(sampleRepo());
      container.listen(rulesLessonProvider(3), (_, _) {});
      final notifier = container.read(rulesLessonProvider(3).notifier);
      await notifier.loaded;
      notifier.startAsking();
      expect(
        container.read(rulesLessonProvider(3)).chat,
        ChatAvailability.noRulebook,
      );
    });

    test('遊戲沒有教材：保留後端的錯誤訊息', () async {
      final repo = sampleRepo()..lessonError = notFound;
      final state = await load(repo, 9);
      expect(state.lesson.error, isA<ApiException>());
      expect((state.lesson.error! as ApiException).message, '這款遊戲還沒有教材');
      expect(state.chat, ChatAvailability.unavailable);
    });
  });
}
