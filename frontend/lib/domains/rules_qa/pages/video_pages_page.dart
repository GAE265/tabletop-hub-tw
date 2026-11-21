import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../data/video_studio_models.dart';
import '../state/video_pages_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/video_studio_widgets.dart';

/// 選頁與編輯文字（`/videos/:id/pages`）。[focusPage]：從草稿的出處頁進來時，那一頁的編輯框
/// 取得焦點（修正 OCR 錯字的路徑）。
class VideoPagesPage extends ConsumerStatefulWidget {
  const VideoPagesPage({required this.projectId, this.focusPage, super.key});

  final String projectId;
  final int? focusPage;

  @override
  ConsumerState<VideoPagesPage> createState() => _VideoPagesPageState();
}

class _VideoPagesPageState extends ConsumerState<VideoPagesPage> {
  /// 點頁碼時加到「參考」還是「本章」。
  bool _reference = false;

  VideoPagesNotifier get _notifier =>
      ref.read(videoPagesProvider(widget.projectId).notifier);

  @override
  void initState() {
    super.initState();
    // 有還沒儲存的修改就保留，不重新讀
    Future.microtask(() {
      if (!mounted) return;
      if (!ref.read(videoPagesProvider(widget.projectId)).dirty) {
        _notifier.load();
      }
    });
  }

  Future<void> _togglePage(VideoPages pages, int page) async {
    final chapter = [...pages.chapterPages];
    final reference = [...pages.referencePages];
    if (chapter.contains(page)) {
      chapter.remove(page);
    } else if (reference.contains(page)) {
      reference.remove(page);
    } else if (_reference) {
      reference.add(page);
    } else {
      chapter.add(page);
    }
    await _notifier.selectPages(chapter: chapter, reference: reference);
  }

  Future<void> _next() async {
    final dirty = ref.read(videoPagesProvider(widget.projectId)).dirty;
    if (dirty && !await _notifier.save()) return;
    if (mounted) context.go('/videos/${widget.projectId}/pages/review');
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(videoPagesProvider(widget.projectId));
    final pages = state.pages;
    final text = Theme.of(context).textTheme;
    final busy = state.loading || state.saving;
    return Scaffold(
      key: const Key('video-pages-page'),
      appBar: AppBar(title: const Text('選頁與編輯文字')),
      bottomNavigationBar: VideoBottomActions(
        children: [
          OutlinedButton(
            key: const Key('video-pages-save'),
            onPressed: state.dirty && !busy ? _notifier.save : null,
            child: Text(state.saving ? '儲存中…' : '儲存'),
          ),
          FilledButton(
            key: const Key('video-pages-next'),
            onPressed: pages != null && pages.chapterPages.isNotEmpty && !busy
                ? _next
                : null,
            child: const Text('下一步：確認差異'),
          ),
        ],
      ),
      body: VideoPageBody(
        child: pages == null && state.loading
            ? const Center(child: CircularProgressIndicator())
            : SingleChildScrollView(
                padding: const EdgeInsets.all(AppSpacing.medium),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (state.error != null) ...[
                      NoticeBanner(text: state.error!, isError: true),
                      const SizedBox(height: AppSpacing.medium),
                    ],
                    if (pages != null) ...[
                      Text('點頁碼加入或移除', style: text.titleSmall),
                      const SizedBox(height: AppSpacing.small),
                      SegmentedButton<bool>(
                        segments: const [
                          ButtonSegment(value: false, label: Text('本章')),
                          ButtonSegment(value: true, label: Text('參考')),
                        ],
                        selected: {_reference},
                        onSelectionChanged: (value) =>
                            setState(() => _reference = value.single),
                      ),
                      const SizedBox(height: AppSpacing.small),
                      Wrap(
                        spacing: AppSpacing.small,
                        runSpacing: AppSpacing.small,
                        children: [
                          for (final page in pages.availablePages)
                            FilterChip(
                              key: Key('video-page-chip-$page'),
                              label: Text(
                                pages.referencePages.contains(page)
                                    ? 'p.$page（參考）'
                                    : 'p.$page',
                              ),
                              selected:
                                  pages.chapterPages.contains(page) ||
                                  pages.referencePages.contains(page),
                              onSelected: busy
                                  ? null
                                  : (_) => _togglePage(pages, page),
                            ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.large),
                      if (pages.pages.isEmpty)
                        Text('還沒有選頁', style: text.bodyLarge),
                      for (final page in pages.pages)
                        Padding(
                          padding: const EdgeInsets.only(
                            bottom: AppSpacing.medium,
                          ),
                          child: _PageEditor(
                            key: ValueKey(page.page),
                            page: page,
                            text: state.texts[page.page] ?? page.text,
                            autofocus: page.page == widget.focusPage,
                            onChanged: (value) =>
                                _notifier.editText(page.page, value),
                          ),
                        ),
                    ],
                  ],
                ),
              ),
      ),
    );
  }
}

class _PageEditor extends StatefulWidget {
  const _PageEditor({
    required this.page,
    required this.text,
    required this.autofocus,
    required this.onChanged,
    super.key,
  });

  final VideoPageText page;
  final String text;
  final bool autofocus;
  final ValueChanged<String> onChanged;

  @override
  State<_PageEditor> createState() => _PageEditorState();
}

class _PageEditorState extends State<_PageEditor> {
  late final _controller = TextEditingController(text: widget.text);
  bool _showOriginal = false;

  @override
  void initState() {
    super.initState();
    if (widget.autofocus) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) Scrollable.ensureVisible(context);
      });
    }
  }

  @override
  void didUpdateWidget(_PageEditor oldWidget) {
    super.didUpdateWidget(oldWidget);
    // 儲存後後端回傳的文字和畫面上不同（例如重新讀取）才換掉
    if (widget.text != _controller.text && widget.text != oldWidget.text) {
      _controller.text = widget.text;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final page = widget.page;
    final text = Theme.of(context).textTheme;
    final original = page.original;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    page.role == 'reference'
                        ? '第 ${page.page} 頁（參考）'
                        : '第 ${page.page} 頁（本章）',
                    style: text.titleMedium,
                  ),
                ),
                if (original != null)
                  TextButton(
                    onPressed: () =>
                        setState(() => _showOriginal = !_showOriginal),
                    child: Text(_showOriginal ? '收起原文' : '看原文'),
                  ),
              ],
            ),
            if (page.originalChanged) ...[
              const SizedBox(height: AppSpacing.small),
              const NoticeBanner(text: '這一頁的原文已重新上傳，請再確認一次'),
            ],
            const SizedBox(height: AppSpacing.small),
            TextField(
              key: Key('video-page-editor-${page.page}'),
              controller: _controller,
              autofocus: widget.autofocus,
              minLines: 4,
              maxLines: null,
              decoration: const InputDecoration(hintText: '刪掉不屬於本章的內容，修正錯字'),
              onChanged: widget.onChanged,
            ),
            if (_showOriginal && original != null) ...[
              const SizedBox(height: AppSpacing.small),
              Text('原文', style: text.labelLarge),
              const SizedBox(height: AppSpacing.xSmall),
              SelectableText(original, style: text.bodyMedium),
            ],
          ],
        ),
      ),
    );
  }
}
