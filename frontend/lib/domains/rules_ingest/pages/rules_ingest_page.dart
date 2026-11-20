import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../core/dev/state/dev_user_state.dart';
import '../../../core/layout/breakpoints.dart';
import '../data/game_option.dart';
import '../state/manual_pages_state.dart';

/// 規則書匯入正式頁面（`/rules-ingest`，add-rules-ingest-page）。
///
/// 只有管理員可以使用；其他人只看到提示，不載入遊戲清單。
/// 手機上下排列，平板與桌機左邊匯入、右邊已入庫頁面。
class RulesIngestPage extends ConsumerWidget {
  const RulesIngestPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final admin = ref.watch(currentDevUserProvider)?.role == 'admin';
    return Scaffold(
      key: const Key('rules-ingest-page'),
      appBar: AppBar(title: const Text('匯入規則書')),
      body: admin
          ? const _AdminView()
          : Center(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.large),
                child: Text(
                  '只有管理員可以匯入規則書',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            ),
    );
  }
}

class _AdminView extends StatelessWidget {
  const _AdminView();

  @override
  Widget build(BuildContext context) {
    const import = _ImportSection(key: Key('rules-ingest-import'));
    const stored = _StoredSection(key: Key('rules-ingest-stored'));
    const padding = EdgeInsets.all(AppSpacing.medium);
    if (context.screenSize == ScreenSize.mobile) {
      return const SingleChildScrollView(
        padding: padding,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            import,
            SizedBox(height: AppSpacing.medium),
            stored,
          ],
        ),
      );
    }
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppSpacing.splitContentMaxWidth,
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: SingleChildScrollView(padding: padding, child: import),
            ),
            Expanded(
              child: SingleChildScrollView(padding: padding, child: stored),
            ),
          ],
        ),
      ),
    );
  }
}

/// 一個區塊：標題加內容。
class _Section extends StatelessWidget {
  const _Section({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.medium),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: AppSpacing.medium),
            ...children,
          ],
        ),
      ),
    );
  }
}

/// 選桌遊、起始頁碼、選圖片、匯入與每一頁的結果。
class _ImportSection extends ConsumerWidget {
  const _ImportSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final upload = ref.watch(manualImportProvider);
    final pages = ref.watch(manualPagesProvider);
    final notifier = ref.read(manualImportProvider.notifier);
    final busy = upload.importing || upload.picking;
    final text = Theme.of(context).textTheme;
    final muted = text.bodyMedium!.copyWith(color: AppColors.inkMuted);
    final startPage = positiveInteger(upload.startPageInput) ?? 1;

    return _Section(
      title: '匯入規則書圖片',
      children: [
        Autocomplete<GameOption>(
          initialValue: TextEditingValue(text: upload.selectedGame?.name ?? ''),
          optionsBuilder: (_) => upload.filteredOptions,
          displayStringForOption: (option) => option.name,
          fieldViewBuilder: (context, controller, focusNode, onSubmitted) =>
              TextFormField(
                key: const Key('games-name-input'),
                controller: controller,
                focusNode: focusNode,
                enabled: !busy && !upload.gamesLoading,
                decoration: InputDecoration(
                  labelText: '桌遊名稱',
                  hintText: upload.gamesLoading ? '載入遊戲清單中…' : '輸入名稱過濾，或從下拉選取',
                  prefixIcon: const Icon(Icons.casino_outlined),
                ),
                onChanged: notifier.setGamesQuery,
              ),
          onSelected: notifier.selectGame,
        ),
        const SizedBox(height: AppSpacing.medium),
        TextFormField(
          key: const Key('start-page-input'),
          initialValue: upload.startPageInput,
          enabled: !busy,
          decoration: const InputDecoration(
            labelText: '起始頁碼',
            prefixIcon: Icon(Icons.format_list_numbered),
          ),
          keyboardType: TextInputType.number,
          onChanged: notifier.setStartPageInput,
        ),
        if (upload.error != null) ...[
          const SizedBox(height: AppSpacing.small),
          Text(
            upload.error!,
            style: text.bodyMedium!.copyWith(
              color: Theme.of(context).colorScheme.error,
            ),
          ),
        ],
        const SizedBox(height: AppSpacing.medium),
        OutlinedButton.icon(
          key: const Key('pick-images-button'),
          onPressed: busy ? null : notifier.pickImages,
          icon: const Icon(Icons.add_photo_alternate_outlined),
          label: const Text('選擇 JPEG／PNG 圖片'),
        ),
        if (upload.picking)
          const Padding(
            padding: EdgeInsets.all(AppSpacing.medium),
            child: Center(child: CircularProgressIndicator()),
          ),
        if (upload.images.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.medium),
          Text('已選 ${upload.images.length} 張圖片（拖曳調整順序）', style: muted),
          const SizedBox(height: AppSpacing.small),
          ReorderableListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            buildDefaultDragHandles: false,
            itemCount: upload.images.length,
            onReorder: notifier.reorderImages,
            itemBuilder: (context, index) {
              final image = upload.images[index];
              return ListTile(
                key: ValueKey(image.name),
                contentPadding: EdgeInsets.zero,
                leading: ClipRRect(
                  borderRadius: BorderRadius.circular(AppRadius.button),
                  child: Image.memory(
                    image.bytes,
                    width: AppSizes.pageThumbWidth,
                    height: AppSizes.pageThumbHeight,
                    fit: BoxFit.cover,
                    errorBuilder: (_, _, _) => SizedBox(
                      width: AppSizes.pageThumbWidth,
                      height: AppSizes.pageThumbHeight,
                      child: ColoredBox(
                        color: AppColors.neutralTint,
                        child: Center(child: Text('${index + 1}')),
                      ),
                    ),
                  ),
                ),
                title: Text(image.name),
                subtitle: Text('→ 匯入為第 ${startPage + index} 頁'),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    ReorderableDragStartListener(
                      index: index,
                      enabled: !busy,
                      child: const Padding(
                        padding: EdgeInsets.all(AppSpacing.small),
                        child: Icon(Icons.drag_handle),
                      ),
                    ),
                    IconButton(
                      key: Key('remove-image-$index'),
                      icon: const Icon(Icons.close),
                      tooltip: '移除',
                      onPressed: busy
                          ? null
                          : () => notifier.removeImage(index),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
        const SizedBox(height: AppSpacing.medium),
        FilledButton.icon(
          key: const Key('import-button'),
          onPressed: upload.canImport && !pages.loading
              ? notifier.importPages
              : null,
          icon: const Icon(Icons.upload_file_outlined),
          label: const Text('匯入'),
        ),
        if (upload.importing) ...[
          const SizedBox(height: AppSpacing.medium),
          const LinearProgressIndicator(),
          const SizedBox(height: AppSpacing.xSmall),
          Text('匯入中：${upload.current}／${upload.images.length}', style: muted),
        ],
        for (final result in upload.results)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(
              result.success ? Icons.check_circle_outline : Icons.error_outline,
              color: result.success
                  ? AppColors.success
                  : Theme.of(context).colorScheme.error,
            ),
            title: Text('第 ${result.page} 頁：${result.filename}'),
            subtitle: Text(result.success ? '成功' : result.error!),
          ),
      ],
    );
  }
}

/// 讀回已入庫頁面：OCR 實作提示與每一頁的內容。
class _StoredSection extends ConsumerWidget {
  const _StoredSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final upload = ref.watch(manualImportProvider);
    final pages = ref.watch(manualPagesProvider);
    final busy = upload.importing || upload.picking;
    final text = Theme.of(context).textTheme;
    final muted = text.bodyMedium!.copyWith(color: AppColors.inkMuted);
    final data = pages.data;

    return _Section(
      title: '已入庫頁面',
      children: [
        OutlinedButton.icon(
          key: const Key('read-pages-button'),
          onPressed: busy || pages.loading || upload.selectedGame == null
              ? null
              : () => ref
                    .read(manualPagesProvider.notifier)
                    .load(upload.selectedGame!.id.toString()),
          icon: const Icon(Icons.refresh),
          label: const Text('讀回已入庫頁面'),
        ),
        const SizedBox(height: AppSpacing.medium),
        if (pages.loading)
          const Center(child: CircularProgressIndicator())
        else if (pages.error != null)
          Text(
            pages.error!,
            style: text.bodyMedium!.copyWith(
              color: Theme.of(context).colorScheme.error,
            ),
          ),
        if (data == null)
          Text('請先讀回，確認目前 OCR 實作；cloud 匯入會產生費用', style: muted)
        else ...[
          Text('已讀回桌遊編號：${pages.gamesId}', style: muted),
          Text(
            data.ocrProvider == 'fake' ? 'OCR：fake（內容不是真實辨識結果）' : 'OCR：cloud',
            style: muted,
          ),
          if (data.ocrProvider == 'cloud')
            Text(
              '使用雲端 OCR 匯入會產生費用',
              style: text.bodyMedium!.copyWith(color: AppColors.warning),
            ),
          const SizedBox(height: AppSpacing.small),
          if (data.items.isEmpty) const Text('這款桌遊還沒有規則書頁面'),
          for (final page in data.items) ...[
            const Divider(),
            Text('第 ${page.page} 頁', style: text.titleSmall),
            const SizedBox(height: AppSpacing.xSmall),
            SelectableText(page.content.isEmpty ? '（整頁沒文字）' : page.content),
          ],
        ],
      ],
    );
  }
}
