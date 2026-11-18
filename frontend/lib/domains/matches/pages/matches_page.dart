import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../data/game_match.dart';
import '../state/match_form_state.dart';
import '../state/match_games.dart';
import '../state/match_labels.dart';
import '../state/match_list_state.dart';
import '../state/match_shops.dart';
import 'widgets/match_widgets.dart';

/// 戰績（`/matches`）：開一局、用編號打開、最近的局。
///
/// 手機上下排列；平板與桌機左右並排。開局成功後跳到這一局（`/matches/<id>`）。
class MatchesPage extends ConsumerWidget {
  const MatchesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen(matchFormProvider.select((s) => s.created), (_, created) {
      if (created != null) context.go('/matches/${created.id}');
    });
    final wide = context.screenSize != ScreenSize.mobile;
    const form = _MatchFormCard(key: Key('match-form-card'));
    const list = _RecentCard(key: Key('match-list-card'));
    return Scaffold(
      key: const Key('matches-page'),
      appBar: AppBar(title: const Text('戰績')),
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: wide ? AppSpacing.splitContentMaxWidth : double.infinity,
          ),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.medium),
            children: [
              if (wide)
                const Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: form),
                    SizedBox(width: AppSpacing.medium),
                    Expanded(child: list),
                  ],
                )
              else ...const [form, SizedBox(height: AppSpacing.medium), list],
            ],
          ),
        ),
      ),
    );
  }
}

/// 開一局：遊戲、日期（預設今天）、自家或桌遊店、店家、我的座位。
class _MatchFormCard extends ConsumerStatefulWidget {
  const _MatchFormCard({super.key});

  @override
  ConsumerState<_MatchFormCard> createState() => _MatchFormCardState();
}

class _MatchFormCardState extends ConsumerState<_MatchFormCard> {
  MatchFormNotifier get _n => ref.read(matchFormProvider.notifier);

  static DateTime _today() {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && ref.read(matchFormProvider).playedOn == null) {
        _n.setPlayedOn(_today());
      }
    });
  }

  Future<void> _pickDate() async {
    final current = ref.read(matchFormProvider).playedOn ?? _today();
    final picked = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(current.year - 5),
      lastDate: DateTime(current.year + 1, 12, 31),
    );
    if (picked != null) _n.setPlayedOn(picked);
  }

  @override
  Widget build(BuildContext context) {
    final form = ref.watch(matchFormProvider);
    final games = ref.watch(matchGameOptionsProvider);
    return MatchSection(
      title: '開一局',
      children: [
        games.when(
          loading: () => const LinearProgressIndicator(),
          error: (error, _) => MatchLoadError(
            error: error,
            prefix: '遊戲載入失敗',
            retryKey: const Key('match-games-retry'),
            onRetry: () => ref.invalidate(matchGameOptionsProvider),
          ),
          data: (options) => DropdownButtonFormField<int>(
            key: const Key('match-game'),
            initialValue: form.gameId,
            isExpanded: true,
            decoration: InputDecoration(
              labelText: '遊戲',
              prefixIcon: const Icon(Icons.casino_outlined),
              errorText: form.errors['gameId'],
            ),
            items: [
              for (final game in options)
                DropdownMenuItem(value: game.id, child: Text(game.name)),
            ],
            onChanged: _n.setGameId,
          ),
        ),
        const SizedBox(height: AppSpacing.medium),
        OutlinedButton.icon(
          key: const Key('match-date'),
          onPressed: _pickDate,
          icon: const Icon(Icons.calendar_today_outlined),
          label: Text('日期：${formatPlayedOn(form.playedOn ?? _today())}'),
        ),
        FieldError(form.errors['playedOn']),
        const SizedBox(height: AppSpacing.medium),
        SegmentedButton<String>(
          segments: [
            ButtonSegment(
              value: 'home',
              icon: const Icon(Icons.home_outlined),
              label: Text(
                locationLabel('home'),
                key: const Key('match-location-home'),
              ),
            ),
            ButtonSegment(
              value: 'shop',
              icon: const Icon(Icons.storefront_outlined),
              label: Text(
                locationLabel('shop'),
                key: const Key('match-location-shop'),
              ),
            ),
          ],
          selected: {form.locationType},
          onSelectionChanged: (s) => _n.setLocationType(s.first),
        ),
        if (form.locationType == 'shop') ...[
          const SizedBox(height: AppSpacing.medium),
          _ShopField(form: form),
        ],
        const SizedBox(height: AppSpacing.medium),
        TextField(
          key: const Key('match-seat'),
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(
            labelText: '我的座位（選填，不填給最小的空位）',
            prefixIcon: Icon(Icons.event_seat_outlined),
          ),
          onChanged: (v) => _n.setSeatNumber(int.tryParse(v.trim())),
        ),
        if (form.error case final error?) ...[
          const SizedBox(height: AppSpacing.medium),
          MatchBanner(
            key: const Key('match-form-error'),
            text: matchErrorText(error),
            isError: true,
          ),
        ],
        const SizedBox(height: AppSpacing.medium),
        FilledButton.icon(
          key: const Key('match-create'),
          onPressed: form.busy ? null : _n.submit,
          icon: const Icon(Icons.play_arrow),
          label: const Text('開局'),
        ),
      ],
    );
  }
}

class _ShopField extends ConsumerWidget {
  const _ShopField({required this.form});

  final MatchFormState form;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final shops = ref.watch(matchShopsProvider);
    return shops.when(
      loading: () => const LinearProgressIndicator(),
      error: (error, _) => MatchLoadError(
        error: error,
        prefix: '店家載入失敗',
        retryKey: const Key('match-shops-retry'),
        onRetry: () => ref.invalidate(matchShopsProvider),
      ),
      data: (options) => options.isEmpty
          ? const Text('目前沒有可選的店家')
          : DropdownButtonFormField<String>(
              key: const Key('match-shop'),
              initialValue: form.shopId.isEmpty ? null : form.shopId,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: '店家',
                prefixIcon: const Icon(Icons.storefront_outlined),
                errorText: form.errors['shopId'],
              ),
              items: [
                for (final shop in options)
                  DropdownMenuItem(value: shop.id, child: Text(shop.name)),
              ],
              onChanged: (v) =>
                  ref.read(matchFormProvider.notifier).setShopId(v ?? ''),
            ),
    );
  }
}

/// 用編號打開與最近的局。
class _RecentCard extends ConsumerStatefulWidget {
  const _RecentCard({super.key});

  @override
  ConsumerState<_RecentCard> createState() => _RecentCardState();
}

class _RecentCardState extends ConsumerState<_RecentCard> {
  final _openId = TextEditingController();

  @override
  void dispose() {
    _openId.dispose();
    super.dispose();
  }

  void _open() {
    final id = _openId.text.trim();
    if (id.isNotEmpty) context.go('/matches/$id');
  }

  @override
  Widget build(BuildContext context) {
    final recent = ref.watch(matchListProvider);
    return MatchSection(
      title: '最近的局',
      trailing: IconButton(
        key: const Key('match-list-refresh'),
        tooltip: '重新整理',
        onPressed: () => ref.invalidate(matchListProvider),
        icon: const Icon(Icons.refresh),
      ),
      children: [
        Row(
          children: [
            Expanded(
              child: TextField(
                key: const Key('match-open-id'),
                controller: _openId,
                decoration: const InputDecoration(labelText: '局的編號（朋友傳來的）'),
                onSubmitted: (_) => _open(),
              ),
            ),
            const SizedBox(width: AppSpacing.small),
            OutlinedButton(
              key: const Key('match-open'),
              onPressed: _open,
              child: const Text('打開'),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.medium),
        recent.when(
          skipLoadingOnRefresh: false,
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => MatchLoadError(
            error: error,
            retryKey: const Key('match-list-retry'),
            onRetry: () => ref.invalidate(matchListProvider),
          ),
          data: (items) => items.isEmpty
              ? const Text('還沒有任何一局，先開一局吧')
              : Column(
                  children: [
                    for (final (i, m) in items.indexed) ...[
                      if (i > 0) const Divider(height: AppSpacing.small),
                      _MatchListItem(key: Key('match-item-${m.id}'), match: m),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}

class _MatchListItem extends StatelessWidget {
  const _MatchListItem({required this.match, super.key});

  final GameMatch match;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return InkWell(
      borderRadius: BorderRadius.circular(AppRadius.button),
      onTap: () => context.go('/matches/${match.id}'),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.small),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    match.game.name,
                    style: textTheme.titleSmall!.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    '${formatPlayedOn(match.playedOn)}・'
                    '${matchLocationText(match)}・${match.participantCount} 人',
                    style: textTheme.bodyMedium!.copyWith(
                      color: AppColors.inkMuted,
                    ),
                  ),
                ],
              ),
            ),
            PillBadge(
              label: statusLabel(match.status),
              tone: match.status == 'in_progress'
                  ? PillTone.duration
                  : PillTone.neutral,
            ),
          ],
        ),
      ),
    );
  }
}
