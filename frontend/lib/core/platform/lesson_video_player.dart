import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

import '../../domains/rules_qa/data/rules_qa_models.dart';

/// 教學影片播放器（AGENTS.md 5.3：平台相關的程式包在 core/platform/ 後面）。
///
/// 頁面只呼叫 [build]，不直接用播放套件；測試用 fake 實作取代，不載入 YouTube。
abstract interface class LessonVideoPlayer {
  Widget build(BuildContext context, LessonVideo video);
}

/// 依影片來源選擇播放方式：`youtube` 用 youtube_player_iframe 內嵌播放（Web、Android、iOS
/// 都支援）；`file`（影片生產器的 mp4）由 add-rules-video-maker 加上支援。
class DefaultLessonVideoPlayer implements LessonVideoPlayer {
  const DefaultLessonVideoPlayer();

  @override
  Widget build(BuildContext context, LessonVideo video) {
    final youtubeId = video.youtubeId;
    if (video.source == LessonVideoSource.youtube && youtubeId != null) {
      return _YoutubeVideo(key: ValueKey(youtubeId), youtubeId: youtubeId);
    }
    return _UnsupportedVideo(video: video);
  }
}

class _YoutubeVideo extends StatefulWidget {
  const _YoutubeVideo({required this.youtubeId, super.key});

  final String youtubeId;

  @override
  State<_YoutubeVideo> createState() => _YoutubeVideoState();
}

class _YoutubeVideoState extends State<_YoutubeVideo> {
  late final _controller = YoutubePlayerController.fromVideoId(
    videoId: widget.youtubeId,
    params: const YoutubePlayerParams(
      showFullscreenButton: true,
      // 只推薦同一個頻道的影片，避免播完後出現無關的內容
      strictRelatedVideos: true,
    ),
  );

  @override
  void dispose() {
    _controller.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => YoutubePlayer(controller: _controller);
}

/// 還不支援的影片來源：顯示標題與網址。
class _UnsupportedVideo extends StatelessWidget {
  const _UnsupportedVideo({required this.video});

  final LessonVideo video;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.ondemand_video),
        title: Text(video.title),
        subtitle: SelectableText(video.videoUrl),
      ),
    );
  }
}

final lessonVideoPlayerProvider = Provider<LessonVideoPlayer>(
  (ref) => const DefaultLessonVideoPlayer(),
);
