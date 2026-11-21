// 規則影片生產器 1d 的手機頁（add-rules-video-mobile MR 6，design.md D12 與外觀決定；
// 整個遊戲一支影片見 D17：建立只選遊戲、自動產生草稿、沒有選頁與編輯文字、草稿只顯示摘要）。
// 行為邏輯已由 state 測試涵蓋，這裡確認畫面有呈現 state、按鈕接對、路由正確。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';

import '../../../support/fakes.dart';
import 'video_pages_support.dart';

CoverageSlot slotOf(
  String slot,
  String title, {
  String status = 'done',
  String? reason,
  List<CoverageIssue> issues = const [],
  List<CoverageHint> hints = const [],
}) => CoverageSlot(
  slot: slot,
  title: title,
  status: status,
  reason: reason,
  totalRules: 3,
  issues: issues,
  problems: const [],
  hints: hints,
);

const missingFive = CoverageIssue(
  ruleId: 'setup-R1',
  category: 'action',
  source: '每位玩家拿 5 張牌',
  narrationStatus: 'missing',
  narrationMissing: '5 張',
  subtitleStatus: 'missing',
  narrationShorter: false,
);

DraftCoverage coverageOf(
  List<CoverageSlot> slots, {
  String status = 'done',
  String? reason,
}) => DraftCoverage(
  status: status,
  reason: reason,
  totalRules: 9,
  issues: [for (final s in slots) ...s.issues],
  problems: const [],
  hints: [for (final s in slots) ...s.hints],
  slots: slots,
);

final cleanCoverage = coverageOf([
  slotOf('setup', '開局'),
  slotOf('round', '走完一輪'),
  slotOf('win', '獲勝方式'),
]);

VideoDraft draftOf({
  DraftCoverage? coverage,
  DraftTerms terms = const DraftTerms(status: 'used'),
}) => VideoDraft(
  videoVersion: 1,
  segments: const [
    DraftSegment(
      segmentKey: 's1',
      chapter: 'setup',
      sourcePages: [3],
      beats: [
        DraftBeat(beatKey: 'b1', narration: '先把牌洗勻。', subtitle: '洗牌'),
        DraftBeat(beatKey: 'b2', narration: '每人拿三張。', subtitle: '拿三張'),
      ],
    ),
    DraftSegment(
      segmentKey: 's2',
      chapter: 'round',
      sourcePages: [6],
      beats: [DraftBeat(beatKey: 'b3', narration: '輪到下一位。', subtitle: '換人')],
    ),
    DraftSegment(
      segmentKey: 's3',
      chapter: 'win',
      sourcePages: [8],
      beats: [DraftBeat(beatKey: 'b4', narration: '白薔薇出現就結束。', subtitle: '結束')],
    ),
  ],
  assets: const [
    DraftAsset(
      assetKey: 'white_rose',
      label: '白薔薇',
      kind: 'flat_photo',
      priority: 'must',
      reason: '要認得白薔薇',
      shot: '整張牌，正面朝上',
      representative: false,
      regions: [],
      hasPhoto: false,
    ),
    DraftAsset(
      assetKey: 'coin',
      label: '金幣',
      kind: 'flat_photo',
      priority: 'optional',
      reason: '輔助說明',
      shot: null,
      representative: false,
      regions: [],
      hasPhoto: false,
    ),
  ],
  coverage: coverage ?? cleanCoverage,
  terms: terms,
  pagesStale: false,
);

FakeVideoStudioRepository draftRepo(VideoDraft draft) =>
    FakeVideoStudioRepository(
      projects: [sampleVideoProject()],
      drafts: {'p1': draft},
    );

void main() {
  group('權限', () {
    for (final user in [fakePlayer, null]) {
      testWidgets('${user?.role ?? '沒有身分'}直接打開網址：顯示沒有權限，不呼叫 API', (
        tester,
      ) async {
        final repo = FakeVideoStudioRepository()
          ..listError = StateError('不應該呼叫');
        await pumpVideo(tester, location: '/videos', repo: repo, user: user);
        expect(find.text('只有店家人員可以使用影片功能'), findsOneWidget);
      });
    }

    testWidgets('管理員可以使用', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos',
        user: fakeAdmin,
        repo: FakeVideoStudioRepository(projects: [sampleVideoProject()]),
      );
      expect(find.text('假遊戲 規則教學'), findsOneWidget);
    });
  });

  group('專案列表', () {
    testWidgets('列出影片標題與目前步驟；點下進到專案總覽', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos',
        repo: FakeVideoStudioRepository(projects: [sampleVideoProject()]),
      );
      expect(find.text('假遊戲 規則教學'), findsOneWidget);
      expect(find.text('草稿'), findsOneWidget);
      expect(find.textContaining('章'), findsNothing); // 不再顯示章節
      await tapText(tester, '假遊戲 規則教學');
      expect(h.path, '/videos/p1');
    });

    testWidgets('沒有專案：顯示「還沒有專案」與新增按鈕', (tester) async {
      final h = await pumpVideo(tester, location: '/videos');
      expect(find.text('還沒有專案'), findsOneWidget);
      await tapText(tester, '新增專案');
      expect(h.path, '/videos/new');
    });

    testWidgets('讀取失敗：顯示錯誤，按「重試」後恢復', (tester) async {
      final repo = FakeVideoStudioRepository()
        ..listError = const ApiException(code: 'NETWORK_ERROR', message: '連不上');
      await pumpVideo(tester, location: '/videos', repo: repo);
      expect(find.text('連不上'), findsOneWidget);
      repo
        ..listError = null
        ..projects = [sampleVideoProject()];
      await tapText(tester, '重試');
      expect(find.text('假遊戲 規則教學'), findsOneWidget);
    });
  });

  group('建立專案（只選遊戲）', () {
    testWidgets('只有選遊戲；選了才能按；建立後進到專案總覽看草稿進度', (tester) async {
      final repo = FakeVideoStudioRepository(
        games: const [VideoGameOption(id: 1, name: '假遊戲')],
      );
      final h = await pumpVideo(tester, location: '/videos/new', repo: repo);
      expect(
        find.byKey(const Key('video-project-chapter-number')),
        findsNothing,
      );
      expect(
        find.byKey(const Key('video-project-chapter-title')),
        findsNothing,
      );
      final submit = find.byKey(const Key('video-project-submit'));
      expect(tester.widget<FilledButton>(submit).onPressed, isNull);

      await tester.tap(find.byKey(const Key('video-project-game')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('假遊戲').last);
      await tester.pumpAndSettle();
      expect(find.text('建立並產生草稿'), findsOneWidget);
      expect(tester.widget<FilledButton>(submit).onPressed, isNotNull);

      await tester.tap(submit);
      await tester.pumpAndSettle();
      expect(repo.created.single.gameId, 1);
      expect(h.path, '/videos/p-new');
    });

    testWidgets('規則書還沒匯入：顯示說明，不顯示錯誤代碼', (tester) async {
      final repo =
          FakeVideoStudioRepository(
              games: const [VideoGameOption(id: 9, name: '沒有規則書')],
            )
            ..createError = const ApiException(
              code: 'RULES_VIDEO_NO_RULEBOOK',
              message: '這款遊戲的規則書還沒有匯入，請管理員先匯入',
              statusCode: 422,
            );
      await pumpVideo(tester, location: '/videos/new', repo: repo);
      await tester.tap(find.byKey(const Key('video-project-game')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('沒有規則書').last);
      await tester.pumpAndSettle();
      await tapKey(tester, 'video-project-submit');
      expect(find.text('這款遊戲的規則書還沒有匯入，請管理員先匯入'), findsOneWidget);
      expect(find.textContaining('RULES_VIDEO'), findsNothing);
    });
  });

  group('專案總覽', () {
    testWidgets('三個步驟（草稿、素材、影片），沒有「頁面文字」', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: FakeVideoStudioRepository(projects: [sampleVideoProject()]),
      );
      for (final label in ['草稿', '素材', '影片']) {
        expect(find.text(label), findsOneWidget, reason: label);
      }
      expect(find.text('頁面文字'), findsNothing);
      expect(find.text('假遊戲 規則教學'), findsOneWidget);
    });

    testWidgets('草稿還在產生：下一步是看草稿進度', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: FakeVideoStudioRepository(projects: [sampleVideoProject()]),
      );
      expect(find.text('查看草稿進度'), findsOneWidget);
      await tapKey(tester, 'video-next-step');
      expect(h.path, '/videos/p1/draft');
    });

    testWidgets('有草稿：不擋流程，下一步直接拍素材', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: draftRepo(draftOf()),
      );
      expect(find.text('下一步：拍素材'), findsOneWidget);
      await tapKey(tester, 'video-next-step');
      expect(h.path, '/videos/p1/assets');
    });

    testWidgets('離開再回來：最近的草稿工作還在進行，就顯示階段文字與不確定進度的橫條', (tester) async {
      final repo = FakeVideoStudioRepository(projects: [sampleVideoProject()])
        ..latestJobs['p1'] = sampleVideoJob(
          status: VideoJobStatus.running,
          progress: 0.5,
          message: 'AI 分類規則（開局、走完一輪、獲勝方式）',
        )
        ..jobSequence = [
          sampleVideoJob(
            status: VideoJobStatus.running,
            progress: 0.5,
            message: 'AI 產生草稿',
          ),
        ];
      // 不確定進度的橫條一直在動，不能用 pumpAndSettle
      await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: repo,
        pollInterval: const Duration(seconds: 1),
        settle: false,
      );
      expect(find.text('AI 分類規則（開局、走完一輪、獲勝方式）'), findsOneWidget);
      expect(find.text('可以離開這頁，完成後回來看'), findsOneWidget);
      final bar = tester.widget<LinearProgressIndicator>(
        find.byType(LinearProgressIndicator),
      );
      expect(bar.value, isNull);
      expect(find.text('50%'), findsNothing);
      await stopPolling(tester);
    });
  });

  group('工作進度', () {
    testWidgets('失敗：只寫店員看得懂的原因與「重試」，按下重新產生', (tester) async {
      final repo = FakeVideoStudioRepository(projects: [sampleVideoProject()])
        ..latestJobs['p1'] = sampleVideoJob(
          status: VideoJobStatus.failed,
          error: '規則書裡找不到「獲勝方式」的內容，無法產生影片；請管理員確認規則書是否完整匯入',
        );
      repo.jobSequence = [sampleVideoJob(status: VideoJobStatus.succeeded)];
      await pumpVideo(tester, location: '/videos/p1', repo: repo);
      expect(find.textContaining('找不到「獲勝方式」'), findsOneWidget);
      await tapText(tester, '重試');
      expect(repo.startedDrafts, ['p1']);
    });

    testWidgets('完成：顯示「查看草稿」', (tester) async {
      final repo = draftRepo(draftOf())
        ..latestJobs['p1'] = sampleVideoJob(status: VideoJobStatus.succeeded);
      final h = await pumpVideo(tester, location: '/videos/p1', repo: repo);
      expect(find.text('草稿已產生'), findsOneWidget);
      await tapText(tester, '查看草稿');
      expect(h.path, '/videos/p1/draft');
    });
  });

  group('草稿（只顯示摘要，不擋流程）', () {
    testWidgets('三格各幾段幾句、必拍與選拍各幾個；不列逐句內容', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf()),
      );
      final summary = find.byKey(const Key('video-draft-summary'));
      for (final text in ['開局：1 段、2 句', '走完一輪：1 段、1 句', '獲勝方式：1 段、1 句']) {
        expect(
          find.descendant(of: summary, matching: find.text(text)),
          findsOneWidget,
          reason: text,
        );
      }
      expect(
        find.descendant(of: summary, matching: find.text('素材：必拍 1、選拍 1')),
        findsOneWidget,
      );
      expect(find.text('先把牌洗勻。'), findsNothing);
      expect(find.byKey(const Key('video-check-count')), findsNothing);
    });

    testWidgets('涵蓋檢查依格顯示；細節展開才看', (tester) async {
      final coverage = coverageOf([
        slotOf('setup', '開局', issues: const [missingFive]),
        slotOf('round', '走完一輪'),
        slotOf(
          'win',
          '獲勝方式',
          hints: const [CoverageHint(ruleId: 'win-R2', source: '目的說明')],
        ),
      ]);
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf(coverage: coverage)),
      );
      expect(find.text('開局：1 項問題'), findsOneWidget);
      expect(find.text('走完一輪：沒有發現問題'), findsOneWidget);
      expect(find.text('獲勝方式：1 項提示'), findsOneWidget);
      expect(find.text('每位玩家拿 5 張牌'), findsNothing);
      await tapKey(tester, 'video-coverage-toggle');
      expect(find.text('每位玩家拿 5 張牌'), findsOneWidget);
      expect(find.text('目的說明'), findsOneWidget);
    });

    testWidgets('某一格的涵蓋檢查沒做成：寫出原因', (tester) async {
      final coverage = coverageOf(
        [
          slotOf('setup', '開局'),
          slotOf(
            'round',
            '走完一輪',
            status: 'not_done',
            reason: '涵蓋檢查沒有完成：AI 服務暫時無法使用',
          ),
          slotOf('win', '獲勝方式'),
        ],
        status: 'not_done',
        reason: '「走完一輪」的涵蓋檢查沒有完成',
      );
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf(coverage: coverage)),
      );
      expect(find.text('走完一輪：涵蓋檢查沒有完成：AI 服務暫時無法使用'), findsOneWidget);
    });

    testWidgets('提示橫幅：對照表、涵蓋檢查過期', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(
          draftOf(
            terms: const DraftTerms(
              status: 'missing',
              message: '這款遊戲還沒有用語對照表，草稿的用詞品質可能下降',
            ),
            coverage: coverageOf(
              [
                slotOf('setup', '開局'),
                slotOf('round', '走完一輪'),
                slotOf('win', '獲勝方式'),
              ],
              status: 'stale',
              reason: '旁白或字幕在涵蓋檢查之後改過，結果可能過期',
            ),
          ),
        ),
      );
      expect(find.text('這款遊戲還沒有用語對照表，草稿的用詞品質可能下降'), findsOneWidget);
      expect(find.text('旁白或字幕在涵蓋檢查之後改過，結果可能過期'), findsOneWidget);
    });

    testWidgets('「下一步：拍素材」不擋流程', (tester) async {
      final coverage = coverageOf([
        slotOf('setup', '開局', issues: const [missingFive]),
        slotOf('round', '走完一輪'),
        slotOf('win', '獲勝方式'),
      ]);
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf(coverage: coverage)),
      );
      final next = find.byKey(const Key('video-draft-next'));
      expect(tester.widget<FilledButton>(next).onPressed, isNotNull);
      await tapKey(tester, 'video-draft-next');
      expect(h.path, '/videos/p1/assets');
    });

    testWidgets('還沒有草稿：說明在產生中，可以產生草稿', (tester) async {
      final repo = FakeVideoStudioRepository(projects: [sampleVideoProject()])
        ..jobSequence = [sampleVideoJob(status: VideoJobStatus.succeeded)];
      await pumpVideo(tester, location: '/videos/p1/draft', repo: repo);
      expect(find.text('還沒有草稿'), findsOneWidget);
      await tapText(tester, '產生草稿');
      expect(repo.startedDrafts, ['p1']);
    });

    testWidgets('「重新產生」：建立草稿工作並顯示進度', (tester) async {
      final repo = draftRepo(draftOf())
        ..jobSequence = [
          sampleVideoJob(status: VideoJobStatus.running, message: 'AI 產生草稿'),
        ];
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: repo,
        pollInterval: const Duration(seconds: 1),
      );
      final button = find.byKey(const Key('video-draft-regenerate'));
      await tester.ensureVisible(button);
      await tester.pumpAndSettle();
      await tester.tap(button);
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(repo.startedDrafts, ['p1']);
      expect(find.text('AI 產生草稿'), findsOneWidget);
      expect(find.text('可以離開這頁，完成後回來看'), findsOneWidget);
      await stopPolling(tester);
    });

    testWidgets('沒有「選頁與編輯文字」的路由', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/pages',
        repo: draftRepo(draftOf()),
      );
      expect(find.byKey(const Key('video-pages-page')), findsNothing);
    });
  });
}
