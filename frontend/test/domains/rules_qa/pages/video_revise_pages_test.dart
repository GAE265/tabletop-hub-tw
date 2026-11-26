// 用一句話修改的手機頁（add-rules-video-mobile MR 12）：草稿頁的入口、寫修改要求與選段、
// AI 在算、提案（前後對照、沒被要求的修改、超過 2 段的提醒）、替代做法、候選段、失敗、
// 套用後的提示與前往產生影片；工作卡片不顯示已結束的修改工作；手機寬 320 不超出。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';

import '../../../support/fakes.dart';
import '../video_revision_support.dart';
import '../video_swap_support.dart';
import 'video_pages_support.dart';

List<String> takeErrors(WidgetTester tester) {
  final errors = <String>[];
  for (var e = tester.takeException(); e != null; e = tester.takeException()) {
    errors.add('$e'.split('\n').first);
  }
  return errors;
}

Future<void> typeRequest(WidgetTester tester, String text) async {
  await tester.enterText(find.byKey(const Key('video-revise-request')), text);
  await tester.pumpAndSettle();
}

/// 打開修改頁、寫下修改要求並送出，等 AI 算完（假的 repository 依序回 [results]）。
Future<Harness> submitRevision(
  WidgetTester tester,
  List<VideoRevision> results, {
  String request = '情況一的金框改成紅框',
  FakeVideoStudioRepository? repo,
  Size size = const Size(400, 900),
}) async {
  final fake = (repo ?? swapRepo())..revisionSequence = results;
  final harness = await pumpVideo(
    tester,
    location: '/videos/p1/revise',
    repo: fake,
    size: size,
  );
  await typeRequest(tester, request);
  await tapKey(tester, 'video-revise-submit');
  return harness;
}

/// AI 一直在算的測試：進度條會一直動，所以按下送出後只 pump，不等畫面靜止。
Future<void> submitWhileRunning(WidgetTester tester) async {
  final repo = swapRepo()..revisionSequence = [runningRevision()];
  await pumpVideo(
    tester,
    location: '/videos/p1/revise',
    repo: repo,
    pollInterval: const Duration(seconds: 1),
  );
  await typeRequest(tester, '情況一的金框改成紅框');
  await tester.tap(find.byKey(const Key('video-revise-submit')));
  await tester.pump();
  await tester.pump(const Duration(seconds: 1));
  await tester.pump();
}

void main() {
  group('草稿頁的入口', () {
    testWidgets('有「用一句話修改」，按了到修改頁', (tester) async {
      final harness = await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: swapRepo(),
      );
      expect(find.byKey(const Key('video-draft-revise-card')), findsOneWidget);
      await tapKey(tester, 'video-draft-revise');
      expect(harness.path, '/videos/p1/revise');
      expect(find.byKey(const Key('video-revise-form')), findsOneWidget);
    });

    testWidgets('已結束的修改工作不顯示在工作卡片（不會出現重試）', (tester) async {
      final repo = swapRepo()
        ..latestJobs['p1'] = sampleVideoJob(
          projectId: 'p1',
          kind: 'revise',
          status: VideoJobStatus.failed,
        );
      await pumpVideo(tester, location: '/videos/p1/draft', repo: repo);
      expect(find.byKey(const Key('video-job-failed')), findsNothing);
    });
  });

  group('寫修改要求', () {
    testWidgets('沒寫修改要求時按不下去', (tester) async {
      final repo = swapRepo();
      await pumpVideo(tester, location: '/videos/p1/revise', repo: repo);
      final submit = find.byKey(const Key('video-revise-submit'));
      expect(tester.widget<FilledButton>(submit).onPressed, isNull);
      await typeRequest(tester, '   ');
      await tester.tap(find.byKey(const Key('video-revise-submit')));
      await tester.pumpAndSettle();
      expect(repo.createdRevisions, isEmpty);
    });

    testWidgets('可以指定只改哪一段（第 N 段加上第一句旁白）', (tester) async {
      final repo = swapRepo()..revisionSequence = [proposalRevision()];
      await pumpVideo(tester, location: '/videos/p1/revise', repo: repo);
      await typeRequest(tester, '字幕講短一點');
      await tapKey(tester, 'video-revise-segment');
      expect(find.text('第 2 段：再看一次紅牌。').last, findsOneWidget);
      await tester.tap(find.text('第 2 段：再看一次紅牌。').last);
      await tester.pumpAndSettle();
      await tapKey(tester, 'video-revise-submit');
      final input = repo.createdRevisions.single.$2;
      expect((input.request, input.segmentKey), ('字幕講短一點', 's2'));
    });

    testWidgets('送出失敗：顯示後端的說明，留在表單', (tester) async {
      final repo = swapRepo()
        ..createRevisionError = const ApiException(
          statusCode: 409,
          code: 'RULES_VIDEO_JOB_RUNNING',
          message: '這個專案已經有進行中的工作，請等它完成',
        );
      await submitRevision(tester, [], repo: repo);
      expect(find.text('這個專案已經有進行中的工作，請等它完成'), findsOneWidget);
      expect(find.byKey(const Key('video-revise-form')), findsOneWidget);
    });
  });

  group('AI 的結果', () {
    testWidgets('還在算：顯示進度訊息', (tester) async {
      await submitWhileRunning(tester);
      expect(find.byKey(const Key('video-revise-thinking')), findsOneWidget);
      expect(find.text('AI 修改中'), findsOneWidget);
      expect(find.byKey(const Key('video-revise-apply')), findsNothing);
      await stopPolling(tester);
    });

    testWidgets('提案：每段的說明、改了什麼、前後對照、沒被要求的修改、沒做涵蓋檢查', (tester) async {
      await submitRevision(tester, [proposalRevision()]);
      expect(find.text('「情況一的金框改成紅框」'), findsOneWidget);
      expect(find.text('第 1 段'), findsOneWidget);
      expect(find.text('h1 的框線由金色改為紅色'), findsOneWidget);
      expect(find.text('改了：框線'), findsOneWidget);
      expect(find.text('改了：旁白、字幕'), findsOneWidget);
      expect(
        find.byKey(const Key('video-revise-unrequested-s2')),
        findsOneWidget,
      );
      expect(find.text('沒有要求改，但也改了：旁白，請確認'), findsOneWidget);
      expect(
        find.byKey(const Key('video-revise-unrequested-s1')),
        findsNothing,
      );
      expect(find.text('旁白：再看一次紅牌。'), findsOneWidget);
      expect(find.text('旁白：再看紅牌。'), findsOneWidget);
      expect(find.text('字幕：看紅牌'), findsOneWidget);
      expect(find.text('這次沒有做規則涵蓋檢查'), findsOneWidget);
      expect(find.byKey(const Key('video-revise-many')), findsNothing);
    });

    testWidgets('一次改超過 2 段：提醒逐段確認', (tester) async {
      await submitRevision(tester, [proposalRevision(many: true)]);
      expect(find.byKey(const Key('video-revise-many')), findsOneWidget);
    });

    testWidgets('套用提案：顯示改了哪幾段、可以前往產生影片', (tester) async {
      final harness = await submitRevision(tester, [proposalRevision()]);
      await tapKey(tester, 'video-revise-apply');
      final input = harness.repo.appliedRevisions.single.$3;
      expect((input.alternative, input.videoVersion), (null, 3));
      expect(find.byKey(const Key('video-revise-applied')), findsOneWidget);
      expect(find.text('已套用到第 1 段、第 2 段。影片要重新產生才會更新'), findsOneWidget);
      await tapKey(tester, 'video-revise-go-render');
      expect(harness.path, '/videos/p1/render');
    });

    testWidgets('套用失敗：顯示說明、提案留著', (tester) async {
      final repo = swapRepo()
        ..applyRevisionError = const ApiException(
          statusCode: 409,
          code: 'RULES_VIDEO_REVISION_STALE',
          message: '算出提案之後草稿被改過（例如換了素材），請重新送出修改',
        );
      await submitRevision(tester, [proposalRevision()], repo: repo);
      await tapKey(tester, 'video-revise-apply');
      expect(find.byKey(const Key('video-revise-error')), findsOneWidget);
      expect(find.byKey(const Key('video-revise-apply')), findsOneWidget);
      expect(find.byKey(const Key('video-revise-applied')), findsNothing);
    });

    testWidgets('不要，重新提：回到表單、不套用', (tester) async {
      final harness = await submitRevision(tester, [proposalRevision()]);
      await tapKey(tester, 'video-revise-restart');
      expect(find.byKey(const Key('video-revise-form')), findsOneWidget);
      expect(harness.repo.appliedRevisions, isEmpty);
    });

    testWidgets('版型做不到：原因與替代做法，選一個套用', (tester) async {
      final harness = await submitRevision(tester, [unsupportedRevision()]);
      expect(find.text('目前的版型做不到'), findsOneWidget);
      expect(find.text('沒有旋轉動作'), findsOneWidget);
      expect(find.text('做法 1：改成淡入'), findsOneWidget);
      expect(find.text('做法 2：改成彈出'), findsOneWidget);
      expect(find.text('改了：動作'), findsOneWidget);
      expect(find.byKey(const Key('video-revise-apply')), findsNothing);
      await tapKey(tester, 'video-revise-apply-alt-2');
      expect(harness.repo.appliedRevisions.single.$3.alternative, 2);
      expect(find.byKey(const Key('video-revise-applied')), findsOneWidget);
    });

    testWidgets('不確定改哪一段：列出候選段，選了就只改那一段重新送出', (tester) async {
      final harness = await submitRevision(tester, [
        ambiguousRevision(),
      ], request: '移除藍牌講慢一點');
      expect(find.text('不確定要改哪一段'), findsOneWidget);
      expect(find.text('第 2 段：情況二移除藍牌'), findsOneWidget);
      harness.repo.revisionSequence = [proposalRevision()];
      await tapKey(tester, 'video-revise-candidate-s2');
      final second = harness.repo.createdRevisions.last.$2;
      expect((second.request, second.segmentKey), ('移除藍牌講慢一點', 's2'));
      expect(find.byKey(const Key('video-revise-apply')), findsOneWidget);
    });

    testWidgets('AI 沒算成：顯示原因，可以重新提', (tester) async {
      await submitRevision(tester, [failedRevision()]);
      expect(find.byKey(const Key('video-revise-failed')), findsOneWidget);
      expect(find.textContaining('換個說法'), findsOneWidget);
      await tapKey(tester, 'video-revise-restart');
      expect(find.byKey(const Key('video-revise-form')), findsOneWidget);
    });
  });

  group('手機寬 320：不超出', () {
    for (final (name, result) in [
      ('表單', null),
      ('提案', proposalRevision(many: true)),
      ('替代做法', unsupportedRevision()),
      ('候選段', ambiguousRevision()),
    ]) {
      testWidgets(name, (tester) async {
        if (result == null) {
          await pumpVideo(
            tester,
            location: '/videos/p1/revise',
            repo: swapRepo(),
            size: const Size(320, 900),
          );
        } else {
          await submitRevision(tester, [result], size: const Size(320, 900));
        }
        expect(takeErrors(tester), isEmpty);
      });
    }

    testWidgets('套用後', (tester) async {
      await submitRevision(tester, [
        proposalRevision(),
      ], size: const Size(320, 900));
      await tapKey(tester, 'video-revise-apply');
      expect(takeErrors(tester), isEmpty);
    });
  });
}
