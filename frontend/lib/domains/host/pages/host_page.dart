import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/shell.dart';
import '../../../app/theme/app_colors.dart';
import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/thick_widgets.dart';
import '../../../app/theme/wood_background.dart';
import '../../../core/layout/breakpoints.dart';
import '../data/host_models.dart';
import '../state/host_controller.dart';
import '../state/host_labels.dart';

/// 提醒的字句（spec §14.5，草稿）。連線中顯示載入圖示，沒有字句。
String? hostNoticeText(HostNotice notice) => switch (notice) {
  HostNotice.paused => '主持暫停中',
  HostNotice.tapToResume => '點一下繼續',
  HostNotice.wakeLockDenied => '請關掉自動鎖定',
  HostNotice.takenOver => '已在別的裝置接著主持',
  HostNotice.reconnecting => '重新連線中',
  HostNotice.micDenied => '需要麥克風才能主持，請到瀏覽器設定允許',
  HostNotice.audioLocked => '點一下開啟聲音',
  HostNotice.unavailable => '主持人暫時連不上，請稍後再試',
  HostNotice.forbidden => '這場主持不是你開的',
  HostNotice.invalidPlayerCount => '人數要在 5 到 10 人',
  HostNotice.connecting => null,
};

/// 「可以這樣說」的八句語音指令（spec §5.1）。只是提示，不能點。
const hostVoiceHints = [
  '等一下',
  '暫停',
  '繼續',
  '下一步',
  '上一步',
  '結束了',
  '白薔薇贏了',
  '血刃贏了',
];

const _modeNames = {
  TurnTakingMode.auto: '自動接話',
  TurnTakingMode.pushToTalk: '按住說話',
};
const _modeIcons = {
  TurnTakingMode.auto: Icons.hearing,
  TurnTakingMode.pushToTalk: Icons.mic,
};
const _voiceNames = {HostVoice.male: '男聲', HostVoice.female: '女聲'};

/// 有厚度卡片的標準內距。
const _inset = EdgeInsets.all(AppSpacing.medium + AppSpacing.xSmall);

/// AI 語音主持（`/host`，Stitch 版面）：一個頁面的兩種樣子。
///
/// - 開主持前：人數、接話方式、聲線，「開始主持」或「接著主持／重新開始」。
/// - 主持中：頁首（遊戲與狀態）、提醒、自動接話時的「正在聽」、目前進度、接話方式、
///   可以這樣說、小提醒；流程鍵與按住說話鍵固定在畫面底部（筆電改成左右兩欄）。
///
/// 所有操作都只呼叫 `state/` 的 [HostController]（交接說明 `docs/handoff/host.md`）。
/// 主持中藏起手機的底部導覽列：流程鍵在底部，擠在一起容易按錯，誤點到別頁也會中斷收音。
class HostPage extends ConsumerStatefulWidget {
  const HostPage({super.key});

  @override
  ConsumerState<HostPage> createState() => _HostPageState();
}

class _HostPageState extends ConsumerState<HostPage> {
  late final HideBottomNavigation _navigation;

  @override
  void initState() {
    super.initState();
    _navigation = ref.read(hideBottomNavigationProvider.notifier);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(hostControllerProvider.notifier).load();
    });
  }

  @override
  void dispose() {
    // 離開頁面：還原導覽列（等這一輪畫面處理完再改，避免在拆畫面時重建外框）
    Future.microtask(_navigation.reset);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(
      hostControllerProvider.select((s) => s.isLive),
      (_, live) => _navigation.set(live),
    );
    final state = ref.watch(hostControllerProvider);
    final controller = ref.read(hostControllerProvider.notifier);
    final hosting = state.isLive && state.live != null;
    final notices = state.notices.isEmpty
        ? null
        : _Notices(state: state, controller: controller);
    final body = LayoutBuilder(
      builder: (context, constraints) {
        final wide =
            screenSizeForWidth(constraints.maxWidth) == ScreenSize.desktop;
        final bottomInset = MediaQuery.paddingOf(context).bottom;
        final layout = hosting
            ? _HostingLayout(
                state: state,
                controller: controller,
                notices: notices,
                wide: wide,
              )
            : null;
        final bottomBar = layout?.bottomBar();
        return Column(
          children: [
            Expanded(
              child: ListView(
                padding: EdgeInsets.fromLTRB(
                  AppSpacing.medium,
                  AppSpacing.medium,
                  AppSpacing.medium,
                  AppSpacing.medium + (bottomBar == null ? bottomInset : 0),
                ),
                children: [
                  if (layout != null)
                    layout.body()
                  else
                    _Setup(
                      state: state,
                      controller: controller,
                      notices: notices,
                    ),
                ],
              ),
            ),
            ?bottomBar,
          ],
        );
      },
    );
    return Scaffold(
      key: const Key('host-page'),
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('語音主持'),
        // 放在木紋上，用半透明白底，文字才看得清楚
        backgroundColor: AppColors.headerGlass,
        // 「結束主持」放在標題列，離流程鍵最遠，按「下一步」時不會誤按；
        // 不再確認（30 分鐘內可以接著主持）
        actions: [
          if (state.showFlowControls)
            Padding(
              padding: const EdgeInsets.only(right: AppSpacing.small),
              child: TextButton.icon(
                key: const Key('host-end'),
                style: TextButton.styleFrom(foregroundColor: AppColors.error),
                onPressed: controller.end,
                icon: const Icon(Icons.stop_circle_outlined),
                label: const Text('結束主持'),
              ),
            ),
        ],
      ),
      body: WoodBackground.isPaintedAbove(context)
          ? body
          : WoodBackground(child: body),
    );
  }
}

/// 提醒（spec §14.5），可能同時有好幾個。依「玩家要不要處理」分成三種：
/// 要玩家點一下的是大按鈕、擋住主持的是橫幅、只是告知的是一行。
class _Notices extends StatelessWidget {
  const _Notices({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      spacing: AppSpacing.small,
      children: [for (final notice in state.notices) _notice(context, notice)],
    );
  }

  Widget _notice(BuildContext context, HostNotice notice) {
    final text = hostNoticeText(notice);
    return switch (notice) {
      HostNotice.connecting => const Padding(
        key: Key('host-connecting'),
        padding: EdgeInsets.all(AppSpacing.small),
        child: Center(child: CircularProgressIndicator()),
      ),
      // 要玩家點一下：整顆大按鈕都可以點
      HostNotice.tapToResume => ThickButton(
        style: ThickStyle.primary,
        expand: true,
        icon: Icons.touch_app,
        label: text!,
        onPressed: controller.tapToResume,
      ),
      HostNotice.audioLocked => ThickButton(
        style: ThickStyle.primary,
        expand: true,
        icon: Icons.volume_up,
        label: text!,
        onPressed: controller.unlockAudio,
      ),
      // 擋住主持：流程停住或主持不能繼續
      HostNotice.paused => _Banner(
        notice: notice,
        icon: Icons.pause_circle,
        title: text!,
        subtitle: '暫停中也可以問規則',
        warning: true,
      ),
      HostNotice.micDenied ||
      HostNotice.unavailable ||
      HostNotice.takenOver ||
      HostNotice.forbidden ||
      HostNotice.invalidPlayerCount => _Banner(
        notice: notice,
        icon: Icons.error_outline,
        title: text!,
      ),
      // 只是告知：不擋主持
      HostNotice.wakeLockDenied || HostNotice.reconnecting => _Line(
        notice: notice,
        icon: notice == HostNotice.reconnecting
            ? Icons.sync
            : Icons.info_outline,
        text: text!,
      ),
    };
  }
}

/// 擋住主持的提醒：琥珀色（暫停）或紅色（錯誤）的橫幅。
class _Banner extends StatelessWidget {
  const _Banner({
    required this.notice,
    required this.icon,
    required this.title,
    this.subtitle,
    this.warning = false,
  });

  final HostNotice notice;
  final IconData icon;
  final String title;
  final String? subtitle;
  final bool warning;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final color = warning ? AppColors.amberText : AppColors.error;
    return Container(
      key: ValueKey('host-banner-${notice.name}'),
      padding: const EdgeInsets.all(AppSpacing.medium),
      decoration: BoxDecoration(
        color: warning ? AppColors.amberTint : AppColors.errorTint,
        border: Border.all(
          color: warning ? AppColors.amber : AppColors.errorEdge,
        ),
        borderRadius: BorderRadius.circular(AppRadius.card),
      ),
      child: Row(
        children: [
          Icon(icon, color: color),
          const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: text.titleMedium!.copyWith(
                    color: color,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (subtitle case final subtitle?)
                  Text(subtitle, style: text.bodyMedium),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 只是告知的一行：放在白底膠囊上（木紋上的文字一律放在白底上）。
class _Line extends StatelessWidget {
  const _Line({required this.notice, required this.icon, required this.text});

  final HostNotice notice;
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: ValueKey('host-line-${notice.name}'),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.medium,
        vertical: AppSpacing.small,
      ),
      decoration: BoxDecoration(
        color: AppColors.surfaceGlass,
        border: Border.all(color: AppColors.cardEdge),
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        children: [
          Icon(icon, size: AppSizes.inlineIcon, color: AppColors.inkMuted),
          const SizedBox(width: AppSpacing.small),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}

/// 一個有標題的厚卡片區塊。
class _Section extends StatelessWidget {
  const _Section({
    super.key,
    required this.title,
    required this.child,
    this.icon,
    this.footnote,
  });

  final String title;
  final IconData? icon;
  final Widget child;
  final String? footnote;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return ThickCard(
      child: Padding(
        padding: _inset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                if (icon case final icon?) ...[
                  Icon(icon, color: AppColors.primaryText),
                  const SizedBox(width: AppSpacing.small),
                ],
                Expanded(
                  child: Text(
                    title,
                    style: text.titleMedium!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
            child,
            if (footnote case final footnote?) ...[
              const SizedBox(height: AppSpacing.small),
              Text(
                footnote,
                style: text.bodySmall!.copyWith(color: AppColors.inkMuted),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 同一條米色軌道上的分段按鍵，選中的是浮起來的白色按鈕。
class _Track<T> extends StatelessWidget {
  const _Track({
    super.key,
    required this.values,
    required this.selected,
    required this.label,
    required this.keyOf,
    required this.onSelect,
    this.icon,
  });

  final List<T> values;
  final T selected;
  final String Function(T) label;
  final String Function(T) keyOf;
  final IconData Function(T)? icon;
  final ValueChanged<T> onSelect;

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
          for (final value in values)
            Expanded(child: _segment(context, value, value == selected)),
        ],
      ),
    );
  }

  Widget _segment(BuildContext context, T value, bool on) {
    return DecoratedBox(
      key: Key(keyOf(value)),
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
            height: AppSizes.minTouchTarget,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icon case final icon?) ...[
                  Icon(
                    icon(value),
                    size: AppSizes.inlineIcon,
                    color: on ? AppColors.primaryText : AppColors.inkMuted,
                  ),
                  const SizedBox(width: AppSpacing.small),
                ],
                Text(
                  label(value),
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
    );
  }
}

/// 開主持前：說明卡、人數、接話方式、聲線，最後是「開始主持」或「接著主持／重新開始」。
/// 寬螢幕也只用手機寬度，置中，不把設定拉滿整個畫面。
class _Setup extends StatelessWidget {
  const _Setup({
    required this.state,
    required this.controller,
    required this.notices,
  });

  final HostState state;
  final HostController controller;
  final Widget? notices;

  @override
  Widget build(BuildContext context) {
    final busy = state.connection == HostConnectionStatus.connecting;
    final text = Theme.of(context).textTheme;
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: mobileMaxWidth),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          spacing: AppSpacing.medium,
          children: [
            ThickCard(
              key: const Key('host-setup-header'),
              child: Padding(
                padding: _inset,
                child: Row(
                  children: [
                    const _IconBox(icon: Icons.record_voice_over),
                    const SizedBox(width: AppSpacing.medium),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '《$hostGameName》',
                            style: text.titleLarge!.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          Text(
                            'AI 主持人帶大家玩，有規則問題直接問',
                            style: text.bodySmall!.copyWith(
                              color: AppColors.inkMuted,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            ?notices,
            _Section(
              key: const Key('host-section-player-count'),
              icon: Icons.groups,
              title: '人數（5 到 10 人）',
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                spacing: AppSpacing.large,
                children: [
                  ThickIconButton(
                    key: const Key('host-player-count-minus'),
                    tooltip: '少一人',
                    onPressed: () =>
                        controller.setPlayerCount(state.playerCount - 1),
                    icon: const Icon(Icons.remove, color: AppColors.ink),
                  ),
                  Text(
                    '${state.playerCount}',
                    key: const Key('host-player-count'),
                    style: text.headlineMedium!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  ThickIconButton(
                    key: const Key('host-player-count-plus'),
                    tooltip: '多一人',
                    onPressed: () =>
                        controller.setPlayerCount(state.playerCount + 1),
                    icon: const Icon(Icons.add, color: AppColors.ink),
                  ),
                ],
              ),
            ),
            _Section(
              key: const Key('host-section-setup-mode'),
              icon: Icons.record_voice_over,
              title: '接話方式',
              footnote: '主持中也可以切換',
              child: _Track<TurnTakingMode>(
                key: const Key('host-mode-track'),
                values: TurnTakingMode.values,
                selected: state.turnTakingMode,
                label: (m) => _modeNames[m]!,
                icon: (m) => _modeIcons[m]!,
                keyOf: (m) => 'host-mode-${m.name}',
                onSelect: controller.setTurnTakingMode,
              ),
            ),
            _Section(
              key: const Key('host-section-setup-voice'),
              icon: Icons.graphic_eq,
              title: '聲線',
              footnote: '開始後這場主持不能換',
              child: _Track<HostVoice>(
                values: HostVoice.values,
                selected: state.voice,
                label: (v) => _voiceNames[v]!,
                keyOf: (v) => 'host-voice-${v.name}',
                onSelect: controller.setVoice,
              ),
            ),
            if (state.canResume)
              _ResumeButtons(state: state, controller: controller)
            else
              ThickButton(
                buttonKey: const Key('host-start'),
                style: ThickStyle.primary,
                expand: true,
                icon: Icons.play_arrow,
                label: '開始主持',
                onPressed: busy ? null : controller.start,
              ),
          ],
        ),
      ),
    );
  }
}

/// 圓角方塊裡的圖示。
class _IconBox extends StatelessWidget {
  const _IconBox({required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) => Container(
    width: AppSizes.entryIconBox,
    height: AppSizes.entryIconBox,
    decoration: BoxDecoration(
      color: AppColors.primaryTint,
      borderRadius: BorderRadius.circular(AppRadius.button),
    ),
    child: Icon(icon, color: AppColors.primaryText),
  );
}

/// 「接著主持（第 N 回合某階段）」「重新開始」：有保留的主持時才出現，已結束的也算。
class _ResumeButtons extends StatelessWidget {
  const _ResumeButtons({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      spacing: AppSpacing.small,
      children: [
        ThickButton(
          buttonKey: const Key('host-resume'),
          style: ThickStyle.primary,
          expand: true,
          icon: Icons.play_arrow,
          label: state.resumeLabel ?? '接著主持',
          onPressed: controller.resume,
        ),
        ThickButton(
          buttonKey: const Key('host-restart'),
          style: ThickStyle.light,
          expand: true,
          icon: Icons.restart_alt,
          label: '重新開始',
          shadow: AppShadows.soft,
          onPressed: controller.restart,
        ),
      ],
    );
  }
}

/// 主持中的排版。按鍵放在提醒與進度改變時都不會被推動的位置，避免連按時按空：
/// - 手機與平板：內容由上往下是頁首、提醒、正在聽、進度、主持人的狀態、接話方式、
///   可以這樣說、小提醒；流程鍵（與按住說話鍵）固定在畫面底部，伸手就按得到。
/// - 筆電：左欄頁首、提醒、進度與主持人的狀態；右欄接話方式、流程鍵、
///   按住說話鍵或正在聽、可以這樣說、小提醒。
class _HostingLayout {
  const _HostingLayout({
    required this.state,
    required this.controller,
    required this.notices,
    required this.wide,
  });

  final HostState state;
  final HostController controller;
  final Widget? notices;
  final bool wide;

  bool get _auto => state.turnTakingMode == TurnTakingMode.auto;

  List<Widget> get _status => [
    _Header(state: state),
    ?notices,
    if (!wide && _auto) const _Listening(),
    _Progress(state: state),
    if (state.lookingUp)
      const ThickCard(
        key: Key('host-section-host-status'),
        child: ListTile(
          leading: Icon(Icons.menu_book, color: AppColors.primaryText),
          title: Text('正在查規則'),
        ),
      ),
    // 這一局結束後，「接著主持」「重新開始」接在進度下面
    if (state.canResume) _ResumeButtons(state: state, controller: controller),
  ];

  Widget get _mode => ThickCard(
    key: const Key('host-section-mode'),
    child: Padding(
      padding: _inset,
      child: Row(
        children: [
          Icon(_modeIcons[state.turnTakingMode], color: AppColors.primaryText),
          const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('接話方式'),
                Text(
                  _modeNames[state.turnTakingMode]!,
                  key: const Key('host-mode-label'),
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ],
            ),
          ),
          ThickButton(
            buttonKey: const Key('host-switch-mode'),
            style: ThickStyle.light,
            label: '切換',
            shadow: AppShadows.soft,
            onPressed: controller.switchTurnTakingMode,
          ),
        ],
      ),
    ),
  );

  Widget? get _talk => state.showTalkButton
      ? Center(
          child: _TalkButton(state: state, controller: controller),
        )
      : null;

  Widget body() {
    if (!wide) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        spacing: AppSpacing.medium,
        children: [..._status, _mode, const _VoiceHints(), const _Tip()],
      );
    }
    return Row(
      key: const Key('host-wide-layout'),
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: AppSpacing.medium,
      children: [
        Expanded(
          child: Column(
            key: const Key('host-column-status'),
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: AppSpacing.medium,
            children: _status,
          ),
        ),
        Expanded(
          child: Column(
            key: const Key('host-column-controls'),
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: AppSpacing.medium,
            children: [
              _mode,
              if (state.showFlowControls)
                ThickCard(
                  child: Padding(
                    padding: _inset,
                    child: _FlowButtons(state: state, controller: controller),
                  ),
                ),
              // 按住說話鍵（或正在聽）放在流程鍵下面：切換接話方式時流程鍵不移位
              ?_talk,
              if (_auto) const _Listening(),
              const _VoiceHints(),
              const _Tip(),
            ],
          ),
        ),
      ],
    );
  }

  /// 手機與平板固定在畫面底部的按鍵；筆電沒有。
  Widget? bottomBar() {
    if (wide) return null;
    // 這一局已經結束：流程鍵收起來；按住說話時還留著按住說話鍵，可以照常問規則
    if (!state.showFlowControls && _talk == null) return null;
    return Container(
      decoration: BoxDecoration(
        color: AppColors.navGlass,
        border: const Border(top: BorderSide(color: AppColors.cardEdge)),
        boxShadow: AppShadows.floating,
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.medium),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: AppSpacing.medium,
            children: [
              ?_talk,
              if (state.showFlowControls)
                _FlowButtons(state: state, controller: controller),
            ],
          ),
        ),
      ),
    );
  }
}

/// 主持中的頁首：遊戲名稱與主持人的狀態膠囊（聆聽中、暫停中、查規則中、連線中、已結束）。
class _Header extends StatelessWidget {
  const _Header({required this.state});

  final HostState state;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final (
      label,
      color,
      background,
    ) = state.connection == HostConnectionStatus.reconnecting
        ? ('連線中', AppColors.amberText, AppColors.amberTint)
        : state.ended
        ? ('已結束', AppColors.inkMuted, AppColors.neutralTint)
        : state.paused
        ? ('暫停中', AppColors.amberText, AppColors.amberTint)
        : state.lookingUp
        ? ('查規則中', AppColors.primaryText, AppColors.primaryTint)
        : ('聆聽中', AppColors.sage, AppColors.sageTint);
    return ThickCard(
      key: const Key('host-header'),
      child: Padding(
        padding: _inset,
        child: Row(
          children: [
            const _IconBox(icon: Icons.record_voice_over),
            const SizedBox(width: AppSpacing.medium),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    hostGameName,
                    style: text.titleMedium!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    'AI 主持人帶大家玩',
                    style: text.bodySmall!.copyWith(color: AppColors.inkMuted),
                  ),
                ],
              ),
            ),
            Container(
              key: const Key('host-status'),
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.small + AppSpacing.xSmall,
                vertical: AppSpacing.xSmall,
              ),
              decoration: BoxDecoration(
                color: background,
                borderRadius: BorderRadius.circular(AppRadius.pill),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: AppSizes.sectionDot,
                    height: AppSizes.sectionDot,
                    decoration: BoxDecoration(
                      color: color,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.xSmall + AppSpacing.xSmall),
                  Text(
                    label,
                    style: text.labelLarge!.copyWith(
                      color: color,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 自動接話時的「正在聽」：橘色大圓與一句說明。只是告訴玩家可以直接說，不能按。
class _Listening extends StatelessWidget {
  const _Listening();

  @override
  Widget build(BuildContext context) {
    return ThickCard(
      key: const Key('host-listening'),
      child: Padding(
        padding: _inset,
        child: Column(
          children: [
            Container(
              width: AppSizes.talkButton,
              height: AppSizes.talkButton,
              alignment: Alignment.center,
              decoration: const BoxDecoration(
                color: AppColors.primaryTint,
                shape: BoxShape.circle,
              ),
              child: Container(
                width: AppSizes.talkButton - AppSpacing.xLarge,
                height: AppSizes.talkButton - AppSpacing.xLarge,
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  shape: BoxShape.circle,
                  boxShadow: AppShadows.raised,
                ),
                child: const Icon(
                  Icons.mic,
                  color: AppColors.surface,
                  size: AppSizes.talkIcon,
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.small + AppSpacing.xSmall),
            Text(
              '直接說話，主持人會回答',
              style: Theme.of(
                context,
              ).textTheme.titleSmall!.copyWith(fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
    );
  }
}

/// 目前進度：整頁最醒目。回合內是第幾回合（最大字）與三個階段（進行中的較大）；
/// 開場到夜晚是節點名稱。
class _Progress extends StatelessWidget {
  const _Progress({required this.state});

  final HostState state;

  @override
  Widget build(BuildContext context) {
    final live = state.live!;
    final turnNumber = live.turnNumber;
    final phaseNumber = live.phaseNumber;
    final inTurn = turnNumber != null && phaseNumber != null;
    final text = Theme.of(context).textTheme;
    final big = text.headlineLarge!.copyWith(fontWeight: FontWeight.w700);
    return ThickCard(
      key: const Key('host-section-progress'),
      child: Padding(
        padding: _inset,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '目前進度',
              style: text.labelLarge!.copyWith(color: AppColors.inkMuted),
            ),
            const SizedBox(height: AppSpacing.small),
            if (inTurn) ...[
              Text('第 $turnNumber 回合', style: big),
              const SizedBox(height: AppSpacing.small),
              for (final phase in hostPhaseNames.keys)
                _PhaseRow(phase: phase, current: phaseNumber),
            ] else
              Text(
                hostProgressLabel(live.step, turnNumber, phaseNumber),
                style: big,
              ),
            // 這一局已經結束：保留結束前的進度，下面另有「接著主持」「重新開始」
            if (state.ended) ...[
              const SizedBox(height: AppSpacing.small),
              const Row(
                children: [
                  Icon(Icons.flag, color: AppColors.inkMuted),
                  SizedBox(width: AppSpacing.small),
                  Text('這一局已經結束'),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 一個階段：已完成（綠）、進行中（橘底，字較大）、還沒到（灰）。
class _PhaseRow extends StatelessWidget {
  const _PhaseRow({required this.phase, required this.current});

  final int phase;
  final int current;

  @override
  Widget build(BuildContext context) {
    final (status, icon, label, color) = phase < current
        ? ('done', Icons.check_circle, '已完成', AppColors.sage)
        : phase == current
        ? ('current', Icons.radio_button_checked, '進行中', AppColors.primary)
        : ('upcoming', Icons.radio_button_unchecked, '還沒到', AppColors.inkMuted);
    final isCurrent = phase == current;
    final text = Theme.of(context).textTheme;
    return Container(
      key: Key('host-phase-$phase-$status'),
      margin: const EdgeInsets.only(top: AppSpacing.xSmall),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.small + AppSpacing.xSmall,
        vertical: AppSpacing.small,
      ),
      decoration: BoxDecoration(
        color: isCurrent ? AppColors.primaryTint : null,
        borderRadius: BorderRadius.circular(AppRadius.button),
      ),
      child: Row(
        children: [
          Icon(icon, color: color),
          const SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
          Expanded(
            child: Text(
              hostPhaseNames[phase]!,
              style: isCurrent
                  ? text.titleLarge!.copyWith(fontWeight: FontWeight.w700)
                  : text.bodyLarge,
            ),
          ),
          Text(label, style: text.bodySmall!.copyWith(color: color)),
        ],
      ),
    );
  }
}

/// 「上一步」「暫停／繼續」「下一步」：同一列、一樣大的厚按鈕，「下一步」是主色。
class _FlowButtons extends StatelessWidget {
  const _FlowButtons({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    return Row(
      key: const Key('host-section-flow'),
      spacing: AppSpacing.small,
      children: [
        Expanded(
          child: ThickButton(
            buttonKey: const Key('host-previous'),
            style: ThickStyle.light,
            expand: true,
            label: '上一步',
            shadow: AppShadows.soft,
            onPressed: controller.previous,
          ),
        ),
        Expanded(
          child: ThickButton(
            buttonKey: const Key('host-pause'),
            style: ThickStyle.dark,
            expand: true,
            label: pauseButtonLabel(state),
            shadow: AppShadows.soft,
            onPressed: controller.togglePause,
          ),
        ),
        Expanded(
          child: ThickButton(
            buttonKey: const Key('host-next'),
            style: ThickStyle.primary,
            expand: true,
            label: '下一步',
            shadow: AppShadows.soft,
            onPressed: controller.next,
          ),
        ),
      ],
    );
  }
}

/// 「按住說話」橘色大圓：只在按住說話時出現。按下送 down，放開送 up；按著時顏色變深。
class _TalkButton extends StatelessWidget {
  const _TalkButton({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    final held = state.talkHeld;
    return Listener(
      onPointerDown: (_) => controller.talkDown(),
      onPointerUp: (_) => controller.talkUp(),
      onPointerCancel: (_) => controller.talkUp(),
      child: Container(
        key: const Key('host-talk'),
        width: AppSizes.talkButton,
        height: AppSizes.talkButton,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: held ? AppColors.primaryText : AppColors.primary,
          shape: BoxShape.circle,
          border: Border.all(
            color: AppColors.primaryTint,
            width: held ? AppSpacing.small : AppSpacing.xSmall,
          ),
          boxShadow: held ? AppShadows.card : AppShadows.raised,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          spacing: AppSpacing.small,
          children: [
            Icon(
              held ? Icons.mic : Icons.mic_none,
              size: AppSizes.talkIcon,
              color: AppColors.surface,
            ),
            Text(
              held ? '放開後主持人回答' : '按住說話',
              style: const TextStyle(
                color: AppColors.surface,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 「可以這樣說」：八句語音指令，每句一張小卡（兩欄）。只是提示，不能點。
class _VoiceHints extends StatelessWidget {
  const _VoiceHints();

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return _Section(
      key: const Key('host-section-voice-hints'),
      icon: Icons.lightbulb_outline,
      title: '可以這樣說',
      child: LayoutBuilder(
        builder: (context, constraints) {
          const gap = AppSpacing.small;
          final width = (constraints.maxWidth - gap) / 2;
          return Wrap(
            key: const Key('host-voice-hints'),
            spacing: gap,
            runSpacing: gap,
            children: [
              for (final (i, phrase) in hostVoiceHints.indexed)
                Container(
                  key: ValueKey('host-hint-$i'),
                  width: width,
                  padding: const EdgeInsets.all(
                    AppSpacing.small + AppSpacing.xSmall,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.backgroundAlt,
                    border: Border.all(color: AppColors.cardEdge),
                    borderRadius: BorderRadius.circular(AppRadius.button),
                  ),
                  child: Text(
                    '「$phrase」',
                    style: text.bodyLarge!.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

/// 底部的一句小提醒。
class _Tip extends StatelessWidget {
  const _Tip();

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const Key('host-tip'),
      padding: const EdgeInsets.all(AppSpacing.medium),
      decoration: BoxDecoration(
        color: AppColors.surfaceGlass,
        border: Border.all(color: AppColors.cardEdge),
        borderRadius: BorderRadius.circular(AppRadius.card),
      ),
      child: const Row(
        children: [
          Icon(Icons.tips_and_updates_outlined, color: AppColors.amber),
          SizedBox(width: AppSpacing.small + AppSpacing.xSmall),
          Expanded(child: Text('有規則問題就直接問主持人，暫停中也可以問')),
        ],
      ),
    );
  }
}
