import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/widgets/pill_badge.dart';
import '../state/video_job_state.dart';
import '../state/video_pages_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/video_studio_widgets.dart';

/// 確認差異（`/videos/:id/pages/review`）：每一處「刪掉」「改過」同時顯示原文與編輯後，
/// 確認後產生草稿。
class VideoPagesReviewPage extends ConsumerStatefulWidget {
  const VideoPagesReviewPage({required this.projectId, super.key});

  final String projectId;

  @override
  ConsumerState<VideoPagesReviewPage> createState() =>
      _VideoPagesReviewPageState();
}

class _VideoPagesReviewPageState extends ConsumerState<VideoPagesReviewPage> {
  String? _error;
  bool _starting = false;

  String get _id => widget.projectId;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (!mounted) return;
      if (!ref.read(videoPagesProvider(_id)).dirty) {
        ref.read(videoPagesProvider(_id).notifier).load();
      }
    });
  }

  Future<void> _startDraft() async {
    setState(() {
      _starting = true;
      _error = null;
    });
    final notifier = ref.read(videoJobProvider(_id).notifier);
    await notifier.startDraft();
    if (!mounted) return;
    final error = ref.read(videoJobProvider(_id)).error;
    if (error == null) {
      context.go('/videos/$_id');
    } else {
      setState(() {
        _starting = false;
        _error = error;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(videoPagesProvider(_id));
    final pages = state.pages;
    final text = Theme.of(context).textTheme;
    final differences = state.differences;
    return Scaffold(
      key: const Key('video-pages-review-page'),
      appBar: AppBar(title: const Text('確認差異')),
      bottomNavigationBar: VideoBottomActions(
        children: [
          OutlinedButton(
            onPressed: () => context.go('/videos/$_id/pages'),
            child: const Text('回去修改'),
          ),
          FilledButton(
            key: const Key('video-start-draft'),
            onPressed: pages == null || _starting ? null : _startDraft,
            child: const Text('產生草稿'),
          ),
        ],
      ),
      body: VideoPageBody(
        child: pages == null
            ? (state.error != null
                  ? Padding(
                      padding: const EdgeInsets.all(AppSpacing.medium),
                      child: NoticeBanner(text: state.error!, isError: true),
                    )
                  : const Center(child: CircularProgressIndicator()))
            : ListView(
                padding: const EdgeInsets.all(AppSpacing.medium),
                children: [
                  if (_error != null) ...[
                    NoticeBanner(text: _error!, isError: true),
                    const SizedBox(height: AppSpacing.medium),
                  ],
                  for (final page in pages.pages)
                    if (page.originalChanged) ...[
                      NoticeBanner(text: '第 ${page.page} 頁的原文已改變，請再確認一次'),
                      const SizedBox(height: AppSpacing.medium),
                    ],
                  Text(
                    differences.isEmpty
                        ? '沒有修改，草稿會依原文產生'
                        : '共 ${differences.length} 處修改，確認原文與編輯後都正確',
                    style: text.bodyLarge,
                  ),
                  const SizedBox(height: AppSpacing.medium),
                  for (final difference in differences)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.medium),
                      child: _DifferenceCard(difference),
                    ),
                ],
              ),
      ),
    );
  }
}

class _DifferenceCard extends StatelessWidget {
  const _DifferenceCard(this.difference);

  final PageDifference difference;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final scheme = Theme.of(context).colorScheme;
    final muted = text.labelMedium!.copyWith(color: scheme.onSurfaceVariant);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                PillBadge(
                  label: difference.removed ? '刪掉' : '改過',
                  tone: difference.removed
                      ? PillTone.accent
                      : PillTone.duration,
                ),
                const SizedBox(width: AppSpacing.small),
                Text('第 ${difference.page} 頁', style: text.titleSmall),
              ],
            ),
            const SizedBox(height: AppSpacing.small),
            Text('原文', style: muted),
            Text(difference.original, style: text.bodyMedium),
            const SizedBox(height: AppSpacing.small),
            Text('編輯後', style: muted),
            Text(
              difference.edited ?? '（整段刪掉）',
              style: difference.edited == null
                  ? text.bodyMedium!.copyWith(color: scheme.onSurfaceVariant)
                  : text.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}
