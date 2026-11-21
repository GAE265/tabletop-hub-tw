// 規則影片生產器 1d 的手機頁 state（add-rules-video-mobile MR 6，design.md D12）。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_draft_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_job_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_pages_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_projects_state.dart';

import '../../support/fakes.dart';

ProviderContainer makeContainer(FakeVideoStudioRepository repo) {
  final container = ProviderContainer(
    overrides: [
      videoStudioRepositoryProvider.overrideWithValue(repo),
      videoJobPollIntervalProvider.overrideWithValue(Duration.zero),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

VideoPageText page7({String? text}) => VideoPageText(
  page: 7,
  role: 'chapter',
  original: '把所有有蓋子的木箱排成一列。',
  text: text ?? '把所有有蓋子的木箱排成一列。',
  originalChanged: false,
  removed: const [],
  changed: const [],
);

VideoPages samplePages({List<VideoPageText>? pages, int version = 1}) =>
    VideoPages(
      availablePages: const [2, 7, 8],
      chapterPages: const [7],
      referencePages: const [],
      pagesVersion: version,
      pages: pages ?? [page7()],
    );

const sampleDraft = VideoDraft(
  videoVersion: 1,
  segments: [
    DraftSegment(
      segmentKey: 's1',
      sourcePages: [7],
      beats: [
        DraftBeat(beatKey: 'b1', narration: '先洗牌。', subtitle: '洗牌。'),
        DraftBeat(beatKey: 'b2', narration: '再翻開。', subtitle: '翻開。'),
      ],
    ),
  ],
  assets: [],
  coverage: DraftCoverage(
    status: 'done',
    totalRules: 3,
    issues: [],
    problems: [],
    hints: [],
  ),
  terms: DraftTerms(status: 'missing', message: '這款遊戲還沒有用語對照表，草稿的用詞品質可能下降'),
  pagesStale: false,
);

Future<void> settle() => Future<void>.delayed(Duration.zero);

void main() {
  group('專案列表', () {
    test('載入專案', () async {
      final repo = FakeVideoStudioRepository(projects: [sampleVideoProject()]);
      final container = makeContainer(repo);
      final projects = await container.read(videoProjectsProvider.future);
      expect(projects.single.chapterTitle, '步驟三');
    });

    test('沒有專案', () async {
      final container = makeContainer(FakeVideoStudioRepository());
      expect(await container.read(videoProjectsProvider.future), isEmpty);
    });

    test('讀取失敗後重試', () async {
      final repo = FakeVideoStudioRepository()
        ..listError = const ApiException(code: 'NETWORK_ERROR', message: '連不上');
      final container = makeContainer(repo);
      await expectLater(
        container.read(videoProjectsProvider.future),
        throwsA(isA<ApiException>()),
      );
      repo
        ..listError = null
        ..projects = [sampleVideoProject()];
      await container.read(videoProjectsProvider.notifier).reload();
      expect(container.read(videoProjectsProvider).value, hasLength(1));
    });
  });

  group('建立專案', () {
    test('欄位齊全才能送出；標題去掉空白後 1–50 字', () {
      final container = makeContainer(FakeVideoStudioRepository());
      final form = container.read(videoProjectFormProvider.notifier);
      expect(container.read(videoProjectFormProvider).canSubmit, isFalse);
      form
        ..selectGame(const VideoGameOption(id: 1, name: '假遊戲'))
        ..setChapterNumber('11')
        ..setChapterTitle('   ');
      expect(container.read(videoProjectFormProvider).canSubmit, isFalse);
      form.setChapterTitle('長' * 51);
      expect(container.read(videoProjectFormProvider).canSubmit, isFalse);
      form.setChapterTitle(' 步驟三 ');
      expect(container.read(videoProjectFormProvider).canSubmit, isTrue);
      form.setChapterNumber('0');
      expect(container.read(videoProjectFormProvider).canSubmit, isFalse);
    });

    test('送出成功：回傳新專案、標題去掉空白', () async {
      final repo = FakeVideoStudioRepository();
      final container = makeContainer(repo);
      final form = container.read(videoProjectFormProvider.notifier)
        ..selectGame(const VideoGameOption(id: 1, name: '假遊戲'))
        ..setChapterNumber('11')
        ..setChapterTitle(' 步驟三 ');
      final project = await form.submit();
      expect(project?.id, 'p-new');
      expect(repo.created.single.chapterTitle, '步驟三');
    });

    test('送出失敗：顯示後端的說明', () async {
      final repo = FakeVideoStudioRepository()
        ..createError = const ApiException(
          code: 'GAME_NOT_FOUND',
          message: '找不到桌遊 9',
          statusCode: 404,
        );
      final container = makeContainer(repo);
      final form = container.read(videoProjectFormProvider.notifier)
        ..selectGame(const VideoGameOption(id: 9, name: '不存在'))
        ..setChapterNumber('1')
        ..setChapterTitle('第一章');
      expect(await form.submit(), isNull);
      expect(container.read(videoProjectFormProvider).error, '找不到桌遊 9');
    });
  });

  group('選頁與編輯文字', () {
    test('載入、修改文字、儲存', () async {
      final repo = FakeVideoStudioRepository(pages: {'p1': samplePages()});
      final container = makeContainer(repo);
      final provider = videoPagesProvider('p1');
      await container.read(provider.notifier).load();
      expect(container.read(provider).pages?.pages.single.page, 7);
      expect(container.read(provider).dirty, isFalse);

      container.read(provider.notifier).editText(7, '把所有蓋好的木箱排成一列。');
      expect(container.read(provider).dirty, isTrue);
      expect(await container.read(provider.notifier).save(), isTrue);
      final (_, sent) = repo.savedPages.single;
      expect(sent.chapterPages, [7]);
      expect(sent.texts, {'7': '把所有蓋好的木箱排成一列。'});
      expect(container.read(provider).dirty, isFalse);
    });

    test('換選頁：保留還在的頁的文字，立刻儲存', () async {
      final repo = FakeVideoStudioRepository(pages: {'p1': samplePages()});
      final container = makeContainer(repo);
      final provider = videoPagesProvider('p1');
      await container.read(provider.notifier).load();
      container.read(provider.notifier).editText(7, '改過');
      await container
          .read(provider.notifier)
          .selectPages(chapter: [7, 8], reference: [2]);
      final (_, sent) = repo.savedPages.single;
      expect(sent.chapterPages, [7, 8]);
      expect(sent.referencePages, [2]);
      expect(sent.texts, {'7': '改過'}); // 新選的頁不給文字：後端用原文
    });

    test('缺頁：提示請管理員先匯入', () async {
      final repo = FakeVideoStudioRepository(pages: {'p1': samplePages()})
        ..savePagesError = const ApiException(
          code: 'RULES_VIDEO_PAGES_MISSING',
          message: '規則書還沒有這幾頁',
          statusCode: 422,
          details: {
            'missing': [3, 9],
          },
        );
      final container = makeContainer(repo);
      final provider = videoPagesProvider('p1');
      await container.read(provider.notifier).load();
      expect(
        await container.read(provider.notifier).selectPages(chapter: [3, 9]),
        isFalse,
      );
      expect(container.read(provider).error, '請管理員先匯入第 3、9 頁');
    });

    test('本章全部空白：提示沒有文字', () async {
      final repo = FakeVideoStudioRepository(pages: {'p1': samplePages()})
        ..savePagesError = const ApiException(
          code: 'RULES_VIDEO_PAGES_EMPTY',
          message: '本章頁的文字全部是空白，沒有東西可以產生草稿',
          statusCode: 422,
        );
      final container = makeContainer(repo);
      final provider = videoPagesProvider('p1');
      await container.read(provider.notifier).load();
      container.read(provider.notifier).editText(7, '');
      expect(await container.read(provider.notifier).save(), isFalse);
      expect(container.read(provider).error, contains('沒有東西可以產生草稿'));
    });

    test('確認差異：刪掉的段落與改過的行都保留原文與編輯後', () async {
      final reviewed = samplePages(
        pages: [
          page7(text: '把所有蓋好的木箱排成一列。').copyWith(
            changed: const [
              ChangedLine(
                original: '把所有有蓋子的木箱排成一列。',
                edited: '把所有蓋好的木箱排成一列。',
                similarity: 0.95,
              ),
            ],
            removed: const [
              RemovedBlock(lines: ['# 收工', '籌碼收進收納盒時活動結束。']),
            ],
          ),
        ],
      );
      final repo = FakeVideoStudioRepository(pages: {'p1': reviewed});
      final container = makeContainer(repo);
      final provider = videoPagesProvider('p1');
      await container.read(provider.notifier).load();
      final differences = container.read(provider).differences;
      expect(differences, hasLength(2));
      expect(differences.first.original, '把所有有蓋子的木箱排成一列。');
      expect(differences.first.edited, '把所有蓋好的木箱排成一列。');
      expect(differences.last.original, '# 收工\n籌碼收進收納盒時活動結束。');
      expect(differences.last.edited, isNull); // 刪掉：只有原文
    });
  });

  group('工作進度', () {
    test('產生草稿：queued → running → succeeded，完成後重新讀草稿', () async {
      final repo = FakeVideoStudioRepository()
        ..jobSequence = [
          sampleVideoJob(
            status: VideoJobStatus.running,
            progress: 0.5,
            message: 'AI 產生草稿',
          ),
          sampleVideoJob(status: VideoJobStatus.succeeded, progress: 1),
        ]
        ..drafts = {'p1': sampleDraft};
      final container = makeContainer(repo);
      final provider = videoJobProvider('p1');
      await container.read(provider.notifier).startDraft();
      await container.read(provider.notifier).finished;
      expect(repo.startedDrafts, ['p1']);
      expect(container.read(provider).job?.status, VideoJobStatus.succeeded);
      expect(container.read(provider).running, isFalse);
      expect(repo.polledJobs, isNotEmpty);
      final draft = await container.read(videoDraftProvider('p1').future);
      expect(draft?.segments.single.segmentKey, 's1');
    });

    test('工作失敗：顯示 error', () async {
      final repo = FakeVideoStudioRepository()
        ..jobSequence = [
          sampleVideoJob(
            status: VideoJobStatus.failed,
            error: 'AI 服務暫時無法使用（連線逾時或忙碌），請稍後再產生一次',
          ),
        ];
      final container = makeContainer(repo);
      final provider = videoJobProvider('p1');
      await container.read(provider.notifier).startDraft();
      await container.read(provider.notifier).finished;
      expect(container.read(provider).job?.error, contains('AI 服務暫時無法使用'));
    });

    test('已有進行中的工作（409）：接上那個工作', () async {
      final repo = FakeVideoStudioRepository()
        ..startDraftError = const ApiException(
          code: 'RULES_VIDEO_JOB_RUNNING',
          message: '這個專案已經有進行中的工作',
          statusCode: 409,
          details: {'job_id': 'j-running'},
        )
        ..jobSequence = [
          sampleVideoJob(id: 'j-running', status: VideoJobStatus.succeeded),
        ];
      final container = makeContainer(repo);
      final provider = videoJobProvider('p1');
      await container.read(provider.notifier).startDraft();
      await container.read(provider.notifier).finished;
      expect(repo.polledJobs.first, 'j-running');
      expect(container.read(provider).job?.status, VideoJobStatus.succeeded);
    });

    test('還沒存頁面文字（422）：提示先選頁', () async {
      final repo = FakeVideoStudioRepository()
        ..startDraftError = const ApiException(
          code: 'RULES_VIDEO_PAGES_NOT_SET',
          message: '還沒有選本章頁，請先選頁並確認文字',
          statusCode: 422,
        );
      final container = makeContainer(repo);
      final provider = videoJobProvider('p1');
      await container.read(provider.notifier).startDraft();
      expect(container.read(provider).error, '還沒有選本章頁，請先選頁並確認文字');
      expect(container.read(provider).job, isNull);
    });

    test('離開再回來：最近的工作還在進行，就接著查', () async {
      final repo = FakeVideoStudioRepository()
        ..latestJobs['p1'] = sampleVideoJob(status: VideoJobStatus.running)
        ..jobSequence = [sampleVideoJob(status: VideoJobStatus.succeeded)];
      final container = makeContainer(repo);
      final provider = videoJobProvider('p1');
      await container.read(provider.notifier).resume();
      await container.read(provider.notifier).finished;
      expect(container.read(provider).job?.status, VideoJobStatus.succeeded);
    });

    test('離開再回來：最近的工作已結束，就不查', () async {
      final repo = FakeVideoStudioRepository()
        ..latestJobs['p1'] = sampleVideoJob(
          status: VideoJobStatus.failed,
          error: '失敗了',
        );
      final container = makeContainer(repo);
      final provider = videoJobProvider('p1');
      await container.read(provider.notifier).resume();
      expect(container.read(provider).job?.error, '失敗了');
      expect(repo.polledJobs, isEmpty);
    });
  });

  group('草稿', () {
    test('還沒有草稿', () async {
      final container = makeContainer(FakeVideoStudioRepository());
      expect(await container.read(videoDraftProvider('p1').future), isNull);
    });

    test('逐句勾選「已檢查」：只存在畫面上', () async {
      final repo = FakeVideoStudioRepository(drafts: {'p1': sampleDraft});
      final container = makeContainer(repo);
      await container.read(videoDraftProvider('p1').future);
      final checks = container.read(subtitleChecksProvider('p1').notifier);
      checks.toggle('b1');
      expect(container.read(subtitleChecksProvider('p1')), {'b1'});
      checks.toggle('b1');
      expect(container.read(subtitleChecksProvider('p1')), isEmpty);
      checks.toggle('b2');
      expect(
        checkedCount(container.read(subtitleChecksProvider('p1')), sampleDraft),
        (1, 2),
      );
    });

    test('對照表與依舊文字的提示原樣提供', () async {
      final stale = sampleDraft.copyWith(
        pagesStale: true,
        pagesStaleMessage: '這份草稿依舊的頁面文字產生，建議重新產生',
      );
      final repo = FakeVideoStudioRepository(drafts: {'p1': stale});
      final container = makeContainer(repo);
      final draft = await container.read(videoDraftProvider('p1').future);
      expect(draft?.terms.message, contains('用語對照表'));
      expect(draft?.pagesStaleMessage, contains('依舊的頁面文字'));
    });
  });
}
