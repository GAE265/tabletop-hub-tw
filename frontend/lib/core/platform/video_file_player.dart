import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';

import '../../app/theme/app_spacing.dart';
import 'blob_url.dart';

/// 播放影片檔的內容（例如規則影片生產器產生的 mp4）。AGENTS.md 5.3：播放套件包在
/// core/platform/ 後面，頁面只呼叫 [build]；測試用 fake 實作取代，不載入 video_player。
abstract interface class VideoFilePlayer {
  Widget build(
    BuildContext context, {
    required Uint8List bytes,
    required VideoSeekController seek,
  });
}

/// 讓頁面要求播放器跳到某個時間點（例如點段清單的一段）。
class VideoSeekController extends ChangeNotifier {
  Duration? _target;

  /// 最近一次要求跳到的時間點。
  Duration? get target => _target;

  void seekTo(Duration target) {
    _target = target;
    notifyListeners();
  }
}

/// 播放狀態與操作（包住播放套件的控制器；測試用 fake）。
abstract interface class VideoPlayback implements Listenable {
  bool get isPlaying;
  Duration get position;
  Duration get duration;
  Future<void> play();
  Future<void> pause();
  Future<void> seekTo(Duration target);
}

String formatPlaybackTime(Duration time) {
  final seconds = time.inSeconds;
  return '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';
}

/// 播放控制列：播放／暫停、目前時間與總長、拖動、全螢幕。
class VideoPlaybackControls extends StatelessWidget {
  const VideoPlaybackControls({
    required this.playback,
    required this.onFullscreen,
    this.fullscreen = false,
    super.key,
  });

  final VideoPlayback playback;
  final VoidCallback onFullscreen;

  /// 已經在全螢幕：按鈕改成「離開全螢幕」。
  final bool fullscreen;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ListenableBuilder(
      listenable: playback,
      builder: (context, _) {
        final total = playback.duration.inMilliseconds;
        final position = playback.position.inMilliseconds.clamp(0, total);
        return Material(
          color: scheme.surface.withValues(alpha: 0.85),
          child: Row(
            children: [
              IconButton(
                key: const Key('video-play-toggle'),
                tooltip: playback.isPlaying ? '暫停' : '播放',
                onPressed: playback.isPlaying ? playback.pause : playback.play,
                icon: Icon(playback.isPlaying ? Icons.pause : Icons.play_arrow),
              ),
              Text(
                '${formatPlaybackTime(playback.position)}／'
                '${formatPlaybackTime(playback.duration)}',
                style: Theme.of(context).textTheme.labelMedium,
              ),
              Expanded(
                child: Slider(
                  key: const Key('video-seek'),
                  max: total <= 0 ? 1 : total.toDouble(),
                  value: total <= 0 ? 0 : position.toDouble(),
                  onChanged: total <= 0
                      ? null
                      : (value) => playback.seekTo(
                          Duration(milliseconds: value.round()),
                        ),
                ),
              ),
              IconButton(
                key: const Key('video-fullscreen'),
                tooltip: fullscreen ? '離開全螢幕' : '全螢幕',
                onPressed: onFullscreen,
                icon: Icon(
                  fullscreen ? Icons.fullscreen_exit : Icons.fullscreen,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// 用 video_player 播放：網頁版把內容轉成 blob 網址（design.md D13 待決 1：帶身分下載後播放）。
/// 目前只支援網頁；之後轉 App 時改成寫入暫存檔再播放。
class DefaultVideoFilePlayer implements VideoFilePlayer {
  const DefaultVideoFilePlayer();

  @override
  Widget build(
    BuildContext context, {
    required Uint8List bytes,
    required VideoSeekController seek,
  }) => _FilePlayer(bytes: bytes, seek: seek);
}

class _FilePlayer extends StatefulWidget {
  const _FilePlayer({required this.bytes, required this.seek});

  final Uint8List bytes;
  final VideoSeekController seek;

  @override
  State<_FilePlayer> createState() => _FilePlayerState();
}

class _FilePlayerState extends State<_FilePlayer> {
  String? _url;
  VideoPlayerController? _controller;
  _ControllerPlayback? _playback;
  String? _error;

  @override
  void initState() {
    super.initState();
    try {
      _url = createBlobUrl(widget.bytes, 'video/mp4');
    } on UnsupportedError {
      _error = '目前只能在網頁播放影片';
      return;
    }
    final controller = VideoPlayerController.networkUrl(Uri.parse(_url!));
    _controller = controller;
    _playback = _ControllerPlayback(controller);
    controller.initialize().then(
      (_) {
        if (mounted) setState(() {});
      },
      onError: (Object _) {
        if (mounted) setState(() => _error = '影片無法播放，請重新下載');
      },
    );
    widget.seek.addListener(_seek);
  }

  void _seek() {
    final target = widget.seek.target;
    final controller = _controller;
    if (target == null || controller == null) return;
    controller
      ..seekTo(target)
      ..play();
  }

  @override
  void dispose() {
    widget.seek.removeListener(_seek);
    _controller?.dispose();
    final url = _url;
    if (url != null) revokeBlobUrl(url);
    super.dispose();
  }

  void _openFullscreen() {
    final controller = _controller;
    final playback = _playback;
    if (controller == null || playback == null) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        fullscreenDialog: true,
        builder: (context) => Scaffold(
          backgroundColor: Theme.of(context).colorScheme.inverseSurface,
          body: SafeArea(
            child: Stack(
              children: [
                Center(
                  child: AspectRatio(
                    aspectRatio: controller.value.aspectRatio,
                    child: VideoPlayer(controller),
                  ),
                ),
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: 0,
                  child: VideoPlaybackControls(
                    playback: playback,
                    fullscreen: true,
                    onFullscreen: () => Navigator.of(context).pop(),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    final playback = _playback;
    if (_error != null || controller == null || playback == null) {
      final scheme = Theme.of(context).colorScheme;
      return ColoredBox(
        color: scheme.inverseSurface,
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.medium),
            child: Text(
              _error ?? '準備播放…',
              style: TextStyle(color: scheme.onInverseSurface),
            ),
          ),
        ),
      );
    }
    return ColoredBox(
      color: Theme.of(context).colorScheme.inverseSurface,
      child: Stack(
        children: [
          Center(
            child: controller.value.isInitialized
                ? AspectRatio(
                    aspectRatio: controller.value.aspectRatio,
                    child: VideoPlayer(controller),
                  )
                : const CircularProgressIndicator(),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: VideoPlaybackControls(
              playback: playback,
              onFullscreen: _openFullscreen,
            ),
          ),
        ],
      ),
    );
  }
}

/// 把 VideoPlayerController 轉成 [VideoPlayback]。
class _ControllerPlayback implements VideoPlayback {
  _ControllerPlayback(this._controller);

  final VideoPlayerController _controller;

  @override
  bool get isPlaying => _controller.value.isPlaying;
  @override
  Duration get position => _controller.value.position;
  @override
  Duration get duration => _controller.value.duration;
  @override
  Future<void> play() => _controller.play();
  @override
  Future<void> pause() => _controller.pause();
  @override
  Future<void> seekTo(Duration target) => _controller.seekTo(target);
  @override
  void addListener(VoidCallback listener) => _controller.addListener(listener);
  @override
  void removeListener(VoidCallback listener) =>
      _controller.removeListener(listener);
}

final videoFilePlayerProvider = Provider<VideoFilePlayer>(
  (ref) => const DefaultVideoFilePlayer(),
);
