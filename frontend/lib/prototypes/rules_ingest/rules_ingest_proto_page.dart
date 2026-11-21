import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/rules_ingest/data/game_option.dart';
import '../../domains/rules_ingest/state/manual_pages_state.dart';

class RulesIngestProtoPage extends ConsumerWidget {
  const RulesIngestProtoPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final upload = ref.watch(manualImportProvider);
    final pages = ref.watch(manualPagesProvider);
    final notifier = ref.read(manualImportProvider.notifier);
    final busy = upload.importing || upload.picking;
    return Scaffold(
      key: const Key('rules-ingest-proto-page'),
      appBar: AppBar(title: const Text('規則書圖片匯入（參考畫面）')),
      body: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Autocomplete<GameOption>(
                  initialValue:
                      upload.selectedGame != null
                          ? TextEditingValue(text: upload.selectedGame!.name)
                          : const TextEditingValue(text: ''),
                  optionsBuilder: (editingValue) {
                    return upload.filteredOptions;
                  },
                  displayStringForOption: (option) => option.name,
                  fieldViewBuilder:
                      (ctx, controller, focusNode, onSubmitted) =>
                          TextFormField(
                            key: const Key('games-name-input'),
                            controller: controller,
                            focusNode: focusNode,
                            enabled: !busy && !upload.gamesLoading,
                            decoration: InputDecoration(
                              labelText: '桌遊名稱',
                              hintText: upload.gamesLoading ? '載入遊戲清單中…' : '輸入名稱過濾，或直接從下拉選取',
                              suffixIcon: upload.gamesLoading
                                  ? const SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(strokeWidth: 2),
                                    )
                                  : const Icon(Icons.arrow_drop_down),
                            ),
                            onChanged: (value) => notifier.setGamesQuery(value),
                          ),
                  onSelected: (option) => notifier.selectGame(option),
                ),
                TextFormField(
                  key: const Key('start-page-input'),
                  initialValue: upload.startPageInput,
                  enabled: !busy,
                  decoration: const InputDecoration(labelText: '起始頁碼'),
                  keyboardType: TextInputType.number,
                  onChanged: notifier.setStartPageInput,
                ),
                if (upload.error != null) Text(upload.error!),
                ElevatedButton(
                  key: const Key('pick-images-button'),
                  onPressed: busy ? null : notifier.pickImages,
                  child: const Text('選擇 JPEG／PNG 圖片'),
                ),
                if (upload.picking) const CircularProgressIndicator(),
                if (upload.images.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text(
                      '已選 ${upload.images.length} 張圖片（拖曳調整順序）：',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ),
              ],
            ),
          ),
          if (upload.images.isNotEmpty)
            SliverReorderableList(
              itemCount: upload.images.length,
              onReorder: notifier.reorderImages,
              proxyDecorator:
                  (child, index, animation) => Material(
                    elevation: 4,
                    borderRadius: BorderRadius.circular(8),
                    child: child,
                  ),
              itemBuilder:
                  (context, index) => Card(
                    key: ValueKey(upload.images[index].name),
                    child: ListTile(
                      dense: true,
                      leading: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: Image.memory(
                          upload.images[index].bytes,
                          width: 60,
                          height: 80,
                          fit: BoxFit.cover,
                          errorBuilder: (_, error, stack) => CircleAvatar(
                            backgroundColor:
                                Theme.of(context).colorScheme.primaryContainer,
                            child: Text('${index + 1}'),
                          ),
                        ),
                      ),
                      title: Text(upload.images[index].name),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          ReorderableDragStartListener(
                            index: index,
                            child: const Padding(
                              padding: EdgeInsets.all(8),
                              child: Icon(Icons.drag_handle),
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close),
                            tooltip: '移除',
                            onPressed: () => notifier.removeImage(index),
                          ),
                        ],
                      ),
                      subtitle: Text(
                        '→ 匯入為第 ${(positiveInteger(upload.startPageInput) ?? 1) + index} 頁',
                      ),
                    ),
                  ),
            ),
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ElevatedButton(
                  key: const Key('import-button'),
                  onPressed:
                      upload.canImport && !pages.loading
                          ? notifier.importPages
                          : null,
                  child: const Text('匯入'),
                ),
                if (upload.importing) ...[
                  const LinearProgressIndicator(),
                  Text('匯入中：${upload.current}／${upload.images.length}'),
                ],
                for (final result in upload.results)
                  ListTile(
                    title: Text('第 ${result.page} 頁：${result.filename}'),
                    subtitle: Text(
                      result.success
                          ? '成功（索引 ${result.chunkCount} 段）'
                          : result.error!,
                    ),
                  ),
                ElevatedButton(
                  key: const Key('read-pages-button'),
                  onPressed:
                      busy ||
                              pages.loading ||
                              upload.selectedGame == null
                          ? null
                          : () => ref
                              .read(manualPagesProvider.notifier)
                              .load(upload.selectedGame!.id.toString()),
                  child: const Text('讀回已入庫頁面'),
                ),
                if (pages.loading) const CircularProgressIndicator(),
                if (pages.error != null) Text(pages.error!),
                if (pages.data != null) ...[
                  Text('已讀回桌遊編號：${pages.gamesId}'),
                  Text(
                    pages.data!.ocrProvider == 'fake'
                        ? 'OCR：fake（內容不是真實辨識結果）'
                        : 'OCR：cloud',
                  ),
                  if (pages.data!.ocrProvider == 'cloud')
                    const Text('使用雲端 OCR 匯入會產生費用'),
                  if (pages.data!.items.isEmpty)
                    const Text('這款桌遊還沒有規則書頁面'),
                  for (final page in pages.data!.items)
                    ListTile(
                      title: Text('第 ${page.page} 頁'),
                      subtitle: SelectableText(
                        page.content.isEmpty ? '（整頁沒文字）' : page.content,
                      ),
                    ),
                ] else
                  const Text('請先讀回，確認目前 OCR 實作；cloud 匯入會產生費用'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
