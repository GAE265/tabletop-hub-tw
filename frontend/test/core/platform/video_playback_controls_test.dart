// 影片播放的控制列（add-rules-video-mobile MR 10）：播放、暫停、拖動、全螢幕。
// 用手寫的 FakeVideoPlayback，不載入 video_player 套件。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/app_theme.dart';
import 'package:tabletop_hub/core/platform/video_file_player.dart';

import '../../support/fakes.dart';

Future<FakeVideoPlayback> pumpControls(
  WidgetTester tester, {
  FakeVideoPlayback? playback,
  VoidCallback? onFullscreen,
}) async {
  tester.view.physicalSize = const Size(400, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final fake = playback ?? FakeVideoPlayback();
  await tester.pumpWidget(
    MaterialApp(
      theme: buildAppTheme(const FakeAppFonts()),
      home: Scaffold(
        body: VideoPlaybackControls(
          playback: fake,
          onFullscreen: onFullscreen ?? () {},
        ),
      ),
    ),
  );
  return fake;
}

void main() {
  testWidgets('按播放、再按暫停', (tester) async {
    final playback = await pumpControls(tester);
    final toggle = find.byKey(const Key('video-play-toggle'));
    expect(find.byIcon(Icons.play_arrow), findsOneWidget);
    await tester.tap(toggle);
    await tester.pump();
    expect(playback.calls, ['play']);
    expect(find.byIcon(Icons.pause), findsOneWidget);
    await tester.tap(toggle);
    await tester.pump();
    expect(playback.calls, ['play', 'pause']);
  });

  testWidgets('顯示目前時間與總長', (tester) async {
    await pumpControls(
      tester,
      playback: FakeVideoPlayback(
        duration: const Duration(seconds: 125),
        position: const Duration(seconds: 5),
      ),
    );
    expect(find.text('0:05／2:05'), findsOneWidget);
  });

  testWidgets('拖動進度條：跳到那個時間點', (tester) async {
    final playback = await pumpControls(tester);
    final slider = find.byKey(const Key('video-seek'));
    final rect = tester.getRect(slider);
    // 點在進度條約一半的位置
    await tester.tapAt(Offset(rect.left + rect.width / 2, rect.center.dy));
    await tester.pump();
    final seek = playback.calls.singleWhere((c) => c.startsWith('seek'));
    final ms = int.parse(seek.split(' ').last);
    expect(ms, closeTo(21000, 4000));
  });

  testWidgets('全螢幕按鈕', (tester) async {
    var pressed = 0;
    await pumpControls(tester, onFullscreen: () => pressed++);
    await tester.tap(find.byKey(const Key('video-fullscreen')));
    expect(pressed, 1);
  });

  test('跳到某個時間點：通知播放器', () {
    final seek = VideoSeekController();
    var notified = 0;
    seek.addListener(() => notified++);
    seek.seekTo(const Duration(seconds: 12));
    expect(seek.target, const Duration(seconds: 12));
    expect(notified, 1);
  });
}
