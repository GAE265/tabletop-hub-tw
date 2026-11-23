import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/layout/breakpoints.dart';
import '../../../core/widgets/pill_badge.dart';
import '../../booking/data/shop.dart';
import '../../groups/data/group.dart';
import '../data/game_match.dart';
import '../state/match_current_user.dart';
import '../state/match_form_state.dart';
import '../state/match_games.dart';
import '../state/match_labels.dart';
import '../state/match_list_state.dart';
import '../state/match_shops.dart';
import 'widgets/match_widgets.dart';

/// 從揪團的「填入戰績」進來時的揪團 id（網址 `?group_id=`）。
class MatchPrefill {
  const MatchPrefill({this.groupId});

  /// 有值時：上方顯示揪團名稱、最近的局只列這個揪團的局，開局帶入揪團的店家與唯一的遊戲，
  /// 並帶 `group_id`，這一局連到該揪團。
  final String? groupId;
}

/// 戰績（`/matches`）：頁首、用編號打開、開一局、最近的局。
///
/// Stitch 版面：木紋背景，文字都放在有厚度的卡片上。手機上下排列；平板與桌機的開局表單與
/// 最近的局左右並排。開局成功後跳到這一局（`/matches/<id>`）。
/// 網址參數 `group_id`（從揪團的「填入戰績」進來）：讀取揪團後帶入開局表單，
/// 最近的局只列這個揪團的局。
class MatchesPage extends ConsumerWidget {
  const MatchesPage({this.prefill = const MatchPrefill(), super.key});

  factory MatchesPage.fromQuery(Map<String, String> query, {Key? key}) {
    final groupId = query['group_id']?.trim();
    return MatchesPage(
      key: key,
      prefill: MatchPrefill(
        groupId: groupId == null || groupId.isEmpty ? null : groupId,
      ),
    );
  }

  final MatchPrefill prefill;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen(matchFormProvider.select((s) => s.created), (_, created) {
      if (created != null) context.go('/matches/${created.id}');
    });
    final wide = context.screenSize != ScreenSize.mobile;
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    final form = _MatchFormCard(
      key: const Key('match-form-card'),
      prefill: prefill,
    );
    final list = _RecentList(
      key: const Key('match-list-card'),
      groupId: prefill.groupId,
    );
    const gap = SizedBox(height: AppSpacing.medium);
    final body = Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: wide ? AppSpacing.splitContentMaxWidth : double.infinity,
        ),
        child: ListView(
          // 手機的浮動導覽列蓋住的高度留在最下面
          padding: EdgeInsets.fromLTRB(
            AppSpacing.medium,
            AppSpacing.medium,
            AppSpacing.medium,
            AppSpacing.medium + bottomInset,
          ),
          children: [
            _Header(key: const Key('match-header'), groupId: prefill.groupId),
            gap,
            if (prefill.groupId case final groupId?) ...[
              _GroupHeader(groupId: groupId),
              gap,
            ],
            const _OpenCard(key: Key('match-open-card')),
            gap,
            if (wide)
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: form),
                  const SizedBox(width: AppSpacing.medium),
                  Expanded(child: list),
                ],
              )
            else ...[
              form,
              const SizedBox(height: AppSpacing.large),
              list,
            ],
          ],
        ),
      ),
    );
    return Scaffold(
      key: const Key('matches-page'),
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: WoodBackground.isPaintedAbove(context)
            ? body
            : WoodBackground(child: body),
      ),
    );
  }
}

/// 頁首：獎盃方塊、「對局戰績」與說明，右邊重新整理最近的局。
class _Header extends ConsumerWidget {
  const _Header({required this.groupId, super.key});

  final String? groupId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final text = Theme.of(context).textTheme;
    return ThickCard(
      child: Padding(
        padding: matchCardInset,
        child: Row(
          children: [
            const MatchIconBox(icon: Icons.emoji_events_outlined),
            const SizedBox(width: AppSpacing.medium),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '對局戰績',
                    style: text.headlineSmall!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    '記錄每一局的回合與勝負，和朋友一起確認',
                    style: text.bodySmall!.copyWith(color: AppColors.inkMuted),
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.small),
            ThickIconButton(
              key: const Key('match-list-refresh'),
              tooltip: '重新整理',
              icon: const Icon(Icons.refresh, color: AppColors.ink),
              onPressed: () => ref.invalidate(matchListProvider(groupId)),
            ),
          ],
        ),
      ),
    );
  }
}

/// 從揪團進來時顯示的揪團名稱；讀取失敗時顯示錯誤與「重試」。
class _GroupHeader extends ConsumerWidget {
  const _GroupHeader({required this.groupId});

  final String groupId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final form = ref.watch(matchFormProvider);
    if (form.groupError case final error?) {
      return ThickCard(
        key: const Key('match-group-error'),
        child: Padding(
          padding: matchCardInset,
          child: MatchLoadError(
            error: error,
            prefix: '揪團載入失敗',
            retryKey: const Key('match-group-retry'),
            onRetry: () =>
                ref.read(matchFormProvider.notifier).loadGroup(groupId),
          ),
        ),
      );
    }
    if (form.group case final group?) {
      return ThickCard(
        key: const Key('match-group-title'),
        child: ListTile(
          leading: const Icon(Icons.groups_outlined),
          title: Text(group.title),
          subtitle: const Text('這個揪團的戰績'),
        ),
      );
    }
    return const LinearProgressIndicator();
  }
}

/// 用編號打開一局：輸入朋友傳來的編號，按「打開」。
class _OpenCard extends StatefulWidget {
  const _OpenCard({super.key});

  @override
  State<_OpenCard> createState() => _OpenCardState();
}

class _OpenCardState extends State<_OpenCard> {
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
    return ThickCard(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.small + AppSpacing.xSmall),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                key: const Key('match-open-id'),
                controller: _openId,
                decoration: const InputDecoration(
                  hintText: '局的編號（朋友傳來的）',
                  prefixIcon: Icon(Icons.tag),
                ),
                onSubmitted: (_) => _open(),
              ),
            ),
            const SizedBox(width: AppSpacing.small),
            ThickButton(
              buttonKey: const Key('match-open'),
              style: ThickStyle.dark,
              icon: Icons.arrow_forward,
              label: '打開',
              shadow: AppShadows.soft,
              onPressed: _open,
            ),
          ],
        ),
      ),
    );
  }
}

/// 開一局：遊戲、日期（今天／昨天／其他日期，預設今天）、自家或桌遊店、店家、我的座位。
class _MatchFormCard extends ConsumerStatefulWidget {
  const _MatchFormCard({required this.prefill, super.key});

  final MatchPrefill prefill;

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
    // 改 provider 不能在建立畫面的過程中做，等第一個畫面畫完再帶入
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (ref.read(matchFormProvider).playedOn == null) {
        _n.setPlayedOn(_today());
      }
      // 從揪團進來：讀取揪團，帶入店家、唯一的遊戲、日期與 group_id
      if (widget.prefill.groupId case final groupId?) _n.loadGroup(groupId);
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
    final text = Theme.of(context).textTheme;
    return ThickCard(
      child: Padding(
        padding: matchCardInset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const MatchIconBox(icon: Icons.add),
                const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '開一局新紀錄',
                        style: text.titleMedium!.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      Text(
                        '開局後就能記錄回合與結果',
                        style: text.bodySmall!.copyWith(
                          color: AppColors.inkMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.medium),
            const _FieldLabel('遊戲名稱'),
            games.when(
              loading: () => const LinearProgressIndicator(),
              error: (error, _) => MatchLoadError(
                error: error,
                prefix: '遊戲載入失敗',
                retryKey: const Key('match-games-retry'),
                onRetry: () => ref.invalidate(matchGameOptionsProvider),
              ),
              // 帶入的遊戲可能在選單建立後才設定；內層換 Key 讓選單跟著重建
              data: (options) => KeyedSubtree(
                key: const Key('match-game'),
                child: _gameField(options, form),
              ),
            ),
            const SizedBox(height: AppSpacing.medium),
            ..._restOfForm(form),
          ],
        ),
      ),
    );
  }

  Widget _gameField(List<GameRef> options, MatchFormState form) =>
      DropdownButtonFormField<int>(
        key: ValueKey(('game', form.gameId, options.length)),
        initialValue: options.any((g) => g.id == form.gameId)
            ? form.gameId
            : null,
        isExpanded: true,
        decoration: InputDecoration(
          hintText: '選擇遊戲',
          prefixIcon: const Icon(Icons.casino_outlined),
          errorText: form.errors['gameId'],
        ),
        items: [
          for (final game in options)
            DropdownMenuItem(value: game.id, child: Text(game.name)),
        ],
        onChanged: _n.setGameId,
      );

  List<Widget> _restOfForm(MatchFormState form) {
    final today = _today();
    final yesterday = today.subtract(const Duration(days: 1));
    final played = form.playedOn ?? today;
    bool same(DateTime a, DateTime b) =>
        a.year == b.year && a.month == b.month && a.day == b.day;
    final other = !same(played, today) && !same(played, yesterday);
    return [
      const _FieldLabel('日期'),
      Wrap(
        spacing: AppSpacing.small,
        runSpacing: AppSpacing.small,
        children: [
          _ChoicePill(
            key: const Key('match-date-today'),
            label: '今天',
            selected: same(played, today),
            onTap: () => _n.setPlayedOn(today),
          ),
          _ChoicePill(
            key: const Key('match-date-yesterday'),
            label: '昨天',
            selected: same(played, yesterday),
            onTap: () => _n.setPlayedOn(yesterday),
          ),
          _ChoicePill(
            key: const Key('match-date'),
            icon: Icons.calendar_today_outlined,
            label: other ? formatPlayedOn(played) : '其他日期',
            selected: other,
            onTap: _pickDate,
          ),
        ],
      ),
      FieldError(form.errors['playedOn']),
      const SizedBox(height: AppSpacing.medium),
      const _FieldLabel('地點'),
      _LocationTrack(selected: form.locationType, onSelect: _n.setLocationType),
      if (form.locationType == 'shop') ...[
        const SizedBox(height: AppSpacing.small),
        _ShopField(form: form),
      ],
      const SizedBox(height: AppSpacing.medium),
      const _FieldLabel('我的座位'),
      TextField(
        key: const Key('match-seat'),
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(
          hintText: '選填，不填給最小的空位',
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
      const SizedBox(height: AppSpacing.large),
      ThickButton(
        buttonKey: const Key('match-create'),
        style: ThickStyle.primary,
        icon: Icons.add_circle_outline,
        label: '立即開局',
        expand: true,
        onPressed: form.busy ? null : _n.submit,
      ),
    ];
  }
}

/// 欄位上方的小標。
class _FieldLabel extends StatelessWidget {
  const _FieldLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.small),
    child: Text(
      text,
      style: Theme.of(context).textTheme.labelLarge!.copyWith(
        color: AppColors.inkMuted,
        fontWeight: FontWeight.w600,
      ),
    ),
  );
}

/// 可以選的膠囊（日期快選）：選中的是深炭底白字。
class _ChoicePill extends StatelessWidget {
  const _ChoicePill({
    required this.label,
    required this.selected,
    required this.onTap,
    this.icon,
    super.key,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final foreground = selected ? AppColors.surface : AppColors.ink;
    return Material(
      color: selected ? AppColors.ink : AppColors.neutralTint,
      shape: const StadiumBorder(),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: AppSizes.minTouchTarget),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.medium),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon case final icon?) ...[
                  Icon(icon, size: AppSizes.inlineIcon, color: foreground),
                  const SizedBox(width: AppSpacing.small),
                ],
                Text(
                  label,
                  style: TextStyle(
                    color: foreground,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 自家／桌遊店：同一條米色軌道，選中的是浮起來的白色按鈕。
class _LocationTrack extends StatelessWidget {
  const _LocationTrack({required this.selected, required this.onSelect});

  final String selected;
  final ValueChanged<String> onSelect;

  Widget _segment(String value, IconData icon) {
    final on = value == selected;
    return Expanded(
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: on ? AppColors.surface : Colors.transparent,
          borderRadius: BorderRadius.circular(AppRadius.pill),
          boxShadow: on ? AppShadows.soft : null,
        ),
        child: Material(
          type: MaterialType.transparency,
          shape: const StadiumBorder(),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => onSelect(value),
            child: SizedBox(
              height: AppSizes.minTouchTarget - AppSpacing.small,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    icon,
                    size: AppSizes.inlineIcon,
                    color: on ? AppColors.primaryText : AppColors.inkMuted,
                  ),
                  const SizedBox(width: AppSpacing.small),
                  Text(
                    locationLabel(value),
                    key: Key('match-location-$value'),
                    style: TextStyle(
                      color: on ? AppColors.ink : AppColors.inkMuted,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xSmall),
      decoration: BoxDecoration(
        color: AppColors.neutralTint,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        children: [
          _segment('home', Icons.home_outlined),
          _segment('shop', Icons.storefront_outlined),
        ],
      ),
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
          // 帶入的店家可能在選單建立後才設定；內層換 Key 讓選單跟著重建
          : KeyedSubtree(
              key: const Key('match-shop'),
              child: _shopDropdown(ref, options),
            ),
    );
  }

  Widget _shopDropdown(WidgetRef ref, List<Shop> options) =>
      DropdownButtonFormField<String>(
        key: ValueKey(('shop', form.shopId, options.length)),
        initialValue: options.any((s) => s.id == form.shopId)
            ? form.shopId
            : null,
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
      );
}

/// 最近的局：標題條（筆數）與每一局一張卡片；載入中、失敗、沒有資料也各是一張卡片。
class _RecentList extends ConsumerWidget {
  const _RecentList({this.groupId, super.key});

  /// 不是 null 時只列這個揪團的局。
  final String? groupId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = matchListProvider(groupId);
    final recent = ref.watch(provider);
    final count = recent.isLoading ? null : recent.value?.length;
    Widget card(Widget child) => ThickCard(
      child: Padding(padding: matchCardInset, child: child),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionBar(
          key: const Key('match-list-header'),
          title: '最近的局',
          icon: Icons.history,
          trailing: count == null
              ? null
              : Text(
                  '最近 $count 局',
                  style: Theme.of(
                    context,
                  ).textTheme.bodyMedium!.copyWith(color: AppColors.inkMuted),
                ),
        ),
        const SizedBox(height: AppSpacing.medium),
        recent.when(
          skipLoadingOnRefresh: false,
          loading: () => card(const Center(child: CircularProgressIndicator())),
          error: (error, _) => card(
            MatchLoadError(
              error: error,
              retryKey: const Key('match-list-retry'),
              onRetry: () => ref.invalidate(provider),
            ),
          ),
          data: (items) => items.isEmpty
              ? card(const Text('還沒有任何一局，先開一局吧'))
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (final (i, m) in items.indexed) ...[
                      if (i > 0) const SizedBox(height: AppSpacing.medium),
                      _MatchListItem(key: Key('match-item-${m.id}'), match: m),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}

/// 最近的一局：遊戲圖示、名稱與狀態、日期地點人數，有結果時加上獲勝與我的結果；點整張打開。
class _MatchListItem extends ConsumerWidget {
  const _MatchListItem({required this.match, super.key});

  final GameMatch match;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final textTheme = Theme.of(context).textTheme;
    final winner = matchWinnerText(match);
    final mine = matchMyResultText(match, ref.watch(matchUserIdProvider));
    return ThickCard(
      onTap: () => context.go('/matches/${match.id}'),
      child: Padding(
        padding: matchCardInset,
        child: Row(
          children: [
            const MatchIconBox(
              icon: Icons.casino_outlined,
              color: AppColors.neutralTint,
              foreground: AppColors.ink,
            ),
            const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          match.game.name,
                          style: textTheme.titleMedium!.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.small),
                      PillBadge(
                        label: statusLabel(match.status),
                        tone: match.status == 'in_progress'
                            ? PillTone.duration
                            : PillTone.neutral,
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.xSmall),
                  Text(
                    '${formatPlayedOn(match.playedOn)}・'
                    '${matchLocationText(match)}・${match.participantCount} 人',
                    style: textTheme.bodyMedium!.copyWith(
                      color: AppColors.inkMuted,
                    ),
                  ),
                  if (winner != null || mine != null) ...[
                    const SizedBox(height: AppSpacing.small),
                    Wrap(
                      spacing: AppSpacing.small,
                      runSpacing: AppSpacing.small,
                      children: [
                        if (winner != null)
                          PillBadge(
                            label: winner,
                            tone: PillTone.accent,
                            icon: Icons.emoji_events_outlined,
                          ),
                        if (mine != null) PillBadge(label: mine),
                      ],
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.small),
            const Icon(Icons.chevron_right, color: AppColors.inkMuted),
          ],
        ),
      ),
    );
  }
}
