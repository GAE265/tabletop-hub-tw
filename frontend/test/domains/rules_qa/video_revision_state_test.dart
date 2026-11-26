// 用一句話修改（add-rules-video-mobile MR 12）的 state 與純函式：送出修改並查到算完、
// 套用提案或替代做法、不確定改哪一段時選段重新送出、版本衝突與其他錯誤、欄位分類的說法。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_draft_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_job_state.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_revision_state.dart';

import '../../support/fakes.dart';
import 'video_revision_support.dart';
import 'video_swap_support.dart';

Future<(ProviderContainer, VideoDraft)> setUpRevision(
  FakeVideoStudioRepository repo,
) async {
  final container = ProviderContainer(
    overrides: [
      videoStudioRepositoryProvider.overrideWithValue(repo),
      videoJobPollIntervalProvider.overrideWithValue(Duration.zero),
    ],
  );
  addTearDown(container.dispose);
  final draft = (await container.read(videoDraftProvider('p1').future))!;
  final sub = container.listen(videoRevisionProvider('p1'), (_, _) {});
  addTearDown(sub.close);
  return (container, draft);
}

VideoRevisionNotifier notifierOf(ProviderContainer container) =>
    container.read(videoRevisionProvider('p1').notifier);

void main() {
  group('欄位分類與選段的說法', () {
    test('分類用店員看得懂的說法', () {
      expect(
        revisionCategories(['narration', 'subtitle', 'highlights', 'cues']),
        '旁白、字幕、框線、動作',
      );
      expect(revisionCategoryName('slots'), '素材');
    });

    test('選段：第 N 段加上第一句旁白', () {
      expect(revisionSegmentOption(swapDraft(), 0), '第 1 段：把紅牌放進甲區。');
    });

    test('套用後的提示：改了哪幾段、影片要重新產生', () {
      final applied = proposalRevision().copyWith(applied: true);
      expect(revisionAppliedNotice(applied), '已套用到第 1 段、第 2 段。影片要重新產生才會更新');
      final alt = unsupportedRevision().copyWith(
        applied: true,
        appliedAlternative: 1,
      );
      expect(revisionAppliedNotice(alt), '已套用到第 1 段。影片要重新產生才會更新');
    });
  });

  group('送出修改', () {
    test('帶草稿版本與指定段送出，查到算完為止', () async {
      final repo = swapRepo()
        ..revisionSequence = [runningRevision(), proposalRevision()];
      final (container, draft) = await setUpRevision(repo);
      final ok = await notifierOf(
        container,
      ).submit(draft: draft, request: '  情況一的金框改成紅框 ', segmentKey: 's1');
      expect(ok, isTrue);
      final input = repo.createdRevisions.single.$2;
      expect(input.request, '情況一的金框改成紅框');
      expect(input.segmentKey, 's1');
      expect(input.videoVersion, 3);
      await notifierOf(container).finished;
      final state = container.read(videoRevisionProvider('p1'));
      expect(state.revision!.outcome, 'proposal');
      expect(state.thinking, isFalse);
      expect(repo.polledRevisions, ['r1', 'r1']);
    });

    test('修改要求空白：不送出', () async {
      final repo = swapRepo();
      final (container, draft) = await setUpRevision(repo);
      expect(
        await notifierOf(container).submit(draft: draft, request: '   '),
        isFalse,
      );
      expect(repo.createdRevisions, isEmpty);
    });

    test('已有工作在跑：顯示後端的說明', () async {
      final repo = swapRepo()
        ..createRevisionError = const ApiException(
          statusCode: 409,
          code: 'RULES_VIDEO_JOB_RUNNING',
          message: '這個專案已經有進行中的工作，請等它完成',
        );
      final (container, draft) = await setUpRevision(repo);
      expect(
        await notifierOf(container).submit(draft: draft, request: '改紅框'),
        isFalse,
      );
      final state = container.read(videoRevisionProvider('p1'));
      expect(state.error, '這個專案已經有進行中的工作，請等它完成');
      expect(state.revision, isNull);
    });

    test('版本衝突：顯示說明並重新讀取草稿', () async {
      final repo = swapRepo()
        ..createRevisionError = const ApiException(
          statusCode: 409,
          code: 'RULES_VIDEO_CONFLICT',
          message: '草稿已被修改，請重新整理後再試一次',
        );
      final (container, draft) = await setUpRevision(repo);
      repo.drafts['p1'] = swapDraft(version: 9);
      await notifierOf(container).submit(draft: draft, request: '改紅框');
      expect(
        container.read(videoRevisionProvider('p1')).error,
        '草稿已被修改，請重新整理後再試一次',
      );
      final reloaded = await container.read(videoDraftProvider('p1').future);
      expect(reloaded!.videoVersion, 9);
    });

    test('AI 沒算成：結果是失敗與原因', () async {
      final repo = swapRepo()..revisionSequence = [failedRevision()];
      final (container, draft) = await setUpRevision(repo);
      await notifierOf(container).submit(draft: draft, request: '改紅框');
      await notifierOf(container).finished;
      final revision = container.read(videoRevisionProvider('p1')).revision!;
      expect(revision.status, VideoJobStatus.failed);
      expect(revision.error, contains('換個說法'));
    });
  });

  group('不確定改哪一段', () {
    test('選一段：用同一句修改要求、只改那一段重新送出', () async {
      final repo = swapRepo()
        ..revisionSequence = [ambiguousRevision()]
        ..createdRevision = ambiguousRevision().copyWith(
          status: VideoJobStatus.queued,
        );
      final (container, draft) = await setUpRevision(repo);
      await notifierOf(container).submit(draft: draft, request: '移除藍牌講慢一點');
      await notifierOf(container).finished;
      final candidate = container
          .read(videoRevisionProvider('p1'))
          .revision!
          .candidates
          .last;
      repo.revisionSequence = [proposalRevision()];
      await notifierOf(
        container,
      ).chooseSegment(draft: draft, candidate: candidate);
      final second = repo.createdRevisions.last.$2;
      expect(second.request, '移除藍牌講慢一點');
      expect(second.segmentKey, 's2');
    });
  });

  group('套用', () {
    Future<(ProviderContainer, VideoDraft, FakeVideoStudioRepository)> ready(
      VideoRevision result,
    ) async {
      final repo = swapRepo()..revisionSequence = [result];
      final (container, draft) = await setUpRevision(repo);
      await notifierOf(container).submit(draft: draft, request: '改紅框');
      await notifierOf(container).finished;
      return (container, draft, repo);
    }

    test('套用提案：帶草稿版本、不帶替代做法；之後重新讀取草稿', () async {
      final (container, draft, repo) = await ready(proposalRevision());
      expect(await notifierOf(container).apply(draft: draft), isTrue);
      final (_, revisionId, input) = repo.appliedRevisions.single;
      expect(revisionId, 'r1');
      expect(input.alternative, isNull);
      expect(input.videoVersion, 3);
      expect(input.toJson()['status'], 'applied');
      final state = container.read(videoRevisionProvider('p1'));
      expect(state.revision!.applied, isTrue);
      final reloaded = await container.read(videoDraftProvider('p1').future);
      expect(reloaded!.videoVersion, 4);
    });

    test('套用替代做法：帶編號', () async {
      final (container, draft, repo) = await ready(unsupportedRevision());
      await notifierOf(container).apply(draft: draft, alternative: 1);
      expect(repo.appliedRevisions.single.$3.alternative, 1);
      expect(
        container
            .read(videoRevisionProvider('p1'))
            .revision!
            .appliedAlternative,
        1,
      );
    });

    test('提案之後草稿被改過：顯示說明、保留提案、重新讀取草稿', () async {
      final (container, draft, repo) = await ready(proposalRevision());
      repo
        ..applyRevisionError = const ApiException(
          statusCode: 409,
          code: 'RULES_VIDEO_REVISION_STALE',
          message: '算出提案之後草稿被改過（例如換了素材），請重新送出修改',
        )
        ..drafts['p1'] = swapDraft(version: 7);
      expect(await notifierOf(container).apply(draft: draft), isFalse);
      final state = container.read(videoRevisionProvider('p1'));
      expect(state.error, contains('請重新送出修改'));
      expect(state.revision!.outcome, 'proposal');
      expect(state.revision!.applied, isFalse);
      final reloaded = await container.read(videoDraftProvider('p1').future);
      expect(reloaded!.videoVersion, 7);
    });

    test('再提一個修改：清掉上一次的結果', () async {
      final (container, draft, _) = await ready(proposalRevision());
      await notifierOf(container).apply(draft: draft);
      notifierOf(container).reset();
      expect(container.read(videoRevisionProvider('p1')).revision, isNull);
    });
  });
}
