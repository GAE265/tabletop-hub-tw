import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
const _voiceNames = {HostVoice.male: '男聲', HostVoice.female: '女聲'};

/// AI 語音主持的參考畫面（spec §14.4）：一個頁面的幾種狀態。
///
/// 只用 Flutter 預設元件，不套主題、不做 RWD。所有操作都只呼叫 `state/` 的方法；
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
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _Notices(state: state, controller: controller),
          if (hosting)
            _Hosting(state: state, controller: controller)
          else
            _Setup(state: state, controller: controller),
          if (state.canResume)
            _ResumeButtons(state: state, controller: controller),
        ],
      ),
    );
  }
}

/// 提醒（spec §14.5）。可能同時有好幾個。
class _Notices extends StatelessWidget {
  const _Notices({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final notice in state.notices)
          switch (notice) {
            HostNotice.connecting => const Padding(
              key: Key('host-connecting'),
              padding: EdgeInsets.all(8),
              child: Center(child: CircularProgressIndicator()),
            ),
            HostNotice.tapToResume => OutlinedButton(
              onPressed: controller.tapToResume,
              child: Text(hostNoticeText(notice)!),
            ),
            HostNotice.audioLocked => OutlinedButton(
              onPressed: controller.unlockAudio,
              child: Text(hostNoticeText(notice)!),
            ),
            HostNotice.paused => ListTile(
              leading: const Icon(Icons.pause_circle),
              title: Text(hostNoticeText(notice)!),
              subtitle: const Text('暫停中也可以問規則'),
            ),
            _ => ListTile(
              leading: const Icon(Icons.info_outline),
              title: Text(hostNoticeText(notice)!),
            ),
          },
      ],
    );
  }
}

/// 開主持前：人數、接話方式、聲線、「開始主持」。
class _Setup extends StatelessWidget {
  const _Setup({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    final busy = state.connection == HostConnectionStatus.connecting;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('《血與刃的白薔薇》'),
        const SizedBox(height: 16),
        const Text('人數（5 到 10 人）'),
        Row(
          children: [
            IconButton(
              key: const Key('host-player-count-minus'),
              onPressed: () => controller.setPlayerCount(state.playerCount - 1),
              icon: const Icon(Icons.remove),
            ),
            Text('${state.playerCount}', key: const Key('host-player-count')),
            IconButton(
              key: const Key('host-player-count-plus'),
              onPressed: () => controller.setPlayerCount(state.playerCount + 1),
              icon: const Icon(Icons.add),
            ),
          ],
        ),
        const SizedBox(height: 16),
        const Text('接話方式'),
        Wrap(
          spacing: 8,
          children: [
            for (final mode in TurnTakingMode.values)
              ChoiceChip(
                label: Text(_modeNames[mode]!),
                selected: state.turnTakingMode == mode,
                onSelected: (_) => controller.setTurnTakingMode(mode),
              ),
          ],
        ),
        const Text('主持中也可以切換'),
        const SizedBox(height: 16),
        const Text('聲線'),
        Wrap(
          spacing: 8,
          children: [
            for (final voice in HostVoice.values)
              ChoiceChip(
                label: Text(_voiceNames[voice]!),
                selected: state.voice == voice,
                onSelected: (_) => controller.setVoice(voice),
              ),
          ],
        ),
        const Text('開始後這場主持不能換'),
        const SizedBox(height: 16),
        if (!state.canResume)
          FilledButton(
            key: const Key('host-start'),
            onPressed: busy ? null : controller.start,
            child: const Text('開始主持'),
          ),
      ],
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
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Wrap(
        spacing: 8,
        children: [
          FilledButton(
            key: const Key('host-resume'),
            onPressed: controller.resume,
            child: Text(state.resumeLabel ?? '接著主持'),
          ),
          OutlinedButton(
            key: const Key('host-restart'),
            onPressed: controller.restart,
            child: const Text('重新開始'),
          ),
        ],
      ),
    );
  }
}

/// 主持中：目前進度、主持人的狀態、接話方式、流程鍵、語音指令的提示。
class _Hosting extends StatelessWidget {
  const _Hosting({required this.state, required this.controller});

  final HostState state;
  final HostController controller;

  @override
  Widget build(BuildContext context) {
    final live = state.live!;
    final turnNumber = live.turnNumber;
    final phaseNumber = live.phaseNumber;
    final inTurn = turnNumber != null && phaseNumber != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('目前進度'),
        if (inTurn) ...[
          Text('第 $turnNumber 回合'),
          for (final phase in hostPhaseNames.keys)
            _PhaseRow(phase: phase, current: phaseNumber),
        ] else
          Text(hostProgressLabel(live.step, turnNumber, phaseNumber)),
        if (state.ended) const Text('這一局已經結束'),
        const SizedBox(height: 16),
        if (state.lookingUp)
          const ListTile(leading: Icon(Icons.menu_book), title: Text('正在查規則')),
        Row(
          children: [
            const Text('接話方式：'),
            Text(
              _modeNames[state.turnTakingMode]!,
              key: const Key('host-mode-label'),
            ),
            TextButton(
              key: const Key('host-switch-mode'),
              onPressed: controller.switchTurnTakingMode,
              child: const Text('切換'),
            ),
          ],
        ),
        if (state.showTalkButton)
          Center(
            child: Listener(
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
                child: Text(state.talkHeld ? '放開後主持人回答' : '按住說話'),
              ),
            ),
          ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          children: [
            OutlinedButton(
              key: const Key('host-previous'),
              onPressed: controller.previous,
              child: const Text('上一步'),
            ),
            OutlinedButton(
              key: const Key('host-pause'),
              onPressed: controller.togglePause,
              child: Text(pauseButtonLabel(state)),
            ),
            FilledButton(
              key: const Key('host-next'),
              onPressed: controller.next,
              child: const Text('下一步'),
            ),
          ],
        ),
        const SizedBox(height: 16),
        const Text('可以這樣說'),
        Wrap(
          key: const Key('host-voice-hints'),
          spacing: 12,
          children: [for (final phrase in hostVoiceHints) Text('「$phrase」')],
        ),
        const SizedBox(height: 16),
        TextButton(
          key: const Key('host-end'),
          // 不再確認：結束後 30 分鐘內可以接著主持
          onPressed: controller.end,
          child: const Text('結束主持'),
        ),
      ],
    );
  }
}

/// 一個階段：已完成、進行中、還沒到。
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
    return ListTile(
      key: Key('host-phase-$phase-$status'),
      dense: true,
      leading: Icon(icon),
      title: Text(hostPhaseNames[phase]!),
      trailing: Text(label),
    );
  }
}
