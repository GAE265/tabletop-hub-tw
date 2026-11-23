// 規則影片：產生影片、成品與選拍略過的 state（add-rules-video-mobile MR 10，design.md D16）。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_assets_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_job_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_projects_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_render_state.dart';

import '../../support/fakes.dart';
import 'video_assets_support.dart';

ProviderContainer makeContainer(FakeVideoStudioRepository repo) {
  final container = ProviderContainer(
    overrides: [
      videoStudioRepositoryProvider.overrideWithValue(repo),
      videoJobPollIntervalProvider.overrideWithValue(Duration.zero),
      imagePickerProvider.overrideWithValue(FakeImagePicker()),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

const sampleRender = VideoRender(
  jobId: 'j9',
  videoPath: '/api/v1/rules-videos/p1/render/video',
  totalSeconds: 42.5,
  reencoded: ['s1'],
  reused: ['s2'],
  skippedAssets: [],
  estimated: false,
  warnings: [],
);

void main() {
  group('產生影片', () {
    test('按下產生 → 進行中 → 完成：重新讀成品與專案', () async {
      final repo = assetsRepo(readiness: readyNone)
        ..jobSequence = [
          sampleVideoJob(
            kind: 'render',
            status: VideoJobStatus.running,
            progress: 0.5,
            message: '段影片 2／3',
          ),
          sampleVideoJob(kind: 'render', status: VideoJobStatus.succeeded),
        ];
      final container = makeContainer(repo);
      expect(await container.read(videoRenderProvider('p1').future), isNull);
      repo
        ..renders['p1'] = sampleRender
        ..projects = [sampleVideoProject(step: 'done')];

      final notifier = container.read(videoJobProvider('p1').notifier);
      await notifier.startRender();
      await notifier.finished;
      expect(repo.startedRenders, ['p1']);
      expect(container.read(videoJobProvider('p1')).job!.kind, 'render');
      expect(
        (await container.read(videoRenderProvider('p1').future))!.totalSeconds,
        42.5,
      );
      expect(
        (await container.read(videoProjectProvider('p1').future)).step,
        'done',
      );
    });

    test('素材沒齊（422 RULES_VIDEO_NOT_READY）：顯示說明，不建立工作', () async {
      final repo = assetsRepo()
        ..startRenderError = const ApiException(
          code: 'RULES_VIDEO_NOT_READY',
          message: '還不能產生影片，請先補齊素材',
          statusCode: 422,
        );
      final container = makeContainer(repo);
      await container.read(videoJobProvider('p1').notifier).startRender();
      final state = container.read(videoJobProvider('p1'));
      expect(state.error, '還不能產生影片，請先補齊素材');
      expect(state.job, isNull);
    });

    test('已有進行中的工作（409）：接上那個工作', () async {
      final repo = assetsRepo(readiness: readyNone)
        ..startRenderError = const ApiException(
          code: 'RULES_VIDEO_JOB_RUNNING',
          message: '已有進行中的工作',
          statusCode: 409,
          details: {'job_id': 'j-running'},
        )
        ..jobSequence = [
          sampleVideoJob(
            id: 'j-running',
            kind: 'render',
            status: VideoJobStatus.succeeded,
          ),
        ];
      final container = makeContainer(repo);
      final notifier = container.read(videoJobProvider('p1').notifier);
      await notifier.startRender();
      await notifier.finished;
      expect(repo.polledJobs, contains('j-running'));
    });
  });

  group('選拍略過', () {
    VideoAssetRef blue = (projectId: 'p1', assetKey: 'blue');

    FakeVideoStudioRepository skipRepo({List<int> blocked = const []}) =>
        assetsRepo(
          asset: sampleAsset(
            key: 'blue',
            priority: 'optional',
            regions: const {},
          ).copyWith(skipAffectedSegments: [1], skipBlockedSegments: blocked),
        );

    test('略過：存 skipped，重新讀缺什麼', () async {
      final repo = skipRepo();
      final container = makeContainer(repo);
      final notifier = container.read(videoAssetProvider(blue).notifier);
      await notifier.load();
      await container.read(videoReadinessProvider('p1').future);
      repo.readiness['p1'] = readyNone;

      expect(await notifier.setSkipped(true), isTrue);
      expect(repo.updates.single.$3.skipped, isTrue);
      expect(container.read(videoAssetProvider(blue)).asset!.skipped, isTrue);
      expect(
        (await container.read(videoReadinessProvider('p1').future)).ready,
        isTrue,
      );
    });

    test('取消略過', () async {
      final repo = skipRepo();
      final container = makeContainer(repo);
      final notifier = container.read(videoAssetProvider(blue).notifier);
      await notifier.load();
      await notifier.setSkipped(true);
      await notifier.setSkipped(false);
      expect(repo.updates.last.$3.skipped, isFalse);
      expect(container.read(videoAssetProvider(blue)).asset!.skipped, isFalse);
    });

    test('只靠它的段不能略過（422）：顯示後端的說明', () async {
      final repo = skipRepo(blocked: [2])
        ..updateError = const ApiException(
          code: 'RULES_VIDEO_SKIP_BLOCKED',
          message: '第 2 段只靠這張，不能略過',
          statusCode: 422,
          details: {
            'segments': [2],
          },
        );
      final container = makeContainer(repo);
      final notifier = container.read(videoAssetProvider(blue).notifier);
      await notifier.load();
      expect(await notifier.setSkipped(true), isFalse);
      expect(container.read(videoAssetProvider(blue)).error, '第 2 段只靠這張，不能略過');
    });

    test('文字：略過前的提示、不能略過的原因', () {
      expect(skipConfirmText([1]), '略過後第 1 段會少一張圖');
      expect(skipConfirmText([1, 3]), '略過後第 1、3 段會少一張圖');
      expect(skipBlockedText([2]), '第 2 段只靠這張，不能略過');
    });
  });
}
