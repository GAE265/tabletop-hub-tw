import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domains/rules_qa/data/rules_qa_models.dart';

/// 教學影片播放器（AGENTS.md 5.3：平台相關的程式包在 core/platform/ 後面）。
///
/// 依 [LessonVideo.source] 決定怎麼播：`youtube` 之後用 `youtube_player_iframe`
/// 內嵌播放（待組內同意新增套件，見 openspec/changes/add-rules-qa/design.md D9）；
/// `file`（影片生產器的 mp4）由 add-rules-video-maker 加上。
abstract interface class LessonVideoPlayer {
  Widget build(BuildContext context, LessonVideo video);
}

/// 新增播放套件前的暫時實作：顯示影片標題與網址，不內嵌播放。
class PlaceholderLessonVideoPlayer implements LessonVideoPlayer {
  const PlaceholderLessonVideoPlayer();

  @override
  Widget build(BuildContext context, LessonVideo video) {
    return Card(
      key: const Key('lesson-video-placeholder'),
      child: ListTile(
        leading: const Icon(Icons.ondemand_video),
        title: Text(video.title),
        subtitle: SelectableText(video.videoUrl),
      ),
    );
  }
}

final lessonVideoPlayerProvider = Provider<LessonVideoPlayer>(
  (ref) => const PlaceholderLessonVideoPlayer(),
);
