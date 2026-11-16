import 'package:flutter/material.dart';

import '../../core/layout/breakpoints.dart';
import '../../core/widgets/pill_badge.dart';
import 'app_colors.dart';
import 'app_spacing.dart';

/// 主題預覽：一頁看完色票、字級與各元件套用主題後的樣子。
/// 只在 `SHOW_PROTOTYPES=true` 時註冊在 `/proto/theme`。
class ThemePreviewPage extends StatefulWidget {
  const ThemePreviewPage({super.key});

  @override
  State<ThemePreviewPage> createState() => _ThemePreviewPageState();
}

class _ThemePreviewPageState extends State<ThemePreviewPage> {
  int _tab = 0;
  bool _beginner = true;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final maxWidth =
        AppSpacing.contentMaxWidth(context.screenSize) ?? double.infinity;
    return Scaffold(
      key: const Key('theme-preview-page'),
      appBar: AppBar(title: const Text('主題預覽')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {},
        icon: const Icon(Icons.add),
        label: const Text('我要開團'),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: '首頁'),
          NavigationDestination(icon: Icon(Icons.groups_outlined), label: '揪團'),
          NavigationDestination(
            icon: Icon(Icons.menu_book_outlined),
            label: '規則',
          ),
          NavigationDestination(icon: Icon(Icons.person_outline), label: '我的'),
        ],
      ),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.medium),
            children: [
              const _Section('色票'),
              const Wrap(
                spacing: AppSpacing.small,
                runSpacing: AppSpacing.small,
                children: [
                  _Swatch('背景', AppColors.background),
                  _Swatch('卡片', AppColors.surface),
                  _Swatch('主色', AppColors.primary),
                  _Swatch('亮主色', AppColors.primaryBright),
                  _Swatch('鼠尾草綠', AppColors.sage),
                  _Swatch('蜂蜜琥珀', AppColors.amber),
                  _Swatch('暖炭褐', AppColors.ink),
                  _Swatch('暖灰', AppColors.inkMuted),
                ],
              ),
              const _Section('字級'),
              Text('遊任有娛 Tabletop', style: text.headlineMedium),
              Text('週末輕策略團 Weekend Game Night', style: text.titleLarge),
              Text('副標題 Title medium', style: text.titleMedium),
              Text(
                '內文：一局約 30 到 45 分鐘，適合 3 到 5 人，新手也能很快上手。',
                style: text.bodyLarge,
              ),
              Text('說明文字 Body small', style: text.bodySmall),
              const _Section('卡片'),
              const _GroupCardSample(),
              const _Section('膠囊標籤'),
              const Wrap(
                spacing: AppSpacing.small,
                runSpacing: AppSpacing.small,
                children: [
                  PillBadge(label: '測試桌遊店'),
                  PillBadge(
                    label: '3–5 人',
                    tone: PillTone.players,
                    icon: Icons.people_outline,
                  ),
                  PillBadge(label: '新手友善', tone: PillTone.players),
                  PillBadge(
                    label: '45 分鐘',
                    tone: PillTone.duration,
                    icon: Icons.schedule,
                  ),
                  PillBadge(label: '進行中', tone: PillTone.duration),
                  PillBadge(label: '剩 1 位', tone: PillTone.accent),
                ],
              ),
              const _Section('按鈕'),
              Wrap(
                spacing: AppSpacing.small,
                runSpacing: AppSpacing.small,
                children: [
                  FilledButton(onPressed: () {}, child: const Text('報名')),
                  OutlinedButton(onPressed: () {}, child: const Text('加入候補')),
                  TextButton(onPressed: () {}, child: const Text('查看規則')),
                  const FilledButton(onPressed: null, child: Text('已額滿')),
                  IconButton(
                    onPressed: () {},
                    icon: const Icon(Icons.chevron_right),
                  ),
                ],
              ),
              const _Section('輸入與選擇'),
              const TextField(
                decoration: InputDecoration(
                  labelText: '揪團標題',
                  hintText: '例如：週五晚上輕策略',
                ),
              ),
              const SizedBox(height: AppSpacing.medium),
              const TextField(
                decoration: InputDecoration(
                  labelText: '人數上限',
                  errorText: '人數上限至少 2 人',
                ),
              ),
              const SizedBox(height: AppSpacing.medium),
              Wrap(
                spacing: AppSpacing.small,
                children: [
                  FilterChip(
                    label: const Text('新手友善'),
                    selected: _beginner,
                    onSelected: (v) => setState(() => _beginner = v),
                  ),
                  const Chip(label: Text('策略')),
                ],
              ),
              const _Section('回饋'),
              Wrap(
                spacing: AppSpacing.small,
                children: [
                  OutlinedButton(
                    onPressed: () => ScaffoldMessenger.of(
                      context,
                    ).showSnackBar(const SnackBar(content: Text('報名成功'))),
                    child: const Text('顯示提示'),
                  ),
                  OutlinedButton(
                    onPressed: () => showDialog<void>(
                      context: context,
                      builder: (context) => AlertDialog(
                        title: const Text('確定要退出揪團？'),
                        content: const Text('退出後名額會讓給候補的玩家。'),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(context),
                            child: const Text('取消'),
                          ),
                          FilledButton(
                            onPressed: () => Navigator.pop(context),
                            child: const Text('確定'),
                          ),
                        ],
                      ),
                    ),
                    child: const Text('顯示對話框'),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xLarge * 3),
            ],
          ),
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(this.title);

  final String title;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(
      top: AppSpacing.large,
      bottom: AppSpacing.small,
    ),
    child: Text(title, style: Theme.of(context).textTheme.titleMedium),
  );
}

class _Swatch extends StatelessWidget {
  const _Swatch(this.name, this.color);

  final String name;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final hex = color.toARGB32().toRadixString(16).substring(2).toUpperCase();
    return SizedBox(
      width: AppSpacing.xLarge * 3,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: AppSpacing.xLarge * 1.5,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(AppRadius.button),
              border: Border.all(color: AppColors.border),
            ),
          ),
          const SizedBox(height: AppSpacing.xSmall),
          Text(name, style: Theme.of(context).textTheme.labelMedium),
          Text('#$hex', style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}

/// 揪團卡片的範例，示範卡片、標籤與按鈕搭配起來的樣子。
class _GroupCardSample extends StatelessWidget {
  const _GroupCardSample();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppRadius.card),
        boxShadow: AppShadows.card,
      ),
      child: Card(
        elevation: 0,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('19:00 – 21:30', style: text.bodySmall),
              const SizedBox(height: AppSpacing.xSmall),
              Text('週五晚上輕策略', style: text.titleLarge),
              const SizedBox(height: AppSpacing.xSmall),
              Text('測試桌遊店 · 開團主：小明', style: text.bodyMedium),
              const SizedBox(height: AppSpacing.medium),
              const Wrap(
                spacing: AppSpacing.small,
                runSpacing: AppSpacing.small,
                children: [
                  PillBadge(
                    label: '3/4 人',
                    tone: PillTone.players,
                    icon: Icons.people_outline,
                  ),
                  PillBadge(
                    label: '150 分鐘',
                    tone: PillTone.duration,
                    icon: Icons.schedule,
                  ),
                  PillBadge(label: '剩 1 位', tone: PillTone.accent),
                ],
              ),
              const SizedBox(height: AppSpacing.medium),
              SizedBox(
                width: double.infinity,
                child: FilledButton(onPressed: () {}, child: const Text('報名')),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
