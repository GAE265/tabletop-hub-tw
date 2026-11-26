import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../core/api/api_exception.dart';
import '../data/video_studio_models.dart';
import '../state/video_draft_state.dart';
import '../state/video_revision_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/video_studio_widgets.dart';

/// 用一句話修改（`/videos/:id/revise`，add-rules-video-mobile MR 12）。
/// 寫下要怎麼改（可以指定只改哪一段）→ AI 算出提案 → 看過再套用。
/// 版型做不到時列出替代做法；不確定改哪一段時列出候選段，選一段後重新送出。
class VideoRevisePage extends ConsumerWidget {
  const VideoRevisePage({required this.projectId, super.key});

  final String projectId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(videoDraftProvider(projectId));
    return VideoScaffold(
      key: const Key('video-revise-page'),
      title: '用一句話修改',
      body: VideoPageBody(
        child: draft.when(
          skipLoadingOnRefresh: true,
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.large),
              child: Text(
                error is ApiException ? error.message : '發生未知錯誤',
                textAlign: TextAlign.center,
              ),
            ),
          ),
          data: (value) => value == null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpacing.large),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('還沒有草稿，先產生草稿才能修改'),
                        const SizedBox(height: AppSpacing.medium),
                        ThickButton(
                          style: ThickStyle.primary,
                          label: '回草稿',
                          onPressed: () =>
                              context.go('/videos/$projectId/draft'),
                        ),
                      ],
                    ),
                  ),
                )
              : _Content(projectId: projectId, draft: value),
        ),
      ),
    );
  }
}

class _Content extends ConsumerWidget {
  const _Content({required this.projectId, required this.draft});

  final String projectId;
  final VideoDraft draft;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(videoRevisionProvider(projectId));
    final revision = state.revision;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.medium),
      children: [
        if (revision == null)
          _RequestForm(projectId: projectId, draft: draft)
        else if (revision.applied)
          _Applied(projectId: projectId, revision: revision)
        else
          _Result(projectId: projectId, draft: draft, state: state),
        if (state.error case final error?) ...[
          const SizedBox(height: AppSpacing.medium),
          NoticeBanner(
            key: const Key('video-revise-error'),
            text: error,
            isError: true,
          ),
        ],
      ],
    );
  }
}

/// 修改要求與選段（不指定時由 AI 判斷要改哪幾段）。
class _RequestForm extends ConsumerStatefulWidget {
  const _RequestForm({required this.projectId, required this.draft});

  final String projectId;
  final VideoDraft draft;

  @override
  ConsumerState<_RequestForm> createState() => _RequestFormState();
}

class _RequestFormState extends ConsumerState<_RequestForm> {
  final _request = TextEditingController();
  String? _segment;

  @override
  void dispose() {
    _request.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    await ref
        .read(videoRevisionProvider(widget.projectId).notifier)
        .submit(
          draft: widget.draft,
          request: _request.text,
          segmentKey: _segment,
        );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(videoRevisionProvider(widget.projectId));
    final text = Theme.of(context).textTheme;
    final muted = text.bodySmall!.copyWith(
      color: Theme.of(context).colorScheme.onSurfaceVariant,
    );
    final ready = _request.text.trim().isNotEmpty && !state.busy;
    final segments = widget.draft.segments;
    return ThickCard(
      key: const Key('video-revise-form'),
      child: Padding(
        padding: videoCardInset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('要怎麼改？', style: text.titleMedium),
            Text('用一句話說要改什麼，AI 會先算出提案，你看過再決定要不要套用', style: muted),
            const SizedBox(height: AppSpacing.small),
            TextField(
              key: const Key('video-revise-request'),
              controller: _request,
              maxLength: revisionRequestMaxChars,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(hintText: '例如：情況二的紅框改成金框'),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: AppSpacing.small),
            DropdownButtonFormField<String?>(
              key: const Key('video-revise-segment'),
              initialValue: _segment,
              isExpanded: true,
              decoration: const InputDecoration(labelText: '要改哪一段（選填）'),
              items: [
                const DropdownMenuItem<String?>(
                  value: null,
                  child: Text('不指定（由 AI 判斷）'),
                ),
                for (final (i, segment) in segments.indexed)
                  DropdownMenuItem<String?>(
                    value: segment.segmentKey,
                    child: Text(
                      revisionSegmentOption(widget.draft, i),
                      key: Key('video-revise-segment-${segment.segmentKey}'),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: (value) => setState(() => _segment = value),
            ),
            const SizedBox(height: AppSpacing.medium),
            ThickButton(
              buttonKey: const Key('video-revise-submit'),
              style: ThickStyle.primary,
              expand: true,
              icon: Icons.auto_awesome,
              label: state.busy ? '送出中…' : '請 AI 算出提案',
              onPressed: ready ? _submit : null,
            ),
          ],
        ),
      ),
    );
  }
}

/// AI 在算、算完（提案、替代做法、候選段）或失敗。
class _Result extends ConsumerWidget {
  const _Result({
    required this.projectId,
    required this.draft,
    required this.state,
  });

  final String projectId;
  final VideoDraft draft;
  final VideoRevisionState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final revision = state.revision!;
    final notifier = ref.read(videoRevisionProvider(projectId).notifier);
    final text = Theme.of(context).textTheme;
    final muted = text.bodySmall!.copyWith(
      color: Theme.of(context).colorScheme.onSurfaceVariant,
    );
    final busy = state.busy;

    Widget restart(String label) => ThickButton(
      buttonKey: const Key('video-revise-restart'),
      style: ThickStyle.light,
      expand: true,
      label: label,
      onPressed: busy ? null : notifier.reset,
    );

    final request = Text(
      '「${revision.request}」',
      key: const Key('video-revise-request-text'),
      style: text.bodyLarge,
    );
    final coverage = revision.coverageMessage == null
        ? const SizedBox.shrink()
        : Text(
            revision.coverageMessage!,
            key: const Key('video-revise-coverage'),
            style: muted,
          );

    final children = <Widget>[
      request,
      const SizedBox(height: AppSpacing.small),
    ];
    if (revision.active) {
      children.addAll([
        Text(
          revision.message ?? 'AI 正在算',
          key: const Key('video-revise-thinking'),
          style: text.titleMedium,
        ),
        const SizedBox(height: AppSpacing.small),
        const LinearProgressIndicator(),
        const SizedBox(height: AppSpacing.small),
        Text('大約要半分鐘到一分鐘；可以離開這頁，完成後回來看', style: muted),
      ]);
    } else if (revision.status == VideoJobStatus.failed) {
      children.addAll([
        NoticeBanner(
          key: const Key('video-revise-failed'),
          text: revision.error ?? '這次修改沒有成功，請重新送出',
          isError: true,
        ),
        const SizedBox(height: AppSpacing.medium),
        restart('重新提修改'),
      ]);
    } else if (revision.outcome == 'proposal') {
      children.addAll([
        Text('AI 的提案', style: text.titleMedium),
        if (revision.manySegments) ...[
          const SizedBox(height: AppSpacing.small),
          NoticeBanner(
            key: const Key('video-revise-many'),
            text: '這次會改 ${revision.segments.length} 段，請逐段確認',
          ),
        ],
        for (final segment in revision.segments)
          _SegmentChange(segment: segment),
        const SizedBox(height: AppSpacing.small),
        coverage,
        const SizedBox(height: AppSpacing.medium),
        ThickButton(
          buttonKey: const Key('video-revise-apply'),
          style: ThickStyle.primary,
          expand: true,
          icon: Icons.check,
          label: busy ? '套用中…' : '套用',
          onPressed: busy ? null : () => notifier.apply(draft: draft),
        ),
        const SizedBox(height: AppSpacing.small),
        restart('不要，重新提'),
      ]);
    } else if (revision.outcome == 'unsupported') {
      children.addAll([
        Text('目前的版型做不到', style: text.titleMedium),
        if (revision.reason case final reason? when reason.isNotEmpty)
          Text(reason, key: const Key('video-revise-reason'), style: muted),
        const SizedBox(height: AppSpacing.small),
        Text('可以改用下面的做法：', style: text.bodyMedium),
        for (final alt in revision.alternatives)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.medium),
            child: ThickCard(
              key: Key('video-revise-alt-${alt.number}'),
              child: Padding(
                padding: videoCardInset,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      '做法 ${alt.number}：${alt.title}',
                      style: text.bodyLarge!.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(alt.description, style: muted),
                    for (final segment in alt.segments)
                      _SegmentChange(segment: segment),
                    const SizedBox(height: AppSpacing.small),
                    ThickButton(
                      buttonKey: Key('video-revise-apply-alt-${alt.number}'),
                      style: ThickStyle.primary,
                      expand: true,
                      label: '用這個做法',
                      onPressed: busy
                          ? null
                          : () => notifier.apply(
                              draft: draft,
                              alternative: alt.number,
                            ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        const SizedBox(height: AppSpacing.small),
        coverage,
        const SizedBox(height: AppSpacing.medium),
        restart('都不要，重新提'),
      ]);
    } else if (revision.outcome == 'ambiguous') {
      children.addAll([
        Text('不確定要改哪一段', style: text.titleMedium),
        if (revision.reason case final reason? when reason.isNotEmpty)
          Text(reason, key: const Key('video-revise-reason'), style: muted),
        const SizedBox(height: AppSpacing.small),
        Text('請選一段，AI 會只改這一段：', style: text.bodyMedium),
        for (final candidate in revision.candidates)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.small),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    '第 ${candidate.segmentNumber} 段：${candidate.reason}',
                  ),
                ),
                TextButton(
                  key: Key('video-revise-candidate-${candidate.segmentKey}'),
                  onPressed: busy
                      ? null
                      : () => notifier.chooseSegment(
                          draft: draft,
                          candidate: candidate,
                        ),
                  child: Text('改第 ${candidate.segmentNumber} 段'),
                ),
              ],
            ),
          ),
        const SizedBox(height: AppSpacing.medium),
        restart('重新提修改'),
      ]);
    }
    return ThickCard(
      key: const Key('video-revise-result'),
      child: Padding(
        padding: videoCardInset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: children,
        ),
      ),
    );
  }
}

/// 提案裡的一段：第 N 段、AI 的說明、改了什麼、沒被要求卻改了的地方、旁白字幕的前後對照。
class _SegmentChange extends StatelessWidget {
  const _SegmentChange({required this.segment});

  final RevisionSegment segment;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    final muted = text.bodySmall!.copyWith(color: scheme.onSurfaceVariant);
    final key = segment.segmentKey;
    return Padding(
      key: Key('video-revise-segment-change-$key'),
      padding: const EdgeInsets.only(top: AppSpacing.medium),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '第 ${segment.segmentNumber} 段',
            style: text.bodyMedium!.copyWith(fontWeight: FontWeight.w600),
          ),
          if (segment.summary.isNotEmpty) Text(segment.summary),
          if (segment.changed.isNotEmpty)
            Text(
              '改了：${revisionCategories(segment.changed)}',
              key: Key('video-revise-changed-$key'),
              style: muted,
            ),
          if (segment.unrequested.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xSmall),
            NoticeBanner(
              key: Key('video-revise-unrequested-$key'),
              text: '沒有要求改，但也改了：${revisionCategories(segment.unrequested)}，請確認',
            ),
          ],
          for (final beat in segment.beats) _BeatChange(beat: beat),
        ],
      ),
    );
  }
}

class _BeatChange extends StatelessWidget {
  const _BeatChange({required this.beat});

  final RevisionBeat beat;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final muted = text.bodySmall!.copyWith(
      color: Theme.of(context).colorScheme.onSurfaceVariant,
    );
    List<Widget> lines(String label, RevisionText? value) => [
      Text(label, style: muted),
      if (value == null)
        Text('（沒有這一句）', style: muted)
      else ...[
        Text('旁白：${value.narration}'),
        if (value.subtitle != value.narration) Text('字幕：${value.subtitle}'),
      ],
    ];
    return Padding(
      key: Key('video-revise-beat-${beat.beatKey}'),
      padding: const EdgeInsets.only(top: AppSpacing.small),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ...lines('改之前', beat.before),
          const SizedBox(height: AppSpacing.xSmall),
          ...lines('改之後', beat.after),
        ],
      ),
    );
  }
}

/// 套用完成：改了哪幾段、影片要重新產生；可以去產生影片、回草稿或再提一個修改。
class _Applied extends ConsumerWidget {
  const _Applied({required this.projectId, required this.revision});

  final String projectId;
  final VideoRevision revision;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return ThickCard(
      key: const Key('video-revise-applied'),
      child: Padding(
        padding: videoCardInset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('「${revision.request}」', style: text.bodyLarge),
            const SizedBox(height: AppSpacing.small),
            NoticeBanner(
              key: const Key('video-revise-applied-notice'),
              text: revisionAppliedNotice(revision),
            ),
            if (revision.coverageMessage case final message?) ...[
              const SizedBox(height: AppSpacing.small),
              Text(message, style: text.bodySmall),
            ],
            const SizedBox(height: AppSpacing.medium),
            ThickButton(
              buttonKey: const Key('video-revise-go-render'),
              style: ThickStyle.primary,
              expand: true,
              icon: Icons.movie_outlined,
              label: '前往產生影片',
              onPressed: () => context.go('/videos/$projectId/render'),
            ),
            const SizedBox(height: AppSpacing.small),
            ThickButton(
              buttonKey: const Key('video-revise-again'),
              style: ThickStyle.light,
              expand: true,
              label: '再提一個修改',
              onPressed: ref
                  .read(videoRevisionProvider(projectId).notifier)
                  .reset,
            ),
            const SizedBox(height: AppSpacing.small),
            TextButton(
              key: const Key('video-revise-back-draft'),
              onPressed: () => context.go('/videos/$projectId/draft'),
              child: const Text('回草稿'),
            ),
          ],
        ),
      ),
    );
  }
}
