// 規則影片生產器 1d 的手機頁 state（add-rules-video-mobile MR 6，design.md D12；
// 整個遊戲一支影片見 D17：建立只選遊戲、沒有選頁與編輯文字、草稿只顯示摘要）。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_draft_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_job_state.dart';
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

const sampleDraft = VideoDraft(
  videoVersion: 1,
  segments: [
    DraftSegment(
      segmentKey: 's1',
      chapter: 'setup',
      sourcePages: [7],
      beats: [
        DraftBeat(beatKey: 'b1', narration: '先洗牌。', subtitle: '洗牌。'),
        DraftBeat(beatKey: 'b2', narration: '再翻開。', subtitle: '翻開。'),
      ],
    ),
    DraftSegment(
      segmentKey: 's2',
      chapter: 'round',
      sourcePages: [8],
      beats: [DraftBeat(beatKey: 'b3', narration: '輪到下一位。', subtitle: '換人。')],
    ),
    DraftSegment(
      segmentKey: 's3',
      chapter: 'round',
      sourcePages: [8],
      beats: [DraftBeat(beatKey: 'b4', narration: '打出一張牌。', subtitle: '出牌。')],
    ),
  ],
  assets: [
    DraftAsset(
      assetKey: 'board',
      label: '盤面',
      kind: 'flat_photo',
      priority: 'must',
      reason: 'r',
      shot: null,
      representative: false,
      regions: [],
      hasPhoto: false,
    ),
    DraftAsset(
      assetKey: 'coin',
      kind: 'flat_photo',
      priority: 'optional',
      reason: '金幣',
      shot: null,
      representative: false,
      regions: [],
      hasPhoto: false,
    ),
  ],
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
      expect(projects.single.title, '假遊戲 規則教學');
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

  group('專案總覽', () {
    test('讀單一專案', () async {
      final repo = FakeVideoStudioRepository(
        projects: [sampleVideoProject(step: 'draft')],
      );
      final container = makeContainer(repo);
      final project = await container.read(videoProjectProvider('p1').future);
      expect(project.step, 'draft');
    });

    test('草稿工作完成後重新讀專案（步驟會變）', () async {
      final repo = FakeVideoStudioRepository(projects: [sampleVideoProject()])
        ..jobSequence = [sampleVideoJob(status: VideoJobStatus.succeeded)];
      final container = makeContainer(repo);
      expect(
        (await container.read(videoProjectProvider('p1').future)).step,
        'draft',
      );
      repo.projects = [sampleVideoProject(step: 'assets')];
      final notifier = container.read(videoJobProvider('p1').notifier);
      await notifier.startDraft();
      await notifier.finished;
      expect(
        (await container.read(videoProjectProvider('p1').future)).step,
        'assets',
      );
    });
  });

  group('建立專案（只選遊戲）', () {
    test('選了遊戲才能送出', () {
      final container = makeContainer(FakeVideoStudioRepository());
      final form = container.read(videoProjectFormProvider.notifier);
      expect(container.read(videoProjectFormProvider).canSubmit, isFalse);
      form.selectGame(const VideoGameOption(id: 1, name: '假遊戲'));
      expect(container.read(videoProjectFormProvider).canSubmit, isTrue);
    });

    test('送出成功：只送遊戲，回傳新專案', () async {
      final repo = FakeVideoStudioRepository();
      final container = makeContainer(repo);
      final form = container.read(videoProjectFormProvider.notifier)
        ..selectGame(const VideoGameOption(id: 1, name: '假遊戲'));
      final project = await form.submit();
      expect(project?.id, 'p-new');
      expect(repo.created.single.toJson(), {'game_id': 1});
    });

    test('規則書還沒匯入（422）：顯示後端的說明', () async {
      final repo = FakeVideoStudioRepository()
        ..createError = const ApiException(
          code: 'RULES_VIDEO_NO_RULEBOOK',
          message: '這款遊戲的規則書還沒有匯入，請管理員先匯入',
          statusCode: 422,
        );
      final container = makeContainer(repo);
      final form = container.read(videoProjectFormProvider.notifier)
        ..selectGame(const VideoGameOption(id: 9, name: '沒有規則書'));
      expect(await form.submit(), isNull);
      expect(
        container.read(videoProjectFormProvider).error,
        '這款遊戲的規則書還沒有匯入，請管理員先匯入',
      );
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
      expect(draft?.segments.first.segmentKey, 's1');
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

    test('草稿摘要：三格各幾段、必拍與選拍各幾個', () {
      final summary = draftSummary(sampleDraft);
      expect(
        [
          for (final slot in summary.slots)
            (slot.title, slot.segments, slot.beats),
        ],
        [('開局', 1, 2), ('走完一輪', 2, 2), ('獲勝方式', 0, 0)],
      );
      expect(summary.mustAssets, 1);
      expect(summary.optionalAssets, 1);
    });

    test('素材的名稱：有中文名稱用名稱，沒有時用 reason', () {
      expect(assetDisplayName(sampleDraft.assets[0]), '盤面');
      expect(assetDisplayName(sampleDraft.assets[1]), '金幣');
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
