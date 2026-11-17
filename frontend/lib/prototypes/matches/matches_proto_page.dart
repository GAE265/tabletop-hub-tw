import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../domains/matches/state/match_form_state.dart';
import '../../domains/matches/state/match_labels.dart';
import '../../domains/matches/state/match_list_state.dart';
import '../../domains/matches/state/match_shops.dart';
import 'proto_widgets.dart';

/// 記錄一局遊戲的參考畫面：開局、打開已有的局、最近的局。
///
/// 只用 Flutter 預設元件，不調顏色、字型、間距。按鈕和狀態對應的 state 方法見
/// docs/handoff/matches.md。
class MatchesProtoPage extends ConsumerStatefulWidget {
  const MatchesProtoPage({super.key});

  @override
  ConsumerState<MatchesProtoPage> createState() => _MatchesProtoPageState();
}

class _MatchesProtoPageState extends ConsumerState<MatchesProtoPage> {
  // 資料庫的 1 號是《血與刃的白薔薇》（ADR 0003：1–4 號固定是 Demo 遊戲）
  final _gameId = TextEditingController(text: '1');
  final _seat = TextEditingController();
  final _openId = TextEditingController();

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (!mounted) return;
      final form = ref.read(matchFormProvider.notifier);
      form.setGameId(1);
      form.setPlayedOn(DateTime.now());
    });
  }

  @override
  void dispose() {
    _gameId.dispose();
    _seat.dispose();
    _openId.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final current = ref.read(matchFormProvider).playedOn ?? DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
    );
    if (picked != null) {
      ref.read(matchFormProvider.notifier).setPlayedOn(picked);
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(matchFormProvider.select((s) => s.created), (_, created) {
      if (created != null) context.go('/proto/matches/${created.id}');
    });
    final form = ref.watch(matchFormProvider);
    final notifier = ref.read(matchFormProvider.notifier);
    final shops = ref.watch(matchShopsProvider);
    final recent = ref.watch(matchListProvider);

    return Scaffold(
      key: const Key('matches-proto-page'),
      appBar: AppBar(title: const Text('記錄一局遊戲（參考畫面）')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Text('開局', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
          TextField(
            key: const Key('game-id'),
            controller: _gameId,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              labelText: '遊戲編號',
              helperText: '1＝血與刃的白薔薇（本機資料庫的固定編號）',
              errorText: form.errors['gameId'],
            ),
            onChanged: (v) => notifier.setGameId(int.tryParse(v.trim())),
          ),
          ListTile(
            key: const Key('played-on'),
            title: Text(
              '日期：${form.playedOn == null ? '尚未選擇' : formatDate(form.playedOn!)}',
            ),
            subtitle: form.errors['playedOn'] == null
                ? null
                : Text(form.errors['playedOn']!),
            trailing: TextButton(
              key: const Key('pick-date'),
              onPressed: _pickDate,
              child: const Text('選擇日期'),
            ),
          ),
          SegmentedButton<String>(
            key: const Key('location-type'),
            segments: [
              ButtonSegment(value: 'home', label: Text(locationLabel('home'))),
              ButtonSegment(value: 'shop', label: Text(locationLabel('shop'))),
            ],
            selected: {form.locationType},
            onSelectionChanged: (s) => notifier.setLocationType(s.first),
          ),
          if (form.locationType == 'shop')
            shops.when(
              loading: () => const Padding(
                padding: EdgeInsets.all(8),
                child: Text('店家載入中…', key: Key('shops-loading')),
              ),
              error: (e, _) => Column(
                key: const Key('shops-error'),
                children: [
                  Text('店家載入失敗：${errorText(e)}'),
                  TextButton(
                    onPressed: () => ref.invalidate(matchShopsProvider),
                    child: const Text('重試'),
                  ),
                ],
              ),
              data: (items) => items.isEmpty
                  ? const Text('目前沒有可選的店家', key: Key('shops-empty'))
                  : DropdownButtonFormField<String>(
                      key: const Key('shop-id'),
                      initialValue: items.any((s) => s.id == form.shopId)
                          ? form.shopId
                          : null,
                      decoration: InputDecoration(
                        labelText: '店家',
                        errorText: form.errors['shopId'],
                      ),
                      items: [
                        for (final shop in items)
                          DropdownMenuItem(
                            value: shop.id,
                            child: Text(shop.name),
                          ),
                      ],
                      onChanged: (v) => notifier.setShopId(v ?? ''),
                    ),
            ),
          TextField(
            key: const Key('my-seat'),
            controller: _seat,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: '我的座位（選填，不填給最小的空位）'),
            onChanged: (v) => notifier.setSeatNumber(int.tryParse(v.trim())),
          ),
          if (form.error != null) ErrorLine(form.error!),
          FilledButton(
            key: const Key('create-match'),
            onPressed: form.busy ? null : notifier.submit,
            child: Text(form.busy ? '開局中…' : '開局'),
          ),
          const Divider(),
          const Text('打開已有的局', style: TextStyle(fontWeight: FontWeight.bold)),
          TextField(
            key: const Key('open-id'),
            controller: _openId,
            decoration: const InputDecoration(labelText: '局的編號'),
          ),
          OutlinedButton(
            key: const Key('open-match'),
            onPressed: () {
              final id = _openId.text.trim();
              if (id.isNotEmpty) context.go('/proto/matches/$id');
            },
            child: const Text('打開'),
          ),
          const Divider(),
          Row(
            children: [
              const Expanded(
                child: Text(
                  '最近的局',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
              IconButton(
                key: const Key('refresh-list'),
                tooltip: '重新整理',
                icon: const Icon(Icons.refresh),
                onPressed: () => ref.invalidate(matchListProvider),
              ),
            ],
          ),
          recent.when(
            loading: () => const Text('載入中…', key: Key('list-loading')),
            error: (e, _) => Column(
              key: const Key('list-error'),
              children: [
                Text('載入失敗：${errorText(e)}'),
                TextButton(
                  onPressed: () => ref.invalidate(matchListProvider),
                  child: const Text('重試'),
                ),
              ],
            ),
            data: (matches) => matches.isEmpty
                ? const Text('還沒有任何一局，先開一局吧', key: Key('list-empty'))
                : Column(
                    children: [
                      for (final m in matches)
                        ListTile(
                          key: Key('match-${m.id}'),
                          title: Text(
                            '${m.game.name}　${formatDate(m.playedOn)}',
                          ),
                          subtitle: Text(
                            '${statusLabel(m.status)}・${locationLabel(m.locationType)}・'
                            '${m.participantCount} 人參加',
                          ),
                          onTap: () => context.go('/proto/matches/${m.id}'),
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

/// 錯誤顯示成一行文字：優先用後端的訊息。
String errorText(Object error) =>
    error is ApiException ? '${error.message}（${error.code}）' : '$error';
