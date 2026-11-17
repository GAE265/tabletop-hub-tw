import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../domains/rules_qa/state/rules_lessons_state.dart';
import 'rules_lesson_proto_page.dart';

/// 規則教學參考畫面：遊戲清單。只用預設元件，不調顏色、字型、間距（AGENTS.md 5.4）。
class RulesQaProtoPage extends ConsumerWidget {
  const RulesQaProtoPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lessons = ref.watch(rulesLessonsProvider);
    return Scaffold(
      key: const Key('rules_qa-proto-page'),
      appBar: AppBar(title: const Text('規則教學（參考畫面）')),
      body: lessons.when(
        skipLoadingOnRefresh: false,
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(error is ApiException ? error.message : '發生未知錯誤'),
              ElevatedButton(
                onPressed: ref.read(rulesLessonsProvider.notifier).reload,
                child: const Text('重試'),
              ),
            ],
          ),
        ),
        data: (items) => items.isEmpty
            ? const Center(child: Text('目前還沒有可以教學的遊戲'))
            : ListView(
                children: [
                  for (final item in items)
                    ListTile(
                      title: Text(item.gameName),
                      subtitle: item.hasVideo ? const Text('有教學影片') : null,
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) =>
                              RulesLessonProtoPage(gameId: item.gameId),
                        ),
                      ),
                    ),
                ],
              ),
      ),
    );
  }
}
