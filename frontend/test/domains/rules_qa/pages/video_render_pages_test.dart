// 規則影片：產生影片頁、選拍略過、步驟（add-rules-video-mobile MR 10，design.md D16 與外觀決定）。
// 看影片的播放頁要新增播放套件，另外處理。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';

import '../../../support/fakes.dart';
import '../video_assets_support.dart';
import 'video_pages_support.dart';

const sampleRender = VideoRender(
  jobId: 'j9',
  videoPath: '/api/v1/rules-videos/p1/render/video',
  totalSeconds: 42.5,
  reencoded: ['s1'],
  reused: ['s2'],
  skippedAssets: [],
  estimated: true,
  warnings: [],
);

const draftForSkip = VideoDraft(
  videoVersion: 1,
  segments: [
    DraftSegment(
      segmentKey: 's1',
      sourcePages: [7],
      beats: [DraftBeat(beatKey: 'b1', narration: '看牌。', subtitle: '看牌')],
    ),
  ],
  assets: [
    DraftAsset(
      assetKey: 'blue',
      kind: 'flat_photo',
      priority: 'optional',
      reason: '藍牌',
      shot: null,
      representative: false,
      regions: [],
      hasPhoto: false,
      skipped: true,
    ),
    DraftAsset(
      assetKey: 'red',
      kind: 'flat_photo',
      priority: 'optional',
      reason: '紅牌',
      shot: null,
      representative: false,
      regions: [],
      hasPhoto: false,
    ),
  ],
  coverage: DraftCoverage(
    status: 'done',
    totalRules: 1,
    issues: [],
    problems: [],
    hints: [],
  ),
  terms: DraftTerms(status: 'used'),
  pagesStale: false,
);

const redBlocked = VideoReadiness(
  ready: false,
  missingPhotos: [
    MissingPhoto(
      assetKey: 'red',
      priority: 'optional',
      reason: '紅牌',
      shot: null,
      skipAffectedSegments: [1, 2],
      skipBlockedSegments: [2],
    ),
  ],
  missingRegions: [],
  unsupported: [],
);

FakeVideoStudioRepository renderRepo({
  String step = 'render',
  VideoReadiness readiness = readyNone,
  VideoRender? render,
}) {
  final repo = assetsRepo(readiness: readiness)
    ..projects = [sampleVideoProject(step: step)];
  if (render != null) repo.renders['p1'] = render;
  return repo;
}

Finder inTile(String key, Finder finder) => find.descendant(
  of: find.byKey(Key('video-asset-tile-$key')),
  matching: finder,
);

void main() {
  group('產生影片', () {
    testWidgets('還缺東西：按鈕停用，列出缺什麼並連到素材頁', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/render',
        repo: renderRepo(step: 'assets', readiness: notReady),
      );
      final start = find.byKey(const Key('video-render-start'));
      expect(tester.widget<FilledButton>(start).onPressed, isNull);
      expect(find.textContaining('說明圖板上的兩個區域'), findsOneWidget);
      await tapKey(tester, 'video-render-go-assets');
      expect(h.path, '/videos/p1/assets');
    });

    testWidgets('按下產生 → 進行中：顯示真正的百分比與目前在做什麼', (tester) async {
      final repo = renderRepo()
        ..jobSequence = [
          sampleVideoJob(
            kind: 'render',
            status: VideoJobStatus.running,
            progress: 0.5,
            message: '段影片 2／3',
          ),
        ];
      await pumpVideo(
        tester,
        location: '/videos/p1/render',
        repo: repo,
        pollInterval: const Duration(seconds: 1),
      );
      await tester.tap(find.byKey(const Key('video-render-start')));
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(repo.startedRenders, ['p1']);
      expect(find.text('段影片 2／3'), findsOneWidget);
      expect(find.text('50%'), findsOneWidget);
      final bar = tester.widget<LinearProgressIndicator>(
        find.byType(LinearProgressIndicator),
      );
      expect(bar.value, 0.5);
      expect(find.text('可以離開這頁，完成後回來看'), findsOneWidget);
      // 進行中不能再按
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('video-render-start')))
            .onPressed,
        isNull,
      );
      await stopPolling(tester);
    });

    testWidgets('離開再回來：產生中就接著顯示進度', (tester) async {
      final running = sampleVideoJob(
        kind: 'render',
        status: VideoJobStatus.running,
        progress: 0.3,
        message: '旁白 2／5',
      );
      final repo = renderRepo()
        ..latestJobs['p1'] = running
        ..jobSequence = [running];
      await pumpVideo(
        tester,
        location: '/videos/p1/render',
        repo: repo,
        pollInterval: const Duration(seconds: 1),
        settle: false,
      );
      expect(find.text('旁白 2／5'), findsOneWidget);
      expect(find.text('30%'), findsOneWidget);
      await stopPolling(tester);
    });

    testWidgets('完成：顯示「影片已產生」與「看影片」、成品的總長', (tester) async {
      final repo = renderRepo(step: 'done', render: sampleRender)
        ..latestJobs['p1'] = sampleVideoJob(
          kind: 'render',
          status: VideoJobStatus.succeeded,
        );
      await pumpVideo(tester, location: '/videos/p1/render', repo: repo);
      expect(find.text('影片已產生'), findsOneWidget);
      expect(find.text('看影片'), findsWidgets);
      expect(find.textContaining('42.5 秒'), findsOneWidget);
      expect(find.textContaining('重新產生 1 段、沿用 1 段'), findsOneWidget);
      // 沒有設定文字轉語音：旁白靜音、時間為估計值
      expect(find.textContaining('時間為估計值'), findsOneWidget);
    });

    testWidgets('失敗：只寫原因與「重試」', (tester) async {
      final repo = renderRepo()
        ..latestJobs['p1'] = sampleVideoJob(
          kind: 'render',
          status: VideoJobStatus.failed,
          error: '影片輸出失敗，請再試一次；若一直發生請通知管理員',
        )
        ..jobSequence = [
          sampleVideoJob(kind: 'render', status: VideoJobStatus.succeeded),
        ];
      await pumpVideo(tester, location: '/videos/p1/render', repo: repo);
      expect(find.text('影片輸出失敗，請再試一次；若一直發生請通知管理員'), findsOneWidget);
      await tapText(tester, '重試');
      expect(repo.startedRenders, ['p1']);
    });
  });

  group('選拍略過', () {
    testWidgets('素材清單：只靠它的段標示「不能略過」；已略過的標示「已略過」', (tester) async {
      final repo = assetsRepo(readiness: redBlocked)
        ..drafts['p1'] = draftForSkip;
      await pumpVideo(tester, location: '/videos/p1/assets', repo: repo);
      expect(inTile('red', find.text('第 2 段只靠這張，不能略過')), findsOneWidget);
      expect(inTile('blue', find.text('已略過')), findsOneWidget);
    });

    testWidgets('略過前提示「略過後第 1 段會少一張圖」，確定後略過；可以取消', (tester) async {
      final repo = assetsRepo(
        asset: sampleAsset(
          key: 'blue',
          priority: 'optional',
          regions: const {},
        ).copyWith(skipAffectedSegments: [1]),
      );
      await pumpVideo(tester, location: '/videos/p1/assets/blue', repo: repo);
      await tapKey(tester, 'video-asset-skip');
      expect(find.text('略過後第 1 段會少一張圖'), findsOneWidget);
      await tapText(tester, '略過');
      expect(repo.updates.single.$3.skipped, isTrue);
      expect(find.text('已略過'), findsOneWidget);

      await tapKey(tester, 'video-asset-unskip');
      expect(repo.updates.last.$3.skipped, isFalse);
      expect(find.byKey(const Key('video-asset-skip')), findsOneWidget);
    });

    testWidgets('略過前按「取消」：不略過', (tester) async {
      final repo = assetsRepo(
        asset: sampleAsset(
          key: 'blue',
          priority: 'optional',
          regions: const {},
        ).copyWith(skipAffectedSegments: [1]),
      );
      await pumpVideo(tester, location: '/videos/p1/assets/blue', repo: repo);
      await tapKey(tester, 'video-asset-skip');
      await tapText(tester, '取消');
      expect(repo.updates, isEmpty);
    });

    testWidgets('只靠它的段：說明不能略過，沒有略過按鈕', (tester) async {
      final repo = assetsRepo(
        asset: sampleAsset(
          key: 'red',
          priority: 'optional',
          regions: const {},
        ).copyWith(skipAffectedSegments: [1, 2], skipBlockedSegments: [2]),
      );
      await pumpVideo(tester, location: '/videos/p1/assets/red', repo: repo);
      expect(find.text('第 2 段只靠這張，不能略過'), findsOneWidget);
      expect(find.byKey(const Key('video-asset-skip')), findsNothing);
    });

    testWidgets('必拍：沒有略過按鈕', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board',
        repo: assetsRepo(),
      );
      expect(find.byKey(const Key('video-asset-skip')), findsNothing);
    });
  });

  group('步驟', () {
    testWidgets('素材清單：齊了之後「下一步：產生影片」', (tester) async {
      final repo = assetsRepo(readiness: readyNone)
        ..drafts['p1'] = draftForSkip;
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/assets',
        repo: repo,
      );
      await tapKey(tester, 'video-assets-next');
      expect(h.path, '/videos/p1/render');
    });

    for (final (step, label, path) in [
      ('assets', '下一步：拍素材', '/videos/p1/assets'),
      ('render', '下一步：產生影片', '/videos/p1/render'),
    ]) {
      testWidgets('專案總覽：步驟 $step 的下一步是「$label」', (tester) async {
        final h = await pumpVideo(
          tester,
          location: '/videos/p1',
          repo: renderRepo(step: step),
        );
        expect(find.text(label), findsOneWidget);
        await tapKey(tester, 'video-next-step');
        expect(h.path, path);
      });
    }

    testWidgets('專案總覽：完成時下一步是「看影片」，四步都打勾', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: renderRepo(step: 'done', render: sampleRender),
      );
      expect(
        find.descendant(
          of: find.byKey(const Key('video-next-step')),
          matching: find.text('看影片'),
        ),
        findsOneWidget,
      );
      expect(find.byIcon(Icons.check_circle), findsNWidgets(4));
    });

    testWidgets('專案總覽：可以齊了以後點「影片」', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: renderRepo(step: 'render'),
      );
      await tapKey(tester, 'video-step-3');
      expect(h.path, '/videos/p1/render');
    });

    testWidgets('專案列表：完成的專案標示「完成」', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos',
        repo: renderRepo(step: 'done'),
      );
      expect(find.text('完成'), findsOneWidget);
    });
  });
}
