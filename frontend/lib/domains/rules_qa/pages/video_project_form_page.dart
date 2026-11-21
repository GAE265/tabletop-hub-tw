import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../state/video_projects_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/video_studio_widgets.dart';

/// 建立影片專案（`/videos/new`）：選遊戲、章節編號、章節標題。
class VideoProjectFormPage extends ConsumerStatefulWidget {
  const VideoProjectFormPage({super.key});

  @override
  ConsumerState<VideoProjectFormPage> createState() =>
      _VideoProjectFormPageState();
}

class _VideoProjectFormPageState extends ConsumerState<VideoProjectFormPage> {
  @override
  void initState() {
    super.initState();
    // 每次打開都是空白表單
    Future.microtask(() {
      if (mounted) ref.read(videoProjectFormProvider.notifier).reset();
    });
  }

  Future<void> _submit() async {
    final project = await ref.read(videoProjectFormProvider.notifier).submit();
    if (project != null && mounted) context.go('/videos/${project.id}');
  }

  @override
  Widget build(BuildContext context) {
    final form = ref.watch(videoProjectFormProvider);
    final notifier = ref.read(videoProjectFormProvider.notifier);
    final games = ref.watch(videoGameOptionsProvider);
    final title = form.chapterTitle;
    return Scaffold(
      key: const Key('video-project-form-page'),
      appBar: AppBar(title: const Text('新增影片專案')),
      body: VideoPageBody(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.medium),
          children: [
            games.when(
              loading: () => const LinearProgressIndicator(),
              error: (error, _) => NoticeBanner(
                text: error is ApiException ? error.message : '讀不到遊戲清單',
                isError: true,
              ),
              data: (options) => DropdownButtonFormField<int>(
                key: const Key('video-project-game'),
                initialValue: form.game?.id,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: '遊戲',
                  prefixIcon: Icon(Icons.casino_outlined),
                ),
                items: [
                  for (final game in options)
                    DropdownMenuItem(value: game.id, child: Text(game.name)),
                ],
                onChanged: (id) {
                  for (final game in options) {
                    if (game.id == id) notifier.selectGame(game);
                  }
                },
              ),
            ),
            const SizedBox(height: AppSpacing.medium),
            TextField(
              key: const Key('video-project-chapter-number'),
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: '章節編號',
                helperText: '規則書目錄上的章節號碼',
                errorText:
                    form.chapterNumberInput.isNotEmpty &&
                        form.chapterNumber == null
                    ? '請填 1 以上的整數'
                    : null,
              ),
              onChanged: notifier.setChapterNumber,
            ),
            const SizedBox(height: AppSpacing.medium),
            TextField(
              key: const Key('video-project-chapter-title'),
              decoration: InputDecoration(
                labelText: '章節標題',
                counterText: '${title.length}／$videoChapterTitleMaxChars',
                errorText: title.length > videoChapterTitleMaxChars
                    ? '最多 $videoChapterTitleMaxChars 字'
                    : null,
              ),
              onChanged: notifier.setChapterTitle,
            ),
            if (form.error != null) ...[
              const SizedBox(height: AppSpacing.medium),
              NoticeBanner(text: form.error!, isError: true),
            ],
            const SizedBox(height: AppSpacing.large),
            FilledButton(
              key: const Key('video-project-submit'),
              onPressed: form.canSubmit ? _submit : null,
              child: Text(form.submitting ? '建立中…' : '建立'),
            ),
          ],
        ),
      ),
    );
  }
}
