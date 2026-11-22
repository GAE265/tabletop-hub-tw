import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/layout/breakpoints.dart';
import '../../domains/host/data/host_models.dart';
import '../../domains/host/state/host_controller.dart';
import '../../domains/host/state/host_labels.dart';

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

// 排版用的間距只有這兩種；顏色、字型、字級一律用預設主題。
const double _gap = 16;
const double _smallGap = 8;

/// 主要按鍵與流程鍵的高度：圍桌時伸手也好按（觸控目標至少 48）。
const double _bigButtonHeight = 56;
final _bigFilled = FilledButton.styleFrom(
  minimumSize: const Size.fromHeight(_bigButtonHeight),
);
final _bigOutlined = OutlinedButton.styleFrom(
  minimumSize: const Size.fromHeight(_bigButtonHeight),
);

/// AI 語音主持的參考畫面（spec §14.4）：一個頁面的幾種狀態。
///
/// 只用 Flutter 預設元件，不套主題；只整理分區與排版。筆電寬度（桌機斷點）改成左右兩欄：
/// 左邊看進度，右邊按鍵。所有操作都只呼叫 `state/` 的方法；
/// 正式頁面由永傑依交接說明 `docs/handoff/host.md` 製作。
class HostProtoPage extends ConsumerStatefulWidget {
  const HostProtoPage({super.key});

  @override
  ConsumerState<HostProtoPage> createState() => _HostProtoPageState();
}

class _HostProtoPageState extends ConsumerState<HostProtoPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(hostControllerProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(hostControllerProvider);
    final controller = ref.read(hostControllerProvider.notifier);
    final hosting = state.isLive && state.live != null;
    return Scaffold(
      appBar: AppBar(title: const Text('語音主持')),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final wide =
              screenSizeForWidth(constraints.maxWidth) == ScreenSize.desktop;
          return ListView(
            padding: const EdgeInsets.all(_gap),
            children: [
              if (state.notices.isNotEmpty) ...[
                _Notices(state: state, controller: controller),
                const SizedBox(height: _gap),
              ],
              if (hosting)
                _Hosting(state: state, controller: controller, wide: wide)
              else
                _Setup(state: state, controller: controller),
            ],
          );
        },
      ),
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
      spacing: _smallGap,
      children: [for (final notice in state.notices) _notice(context, notice)],
    );
  }

  Widget _notice(BuildContext context, HostNotice notice) {
    final text = hostNoticeText(notice);
    return switch (notice) {
      HostNotice.connecting => const Padding(
        key: Key('host-connecting'),
        padding: EdgeInsets.all(_smallGap),
        child: Center(child: CircularProgressIndicator()),
      ),
      // 要玩家點一下：整顆大按鈕都可以點
      HostNotice.tapToResume => FilledButton.icon(
        style: _bigFilled,
        onPressed: controller.tapToResume,
        icon: const Icon(Icons.touch_app),
        label: Text(text!),
      ),
      HostNotice.audioLocked => FilledButton.icon(
        style: _bigFilled,
        onPressed: controller.unlockAudio,
        icon: const Icon(Icons.volume_up),
        label: Text(text!),
      ),
      // 擋住主持：流程停住或主持不能繼續
      HostNotice.paused => _Banner(
        icon: Icons.pause_circle,
        title: text!,
        subtitle: '暫停中也可以問規則',
      ),
      HostNotice.micDenied ||
      HostNotice.unavailable ||
      HostNotice.takenOver ||
      HostNotice.forbidden ||
      HostNotice.invalidPlayerCount => _Banner(
        icon: Icons.error_outline,
        title: text!,
      ),
      // 只是告知：不擋主持
      HostNotice.wakeLockDenied || HostNotice.reconnecting => ListTile(
        dense: true,
        leading: Icon(
          notice == HostNotice.reconnecting ? Icons.sync : Icons.info_outline,
        ),
        title: Text(text!),
      ),
    };
  }
}

/// 擋住主持的提醒。這些狀況沒有橫幅上的動作（「接著主持」「繼續」在下面的按鍵），
/// 但 MaterialBanner 一定要有 actions，所以放一個空的。
class _Banner extends StatelessWidget {
  const _Banner({required this.icon, required this.title, this.subtitle});

  final IconData icon;
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return MaterialBanner(
      leading: Icon(icon),
      content: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(title, style: textTheme.titleMedium),
          if (subtitle != null) Text(subtitle!),
        ],
      ),
      actions: const [SizedBox.shrink()],
    );
  }
}

/// 一個有標題的區塊（Card）。
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
    final textTheme = Theme.of(context).textTheme;
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(_gap),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              spacing: _smallGap,
              children: [
                if (icon != null) Icon(icon),
                Text(title, style: textTheme.titleMedium),
              ],
            ),
            const SizedBox(height: _smallGap),
            child,
            if (footnote != null) ...[
              const SizedBox(height: _smallGap),
              Text(footnote!, style: textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

/// 開主持前：人數、接話方式、聲線，最後是「開始主持」或「接著主持／重新開始」。
/// 寬螢幕也只用手機寬度，置中，不把設定拉滿整個畫面。
class _Setup extends StatelessWidget {
  const _Setup({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    final busy = state.connection == HostConnectionStatus.connecting;
    final textTheme = Theme.of(context).textTheme;
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: mobileMaxWidth),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          spacing: _gap,
          children: [
            Text('《血與刃的白薔薇》', style: textTheme.titleLarge),
            _Section(
              key: const Key('host-section-player-count'),
              icon: Icons.groups,
              title: '人數（5 到 10 人）',
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                spacing: _gap,
                children: [
                  IconButton.outlined(
                    key: const Key('host-player-count-minus'),
                    tooltip: '少一人',
                    onPressed: () =>
                        controller.setPlayerCount(state.playerCount - 1),
                    icon: const Icon(Icons.remove),
                  ),
                  Text(
                    '${state.playerCount}',
                    key: const Key('host-player-count'),
                    style: textTheme.headlineMedium,
                  ),
                  IconButton.outlined(
                    key: const Key('host-player-count-plus'),
                    tooltip: '多一人',
                    onPressed: () =>
                        controller.setPlayerCount(state.playerCount + 1),
                    icon: const Icon(Icons.add),
                  ),
                ],
              ),
            ),
            _Section(
              key: const Key('host-section-setup-mode'),
              icon: Icons.record_voice_over,
              title: '接話方式',
              footnote: '主持中也可以切換',
              child: SegmentedButton<TurnTakingMode>(
                expandedInsets: EdgeInsets.zero,
                segments: [
                  for (final mode in TurnTakingMode.values)
                    ButtonSegment(
                      value: mode,
                      icon: Icon(_modeIcons[mode]),
                      label: Text(_modeNames[mode]!),
                    ),
                ],
                selected: {state.turnTakingMode},
                onSelectionChanged: (modes) =>
                    controller.setTurnTakingMode(modes.single),
              ),
            ),
            _Section(
              key: const Key('host-section-setup-voice'),
              icon: Icons.graphic_eq,
              title: '聲線',
              footnote: '開始後這場主持不能換',
              child: SegmentedButton<HostVoice>(
                expandedInsets: EdgeInsets.zero,
                segments: [
                  for (final voice in HostVoice.values)
                    ButtonSegment(
                      value: voice,
                      label: Text(_voiceNames[voice]!),
                    ),
                ],
                selected: {state.voice},
                onSelectionChanged: (voices) =>
                    controller.setVoice(voices.single),
              ),
            ),
            if (state.canResume)
              _ResumeButtons(state: state, controller: controller)
            else
              FilledButton.icon(
                key: const Key('host-start'),
                style: _bigFilled,
                onPressed: busy ? null : controller.start,
                icon: const Icon(Icons.play_arrow),
                label: const Text('開始主持'),
              ),
          ],
        ),
      ),
    );
  }
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
      spacing: _smallGap,
      children: [
        FilledButton.icon(
          key: const Key('host-resume'),
          style: _bigFilled,
          onPressed: controller.resume,
          icon: const Icon(Icons.play_arrow),
          label: Text(state.resumeLabel ?? '接著主持'),
        ),
        OutlinedButton.icon(
          key: const Key('host-restart'),
          onPressed: controller.restart,
          icon: const Icon(Icons.restart_alt),
          label: const Text('重新開始'),
        ),
      ],
    );
  }
}

/// 主持中。手機與平板由上往下：進度、主持人的狀態、接話方式、流程鍵、可以這樣說、結束主持。
/// 筆電分左右兩欄：左欄進度與主持人的狀態，右欄其餘的按鍵與提示。
class _Hosting extends StatelessWidget {
  const _Hosting({
    required this.state,
    required this.controller,
    required this.wide,
  });

  final HostState state;
  final HostController controller;
  final bool wide;

  @override
  Widget build(BuildContext context) {
    final status = [
      _Progress(state: state),
      if (state.lookingUp)
        const Card(
          key: Key('host-section-host-status'),
          margin: EdgeInsets.zero,
          child: ListTile(leading: Icon(Icons.menu_book), title: Text('正在查規則')),
        ),
    ];
    final controls = [
      if (state.canResume) _ResumeButtons(state: state, controller: controller),
      Card(
        key: const Key('host-section-mode'),
        margin: EdgeInsets.zero,
        child: ListTile(
          leading: Icon(_modeIcons[state.turnTakingMode]),
          title: const Text('接話方式'),
          subtitle: Text(
            _modeNames[state.turnTakingMode]!,
            key: const Key('host-mode-label'),
          ),
          trailing: OutlinedButton(
            key: const Key('host-switch-mode'),
            onPressed: controller.switchTurnTakingMode,
            child: const Text('切換'),
          ),
        ),
      ),
      if (state.showTalkButton)
        Center(
          child: _TalkButton(state: state, controller: controller),
        ),
      _FlowButtons(state: state, controller: controller),
      const _VoiceHints(),
      // 「結束主持」離流程鍵遠一點，避免按「下一步」時誤按；不再確認（30 分鐘內可以接著主持）
      Center(
        key: const Key('host-section-end'),
        child: TextButton.icon(
          key: const Key('host-end'),
          onPressed: controller.end,
          icon: const Icon(Icons.stop_circle_outlined),
          label: const Text('結束主持'),
        ),
      ),
    ];
    if (!wide) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        spacing: _gap,
        children: [...status, ...controls],
      );
    }
    return Row(
      key: const Key('host-wide-layout'),
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: _gap,
      children: [
        Expanded(
          child: Column(
            key: const Key('host-column-status'),
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: _gap,
            children: status,
          ),
        ),
        Expanded(
          child: Column(
            key: const Key('host-column-controls'),
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: _gap,
            children: controls,
          ),
        ),
      ],
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
    final textTheme = Theme.of(context).textTheme;
    return Card(
      key: const Key('host-section-progress'),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(_gap),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('目前進度', style: textTheme.labelLarge),
            const SizedBox(height: _smallGap),
            if (inTurn) ...[
              Text('第 $turnNumber 回合', style: textTheme.headlineMedium),
              const SizedBox(height: _smallGap),
              for (final phase in hostPhaseNames.keys)
                _PhaseRow(phase: phase, current: phaseNumber),
            ] else
              Text(
                hostProgressLabel(live.step, turnNumber, phaseNumber),
                style: textTheme.headlineMedium,
              ),
            // ✅ 這一局已經結束：保留結束前的進度，下面另有「接著主持」「重新開始」
            if (state.ended)
              const ListTile(leading: Icon(Icons.flag), title: Text('這一局已經結束')),
          ],
        ),
      ),
    );
  }
}

/// 一個階段：已完成、進行中、還沒到。進行中的用較大的字並標成選取。
class _PhaseRow extends StatelessWidget {
  const _PhaseRow({required this.phase, required this.current});

  final int phase;
  final int current;

  @override
  Widget build(BuildContext context) {
    final (status, icon, label) = phase < current
        ? ('done', Icons.check_circle, '已完成')
        : phase == current
        ? ('current', Icons.radio_button_checked, '進行中')
        : ('upcoming', Icons.radio_button_unchecked, '還沒到');
    final isCurrent = phase == current;
    return ListTile(
      key: Key('host-phase-$phase-$status'),
      contentPadding: EdgeInsets.zero,
      selected: isCurrent,
      leading: Icon(icon),
      title: Text(
        hostPhaseNames[phase]!,
        style: isCurrent ? Theme.of(context).textTheme.titleLarge : null,
      ),
      trailing: Text(label),
    );
  }
}

/// 「上一步」「暫停／繼續」「下一步」：同一列、一樣大，「下一步」是主要按鍵。
class _FlowButtons extends StatelessWidget {
  const _FlowButtons({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    // 手機寬度放得下三顆含圖示的按鍵：左右內距縮成小間距
    const padding = EdgeInsets.symmetric(horizontal: _smallGap);
    return Card(
      key: const Key('host-section-flow'),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(_gap),
        child: Row(
          spacing: _smallGap,
          children: [
            Expanded(
              child: OutlinedButton.icon(
                key: const Key('host-previous'),
                style: _bigOutlined.copyWith(
                  padding: const WidgetStatePropertyAll(padding),
                ),
                onPressed: controller.previous,
                icon: const Icon(Icons.skip_previous),
                label: const Text('上一步'),
              ),
            ),
            Expanded(
              child: OutlinedButton.icon(
                key: const Key('host-pause'),
                style: _bigOutlined.copyWith(
                  padding: const WidgetStatePropertyAll(padding),
                ),
                onPressed: controller.togglePause,
                icon: Icon(state.paused ? Icons.play_arrow : Icons.pause),
                label: Text(pauseButtonLabel(state)),
              ),
            ),
            Expanded(
              child: FilledButton.icon(
                key: const Key('host-next'),
                style: _bigFilled.copyWith(
                  padding: const WidgetStatePropertyAll(padding),
                ),
                onPressed: controller.next,
                icon: const Icon(Icons.skip_next),
                label: const Text('下一步'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 「按住說話」大按鈕：只在按住說話時出現。按下送 down，放開送 up。
class _TalkButton extends StatelessWidget {
  const _TalkButton({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (_) => controller.talkDown(),
      onPointerUp: (_) => controller.talkUp(),
      onPointerCancel: (_) => controller.talkUp(),
      child: Container(
        key: const Key('host-talk'),
        width: 160,
        height: 160,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(width: state.talkHeld ? 6 : 2),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          spacing: _smallGap,
          children: [
            Icon(state.talkHeld ? Icons.mic : Icons.mic_none, size: 48),
            Text(state.talkHeld ? '放開後主持人回答' : '按住說話'),
          ],
        ),
      ),
    );
  }
}

/// 「可以這樣說」：八句語音指令的提示，只是文字，不能點。
class _VoiceHints extends StatelessWidget {
  const _VoiceHints();

  @override
  Widget build(BuildContext context) {
    return _Section(
      key: const Key('host-section-voice-hints'),
      icon: Icons.record_voice_over,
      title: '可以這樣說',
      child: Wrap(
        key: const Key('host-voice-hints'),
        spacing: _gap,
        runSpacing: _smallGap,
        children: [
          for (final phrase in hostVoiceHints)
            Text('「$phrase」', style: Theme.of(context).textTheme.bodyLarge),
        ],
      ),
    );
  }
}
