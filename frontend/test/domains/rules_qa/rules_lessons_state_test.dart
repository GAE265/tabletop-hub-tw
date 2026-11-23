// 遊戲清單與教學頁（spec：rules-qa-page 的「遊戲清單」「教學頁」）。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_models.dart';
import 'package:tabletop_hub/domains/rules_qa/state/rules_lesson_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/rules_lessons_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

const notFound = ApiException(
  code: 'RULES_LESSON_NOT_FOUND',
  message: '這款遊戲還沒有教材',
  statusCode: 404,
);

const _lessons = [
  RulesLessonSummary(
    gameId: 1,
    gameName: 'Catan 卡坦島',
    hasVideo: true,
    hasRulebook: true,
  ),
  RulesLessonSummary(
    gameId: 2,
    gameName: '璀璨寶石',
    hasVideo: false,
    hasRulebook: true,
  ),
  RulesLessonSummary(
    gameId: 3,
    gameName: '只有影片的遊戲',
    hasVideo: true,
    hasRulebook: false,
  ),
];

List<String> names(List<RulesLessonSummary> items) =>
    items.map((e) => e.gameName).toList();

void main() {
  group('搜尋與篩選（Stitch 版面）', () {
    test('全部、沒有搜尋：照原本順序全部列出', () {
      expect(names(filterLessons(_lessons, const LessonsQuery())), [
        'Catan 卡坦島',
        '璀璨寶石',
        '只有影片的遊戲',
      ]);
    });

    test('有教學影片：只列有影片的', () {
      expect(
        names(
          filterLessons(
            _lessons,
            const LessonsQuery(filter: LessonFilter.video),
          ),
        ),
        ['Catan 卡坦島', '只有影片的遊戲'],
      );
    });

    test('可以問規則：只列有規則書的', () {
      expect(
        names(
          filterLessons(
            _lessons,
            const LessonsQuery(filter: LessonFilter.rulebook),
          ),
        ),
        ['Catan 卡坦島', '璀璨寶石'],
      );
    });

    test('搜尋遊戲名稱：部分符合、不分大小寫、忽略前後空白', () {
      expect(
        names(filterLessons(_lessons, const LessonsQuery(search: ' catan '))),
        ['Catan 卡坦島'],
      );
      expect(names(filterLessons(_lessons, const LessonsQuery(search: '寶石'))), [
        '璀璨寶石',
      ]);
    });

    test('搜尋加篩選：兩個條件都要符合', () {
      expect(
        names(
          filterLessons(
            _lessons,
            const LessonsQuery(search: '遊戲', filter: LessonFilter.rulebook),
          ),
        ),
        isEmpty,
      );
    });

    test('各篩選的筆數（不受搜尋影響）', () {
      expect(lessonCount(_lessons, LessonFilter.all), 3);
      expect(lessonCount(_lessons, LessonFilter.video), 2);
      expect(lessonCount(_lessons, LessonFilter.rulebook), 2);
    });

    test('改搜尋與篩選：provider 記住目前的條件', () {
      final container = makeContainer(sampleRepo());
      final notifier = container.read(lessonsQueryProvider.notifier);
      notifier.setSearch('卡坦');
      notifier.setFilter(LessonFilter.video);
      expect(
        container.read(lessonsQueryProvider),
        const LessonsQuery(search: '卡坦', filter: LessonFilter.video),
      );
    });
  });

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
