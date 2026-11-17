import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/rules_qa_repository.dart';

import '../../support/fakes.dart';

const youtubeVideo = LessonVideo(
  source: LessonVideoSource.youtube,
  videoUrl: 'https://youtu.be/abc123',
  youtubeId: 'abc123',
  title: '測試桌遊規則教學',
);

const suggested = ['怎麼開始一局？', '一個回合可以做什麼？'];

/// 遊戲 1：影片＋規則書；遊戲 2：只有規則書；遊戲 3：只有影片。
FakeRulesQaRepository sampleRepo() => FakeRulesQaRepository(
  lessons: const [
    RulesLessonSummary(
      gameId: 1,
      gameName: '有影片的桌遊',
      hasVideo: true,
      hasRulebook: true,
    ),
    RulesLessonSummary(
      gameId: 2,
      gameName: '只有規則書的桌遊',
      hasVideo: false,
      hasRulebook: true,
    ),
  ],
  details: const {
    1: RulesLesson(
      gameId: 1,
      gameName: '有影片的桌遊',
      video: youtubeVideo,
      hasRulebook: true,
      suggestedQuestions: suggested,
    ),
    2: RulesLesson(
      gameId: 2,
      gameName: '只有規則書的桌遊',
      video: null,
      hasRulebook: true,
      suggestedQuestions: suggested,
    ),
    3: RulesLesson(
      gameId: 3,
      gameName: '只有影片的桌遊',
      video: youtubeVideo,
      hasRulebook: false,
      suggestedQuestions: suggested,
    ),
  },
);

RulesAnswer answer({
  String responseId = 'r-1',
  String text = '每個回合抽兩張牌。',
  bool answerable = true,
  List<int> pages = const [3],
}) => RulesAnswer(
  responseId: responseId,
  answer: text,
  answerable: answerable,
  citations: [for (final page in pages) Citation(page: page)],
);

ProviderContainer makeContainer(FakeRulesQaRepository repo) {
  final container = ProviderContainer(
    overrides: [rulesQaRepositoryProvider.overrideWithValue(repo)],
  );
  addTearDown(container.dispose);
  return container;
}
