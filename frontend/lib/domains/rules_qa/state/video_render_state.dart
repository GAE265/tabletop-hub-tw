import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';

/// 最近一次成功產生的影片；還沒有時是 null。產生影片的工作完成時會重新讀取。
final videoRenderProvider = FutureProvider.family<VideoRender?, String>(
  (ref, projectId) =>
      ref.read(videoStudioRepositoryProvider).getRender(projectId),
  retry: (_, _) => null,
);

/// 成品的影片檔（整支下載，離開看影片頁就釋放）。
final videoRenderVideoProvider = FutureProvider.autoDispose
    .family<Uint8List, String>(
      (ref, projectId) =>
          ref.read(videoStudioRepositoryProvider).getRenderVideo(projectId),
      retry: (_, _) => null,
    );

String _segments(List<int> numbers) => numbers.join('、');

/// 略過前的提示（2026-11-22 永傑決定）。
String skipConfirmText(List<int> affected) =>
    '略過後第 ${_segments(affected)} 段會少一張圖';

/// 只靠這張素材的段：不能略過。和後端 RULES_VIDEO_SKIP_BLOCKED 的訊息一致。
String skipBlockedText(List<int> blocked) =>
    '第 ${_segments(blocked)} 段只靠這張，不能略過';

/// 只靠這張素材的段：拍不了時改用文字卡（2026-11-22 永傑決定，不再擋住產生影片）。
String textCardHint(List<int> blocked) =>
    '第 ${_segments(blocked)} 段只靠這張；拍不了的話，那一段可以改成顯示文字卡';

/// 改用文字卡前的說明。
String textCardConfirmText(List<int> blocked, String label) =>
    '第 ${_segments(blocked)} 段會改成顯示文字「$label」，其他用到它的段會少一張圖。';
