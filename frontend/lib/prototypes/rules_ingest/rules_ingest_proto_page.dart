import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
      body: ListView(
        children: [
          TextFormField(
            key: const Key('games-id-input'),
            initialValue: upload.gamesInput,
            enabled: !busy,
            decoration: const InputDecoration(labelText: '桌遊編號 games_id'),
            keyboardType: TextInputType.number,
            onChanged: notifier.setGamesInput,
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
          for (var index = 0; index < upload.images.length; index++)
            Text(
              '${index + 1}. ${upload.images[index].name} → 第 ${(positiveInteger(upload.startPageInput) ?? 1) + index} 頁',
            ),
          ElevatedButton(
            key: const Key('import-button'),
            onPressed: upload.canImport && !pages.loading
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
              subtitle: Text(result.success ? '成功' : result.error!),
            ),
          ElevatedButton(
            key: const Key('read-pages-button'),
            onPressed:
                busy ||
                    pages.loading ||
                    positiveInteger(upload.gamesInput) == null
                ? null
                : () => ref
                      .read(manualPagesProvider.notifier)
                      .load(upload.gamesInput),
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
            if (pages.data!.items.isEmpty) const Text('這款桌遊還沒有規則書頁面'),
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
    );
  }
}
