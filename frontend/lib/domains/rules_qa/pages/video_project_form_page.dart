import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../core/api/api_exception.dart';
import '../state/video_projects_state.dart';
import 'widgets/notice_banner.dart';
import 'widgets/video_studio_widgets.dart';

/// 建立影片專案（`/videos/new`）：只選遊戲（整個遊戲一支影片，design.md D17）。
/// 建立後後端自動開始產生草稿，畫面回到專案總覽看進度。
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
    if (project == null || !mounted) return;
    // 拍規則書：直接到規則書頁；已匯入的規則書：回到專案總覽看草稿進度
    context.go(
      project.step == 'rulebook'
          ? '/videos/${project.id}/rulebook'
          : '/videos/${project.id}',
    );
  }

  @override
  Widget build(BuildContext context) {
    final form = ref.watch(videoProjectFormProvider);
    final notifier = ref.read(videoProjectFormProvider.notifier);
    final games = ref.watch(videoGameOptionsProvider);
    final text = Theme.of(context).textTheme;
    return Scaffold(
      key: const Key('video-project-form-page'),
      appBar: AppBar(title: const Text('新增影片專案')),
      body: VideoPageBody(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.medium),
          children: [
            Text(
              '選一款遊戲，AI 會從規則書整理出開局、走完一輪、獲勝方式，做成一支教學影片',
              style: text.bodyMedium,
            ),
            const SizedBox(height: AppSpacing.medium),
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
            Text('規則書', style: text.titleSmall),
            RadioGroup<String>(
              groupValue: form.rulebook,
              onChanged: (value) {
                if (value != null) notifier.selectRulebook(value);
              },
              child: const Column(
                children: [
                  RadioListTile<String>(
                    key: Key('video-project-rulebook-imported'),
                    value: 'imported',
                    title: Text('用已匯入的規則書'),
                    subtitle: Text('管理員已經匯入這款遊戲的規則書'),
                  ),
                  RadioListTile<String>(
                    key: Key('video-project-rulebook-photos'),
                    value: 'photos',
                    title: Text('拍規則書'),
                    subtitle: Text('用手機依頁面順序拍規則書的每一頁'),
                  ),
                ],
              ),
            ),
            if (form.error != null) ...[
              const SizedBox(height: AppSpacing.medium),
              NoticeBanner(text: form.error!, isError: true),
            ],
            const SizedBox(height: AppSpacing.large),
            FilledButton(
              key: const Key('video-project-submit'),
              onPressed: form.canSubmit ? _submit : null,
              child: Text(
                form.submitting
                    ? '建立中…'
                    : form.rulebook == 'photos'
                    ? '建立並拍規則書'
                    : '建立並產生草稿',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
