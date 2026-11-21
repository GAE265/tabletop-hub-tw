// 規則影片生產器 1d 的手機頁（add-rules-video-mobile MR 6，design.md D12 與外觀決定）。
// 行為邏輯已由 state 測試涵蓋，這裡確認畫面有呈現 state、按鈕接對、路由正確。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/core/dev/data/dev_user.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/pages/video_routes.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_job_state.dart';

import '../../../support/fakes.dart';

VideoPageText pageText(
  int page, {
  String role = 'chapter',
  String text = '原文',
  String? original,
  bool originalChanged = false,
  List<RemovedBlock> removed = const [],
  List<ChangedLine> changed = const [],
}) => VideoPageText(
  page: page,
  role: role,
  original: original ?? text,
  text: text,
  originalChanged: originalChanged,
  removed: removed,
  changed: changed,
);

VideoPages pagesOf(
  List<VideoPageText> pages, {
  List<int> available = const [2, 7, 8],
}) => VideoPages(
  availablePages: available,
  chapterPages: [
    for (final p in pages)
      if (p.role == 'chapter') p.page,
  ],
  referencePages: [
    for (final p in pages)
      if (p.role == 'reference') p.page,
  ],
  pagesVersion: 1,
  pages: pages,
);

VideoDraft draftOf({
  DraftCoverage? coverage,
  DraftTerms terms = const DraftTerms(status: 'used'),
  bool pagesStale = false,
  String? pagesStaleMessage,
}) => VideoDraft(
  videoVersion: 1,
  segments: const [
    DraftSegment(
      segmentKey: 's1',
      sourcePages: [7, 8],
      beats: [
        DraftBeat(beatKey: 'b1', narration: '先把牌洗勻。', subtitle: '洗牌'),
        DraftBeat(beatKey: 'b2', narration: '再翻開一張。', subtitle: '翻一張'),
      ],
    ),
    DraftSegment(
      segmentKey: 's2',
      sourcePages: [8],
      beats: [DraftBeat(beatKey: 'b3', narration: '輪到下一位。', subtitle: '換人')],
    ),
  ],
  assets: const [
    DraftAsset(
      assetKey: 'white_rose',
      kind: 'photo',
      priority: 'required',
      reason: '說明白玫瑰的位置',
      shot: '整張牌，正面朝上',
      representative: false,
      regions: [],
      hasPhoto: false,
    ),
  ],
  coverage:
      coverage ??
      const DraftCoverage(
        status: 'done',
        totalRules: 3,
        issues: [],
        problems: [],
        hints: [],
      ),
  terms: terms,
  pagesStale: pagesStale,
  pagesStaleMessage: pagesStaleMessage,
);

const coverageWithFindings = DraftCoverage(
  status: 'done',
  totalRules: 5,
  issues: [
    CoverageIssue(
      ruleId: 'r1',
      category: 'setup',
      source: '每位玩家拿 5 張牌',
      narrationStatus: 'missing',
      narrationMissing: '5 張',
      subtitleStatus: 'ok',
      narrationShorter: false,
    ),
  ],
  problems: [
    CoverageProblem(
      beatKey: 'b2',
      track: 'subtitle',
      kind: 'invented',
      text: '翻一張',
      reason: '規則書沒有提到',
    ),
  ],
  hints: [CoverageHint(ruleId: 'r2', source: '這一步的目的是讓大家知道順序')],
);

final checkCount = find.byKey(const Key('video-check-count'));

class Harness {
  Harness(this.repo, this.router);

  final FakeVideoStudioRepository repo;
  final GoRouter router;

  String get path => router.state.uri.toString();
}

Future<Harness> pumpVideo(
  WidgetTester tester, {
  required String location,
  FakeVideoStudioRepository? repo,
  DevUser? user = fakeStaff,
  Size size = const Size(400, 900),
  Duration pollInterval = Duration.zero,
  bool settle = true,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final fake = repo ?? FakeVideoStudioRepository();
  final router = GoRouter(
    initialLocation: location,
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => const Scaffold(body: Text('首頁')),
      ),
      videoStudioRoute,
    ],
  );
  addTearDown(router.dispose);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        videoStudioRepositoryProvider.overrideWithValue(fake),
        videoJobPollIntervalProvider.overrideWithValue(pollInterval),
        currentDevUserProvider.overrideWithValue(user),
      ],
      child: MaterialApp.router(
        theme: buildAppTheme(const FakeAppFonts()),
        routerConfig: router,
      ),
    ),
  );
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
    await tester.pump();
  }
  return Harness(fake, router);
}

/// 工作一直在進行的測試：拆掉畫面後讓排定的查詢跑完，查詢迴圈發現已拆掉就結束。
Future<void> stopPolling(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox());
  await tester.pump(const Duration(seconds: 1));
}

Future<void> tapText(WidgetTester tester, String text) async {
  final target = find.text(text);
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Future<void> tapKey(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

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
      expect(find.text('假遊戲'), findsOneWidget);
    });
  });

  group('專案列表', () {
    testWidgets('列出遊戲、章節與目前步驟；點下進到專案總覽', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos',
        repo: FakeVideoStudioRepository(projects: [sampleVideoProject()]),
      );
      expect(find.text('假遊戲'), findsOneWidget);
      expect(find.text('第 11 章　步驟三'), findsOneWidget);
      expect(find.text('選頁與編輯文字'), findsOneWidget);
      await tapText(tester, '假遊戲');
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
      expect(find.text('假遊戲'), findsOneWidget);
    });
  });

  group('建立專案', () {
    testWidgets('填齊才能按「建立」；建立後進到專案總覽', (tester) async {
      final repo = FakeVideoStudioRepository(
        games: const [VideoGameOption(id: 1, name: '假遊戲')],
      );
      final h = await pumpVideo(tester, location: '/videos/new', repo: repo);
      final submit = find.byKey(const Key('video-project-submit'));
      expect(tester.widget<FilledButton>(submit).onPressed, isNull);

      await tester.tap(find.byKey(const Key('video-project-game')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('假遊戲').last);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('video-project-chapter-number')),
        '11',
      );
      await tester.enterText(
        find.byKey(const Key('video-project-chapter-title')),
        '步驟三',
      );
      await tester.pumpAndSettle();
      expect(tester.widget<FilledButton>(submit).onPressed, isNotNull);

      await tester.tap(submit);
      await tester.pumpAndSettle();
      expect(repo.created.single.chapterNumber, 11);
      expect(h.path, '/videos/p-new');
    });

    testWidgets('後端錯誤：顯示說明，不顯示錯誤代碼', (tester) async {
      final repo =
          FakeVideoStudioRepository(
              games: const [VideoGameOption(id: 9, name: '不存在')],
            )
            ..createError = const ApiException(
              code: 'GAME_NOT_FOUND',
              message: '找不到這款桌遊',
              statusCode: 404,
            );
      await pumpVideo(tester, location: '/videos/new', repo: repo);
      await tester.tap(find.byKey(const Key('video-project-game')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('不存在').last);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('video-project-chapter-number')),
        '1',
      );
      await tester.enterText(
        find.byKey(const Key('video-project-chapter-title')),
        '開始',
      );
      await tester.pumpAndSettle();
      await tapKey(tester, 'video-project-submit');
      expect(find.text('找不到這款桌遊'), findsOneWidget);
      expect(find.textContaining('GAME_NOT_FOUND'), findsNothing);
    });
  });

  group('專案總覽', () {
    testWidgets('四個步驟，目前在「頁面文字」；下一步前往選頁', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: FakeVideoStudioRepository(projects: [sampleVideoProject()]),
      );
      for (final label in ['頁面文字', '草稿', '素材', '影片']) {
        expect(find.text(label), findsOneWidget, reason: label);
      }
      await tapKey(tester, 'video-next-step');
      expect(h.path, '/videos/p1/pages');
    });

    testWidgets('有草稿：下一步前往草稿', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: FakeVideoStudioRepository(
          projects: [sampleVideoProject(step: 'draft')],
        ),
      );
      await tapKey(tester, 'video-next-step');
      expect(h.path, '/videos/p1/draft');
    });

    testWidgets('離開再回來：最近的草稿工作還在進行，就顯示階段文字與不確定進度的橫條', (tester) async {
      final repo = FakeVideoStudioRepository(projects: [sampleVideoProject()])
        ..latestJobs['p1'] = sampleVideoJob(
          status: VideoJobStatus.running,
          progress: 0.5,
          message: 'AI 產生草稿',
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
      expect(find.text('AI 產生草稿'), findsOneWidget);
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
          error: 'AI 暫時無法使用，請稍後再試',
        );
      repo.jobSequence = [sampleVideoJob(status: VideoJobStatus.succeeded)];
      await pumpVideo(tester, location: '/videos/p1', repo: repo);
      expect(find.text('AI 暫時無法使用，請稍後再試'), findsOneWidget);
      await tapText(tester, '重試');
      expect(repo.startedDrafts, ['p1']);
    });

    testWidgets('完成：顯示「查看草稿」', (tester) async {
      final repo = FakeVideoStudioRepository(
        projects: [sampleVideoProject(step: 'draft')],
      )..latestJobs['p1'] = sampleVideoJob(status: VideoJobStatus.succeeded);
      final h = await pumpVideo(tester, location: '/videos/p1', repo: repo);
      expect(find.text('草稿已產生'), findsOneWidget);
      await tapText(tester, '查看草稿');
      expect(h.path, '/videos/p1/draft');
    });
  });

  group('選頁與編輯文字', () {
    FakeVideoStudioRepository pagesRepo() => FakeVideoStudioRepository(
      projects: [sampleVideoProject()],
      pages: {
        'p1': pagesOf([
          pageText(7, text: '將所有牌洗勻。'),
          pageText(8, text: '輪到下一位玩家。'),
        ]),
      },
    );

    testWidgets('列出可選的頁與每頁的文字；改文字後儲存', (tester) async {
      final repo = pagesRepo();
      await pumpVideo(tester, location: '/videos/p1/pages', repo: repo);
      for (final page in [2, 7, 8]) {
        expect(
          find.byKey(Key('video-page-chip-$page')),
          findsOneWidget,
          reason: '$page',
        );
      }
      final editor = find.byKey(const Key('video-page-editor-7'));
      expect(
        find.descendant(of: editor, matching: find.text('將所有牌洗勻。')),
        findsOneWidget,
      );

      await tester.enterText(editor, '將所有的牌洗勻。');
      await tester.pumpAndSettle();
      await tapKey(tester, 'video-pages-save');
      final (_, sent) = repo.savedPages.single;
      expect(sent.texts['7'], '將所有的牌洗勻。');
    });

    testWidgets('點可選的頁：加進本章並立刻儲存', (tester) async {
      final repo = pagesRepo();
      await pumpVideo(tester, location: '/videos/p1/pages', repo: repo);
      await tapKey(tester, 'video-page-chip-2');
      final (_, sent) = repo.savedPages.single;
      expect(sent.chapterPages, [7, 8, 2]);
    });

    testWidgets('切到「參考」後點頁：加進參考頁', (tester) async {
      final repo = pagesRepo();
      await pumpVideo(tester, location: '/videos/p1/pages', repo: repo);
      await tapText(tester, '參考');
      await tapKey(tester, 'video-page-chip-2');
      final (_, sent) = repo.savedPages.single;
      expect(sent.chapterPages, [7, 8]);
      expect(sent.referencePages, [2]);
    });

    testWidgets('缺頁：提示請管理員先匯入', (tester) async {
      final repo = pagesRepo()
        ..savePagesError = const ApiException(
          code: 'RULES_VIDEO_PAGES_MISSING',
          message: '缺頁',
          statusCode: 422,
          details: {
            'missing': [3, 9],
          },
        );
      await pumpVideo(tester, location: '/videos/p1/pages', repo: repo);
      await tapKey(tester, 'video-page-chip-2');
      expect(find.text('請管理員先匯入第 3、9 頁'), findsOneWidget);
    });

    testWidgets('從草稿的出處頁進來（?page=8）：那一頁的編輯框取得焦點', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/pages?page=8',
        repo: pagesRepo(),
      );
      bool focused(int page) => tester
          .widget<EditableText>(
            find.descendant(
              of: find.byKey(Key('video-page-editor-$page')),
              matching: find.byType(EditableText),
            ),
          )
          .focusNode
          .hasFocus;
      expect(focused(8), isTrue);
      expect(focused(7), isFalse);
    });

    testWidgets('「下一步：確認差異」：有改過先儲存，再前往確認差異', (tester) async {
      final repo = pagesRepo();
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/pages',
        repo: repo,
      );
      await tester.enterText(
        find.byKey(const Key('video-page-editor-7')),
        '改過',
      );
      await tester.pumpAndSettle();
      await tapKey(tester, 'video-pages-next');
      expect(repo.savedPages, hasLength(1));
      expect(h.path, '/videos/p1/pages/review');
    });
  });

  group('確認差異', () {
    FakeVideoStudioRepository reviewRepo({bool originalChanged = false}) =>
        FakeVideoStudioRepository(
          projects: [sampleVideoProject()],
          pages: {
            'p1': pagesOf([
              pageText(
                7,
                text: '將所有牌洗勻。',
                original: '將所有牌冼勻。',
                originalChanged: originalChanged,
                changed: const [
                  ChangedLine(
                    original: '將所有牌冼勻。',
                    edited: '將所有牌洗勻。',
                    similarity: 0.9,
                  ),
                ],
              ),
              pageText(
                8,
                text: '輪到下一位。',
                original: '廣告文字\n輪到下一位。',
                removed: const [
                  RemovedBlock(lines: ['廣告文字']),
                ],
              ),
            ]),
          },
        );

    testWidgets('改過與刪掉的地方都同時顯示原文與編輯後', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/pages/review',
        repo: reviewRepo(),
      );
      expect(find.text('將所有牌冼勻。'), findsOneWidget);
      expect(find.text('將所有牌洗勻。'), findsOneWidget);
      expect(find.text('改過'), findsOneWidget);
      expect(find.text('廣告文字'), findsOneWidget);
      expect(find.text('刪掉'), findsOneWidget);
    });

    testWidgets('原文被重新上傳：那一頁加註', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/pages/review',
        repo: reviewRepo(originalChanged: true),
      );
      expect(find.text('第 7 頁的原文已改變，請再確認一次'), findsOneWidget);
    });

    testWidgets('按「產生草稿」：建立工作並回到專案總覽看進度', (tester) async {
      final repo = reviewRepo()
        ..jobSequence = [sampleVideoJob(status: VideoJobStatus.succeeded)];
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/pages/review',
        repo: repo,
      );
      await tapKey(tester, 'video-start-draft');
      expect(repo.startedDrafts, ['p1']);
      expect(h.path, '/videos/p1');
    });

    testWidgets('還沒存頁面文字（422）：留在這頁並顯示說明', (tester) async {
      final repo = reviewRepo()
        ..startDraftError = const ApiException(
          code: 'RULES_VIDEO_PAGES_NOT_SET',
          message: '請先選頁並儲存頁面文字',
          statusCode: 422,
        );
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/pages/review',
        repo: repo,
      );
      await tapKey(tester, 'video-start-draft');
      expect(find.text('請先選頁並儲存頁面文字'), findsOneWidget);
      expect(h.path, '/videos/p1/pages/review');
    });
  });

  group('草稿確認', () {
    FakeVideoStudioRepository draftRepo(VideoDraft draft) =>
        FakeVideoStudioRepository(
          projects: [sampleVideoProject(step: 'draft')],
          drafts: {'p1': draft},
        );

    testWidgets('每段一張卡片，列出旁白與字幕；出處頁標籤', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf()),
      );
      expect(find.text('先把牌洗勻。'), findsOneWidget);
      expect(find.text('洗牌'), findsOneWidget);
      expect(find.text('輪到下一位。'), findsOneWidget);
      expect(find.byKey(const Key('video-segment-s1')), findsOneWidget);
      expect(find.byKey(const Key('video-segment-s2')), findsOneWidget);
      expect(find.text('p.7'), findsOneWidget);
      expect(find.text('p.8'), findsNWidgets(2));
    });

    testWidgets('點出處頁 p.7：跳到那一頁的文字編輯', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf()),
      );
      await tapText(tester, 'p.7');
      expect(h.path, '/videos/p1/pages?page=7');
    });

    testWidgets('頁首直接顯示涵蓋檢查摘要，細節展開才看', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf(coverage: coverageWithFindings)),
      );
      expect(find.text('2 項問題'), findsOneWidget);
      expect(find.text('1 項提示'), findsOneWidget);
      expect(find.text('每位玩家拿 5 張牌'), findsNothing);

      await tapKey(tester, 'video-coverage-toggle');
      expect(find.text('每位玩家拿 5 張牌'), findsOneWidget);
      expect(find.textContaining('5 張'), findsWidgets);
      expect(find.textContaining('規則書沒有提到'), findsOneWidget);
      expect(find.text('這一步的目的是讓大家知道順序'), findsOneWidget);
    });

    testWidgets('沒有問題：摘要寫「沒有發現問題」', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf()),
      );
      expect(find.text('涵蓋檢查沒有發現問題'), findsOneWidget);
    });

    testWidgets('涵蓋檢查沒做成：顯示原因', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(
          draftOf(
            coverage: const DraftCoverage(
              status: 'not_done',
              reason: 'AI 暫時無法使用',
              totalRules: 0,
              issues: [],
              problems: [],
              hints: [],
            ),
          ),
        ),
      );
      expect(find.text('涵蓋檢查沒做成：AI 暫時無法使用'), findsOneWidget);
    });

    testWidgets('提示橫幅：對照表、依舊文字產生、涵蓋檢查過期', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(
          draftOf(
            terms: const DraftTerms(
              status: 'missing',
              message: '這款遊戲還沒有用語對照表，草稿的用詞品質可能下降',
            ),
            pagesStale: true,
            pagesStaleMessage: '這份草稿依舊的頁面文字產生，建議重新產生',
            coverage: const DraftCoverage(
              status: 'stale',
              reason: '旁白或字幕在涵蓋檢查之後改過，結果可能過期',
              totalRules: 3,
              issues: [],
              problems: [],
              hints: [],
            ),
          ),
        ),
      );
      expect(find.text('這款遊戲還沒有用語對照表，草稿的用詞品質可能下降'), findsOneWidget);
      expect(find.text('這份草稿依舊的頁面文字產生，建議重新產生'), findsOneWidget);
      expect(find.text('旁白或字幕在涵蓋檢查之後改過，結果可能過期'), findsOneWidget);
    });

    testWidgets('上傳了空的對照表：不顯示對照表提示', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf(terms: const DraftTerms(status: 'empty'))),
      );
      expect(find.textContaining('用語對照表'), findsNothing);
    });

    testWidgets('逐句勾選「已檢查」；沒勾完也能按「確認草稿」', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf()),
      );
      expect(
        find.descendant(of: checkCount, matching: find.text('已檢查 0／3 句')),
        findsOneWidget,
      );
      await tapKey(tester, 'video-beat-check-b1');
      expect(
        find.descendant(of: checkCount, matching: find.text('已檢查 1／3 句')),
        findsOneWidget,
      );
      final confirm = find.byKey(const Key('video-draft-confirm'));
      expect(tester.widget<FilledButton>(confirm).onPressed, isNotNull);
      await tapKey(tester, 'video-draft-confirm');
      expect(h.path, '/videos/p1');
    });

    testWidgets('素材清單：必拍、拍攝說明', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: draftRepo(draftOf()),
      );
      await tester.scrollUntilVisible(find.text('說明白玫瑰的位置'), 200);
      expect(find.text('必拍'), findsOneWidget);
      expect(find.text('拍攝說明：整張牌，正面朝上'), findsOneWidget);
    });

    testWidgets('還沒有草稿：提示先選頁', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: FakeVideoStudioRepository(projects: [sampleVideoProject()]),
      );
      expect(find.text('還沒有草稿'), findsOneWidget);
      await tapText(tester, '選頁與編輯文字');
      expect(h.path, '/videos/p1/pages');
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
  });
}
