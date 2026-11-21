// 規則影片素材（MR 8）的測試共用資料。
import 'dart:convert';
import 'dart:typed_data';

import 'package:tabletop_hub/core/platform/image_picker.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';

import '../../support/fakes.dart';

/// 40×20 的 PNG（Pillow 產生的有效圖檔）。
final pngBytes = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAACgAAAAUCAIAAABwJOjsAAAAOElEQVR4nO3NQQEAMAgDsa5C8C9lsvYdBo4HjYGcW6UJHlmVGGQy+yXGmKu6xBhzVZcYY67S8vgBX4wBLAwEhl4AAAAASUVORK5CYII=',
);

/// 30×60 的 JPEG（直的）。
final jpegBytes = base64Decode(
  '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAA8AB4DASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDkKKKK8U/TAooooAKKKKACiiigAooooAKKKKACiiigAooooA//2Q==',
);

PickedImage picked([Uint8List? bytes]) =>
    PickedImage(name: 'board.png', bytes: bytes ?? pngBytes);

VideoAsset sampleAsset({
  String key = 'board',
  bool hasPhoto = false,
  int orientation = 0,
  Map<String, List<double>?> regions = const {'zone_a': null, 'zone_b': null},
  String priority = 'must',
  String? shot = '整張圖板，從正上方拍',
}) => VideoAsset(
  assetKey: key,
  kind: 'flat_photo',
  priority: priority,
  reason: '說明圖板上的兩個區域',
  shot: shot,
  hasPhoto: hasPhoto,
  orientation: orientation,
  regions: regions,
  videoVersion: 1,
);

const readyNone = VideoReadiness(
  ready: true,
  missingPhotos: [],
  missingRegions: [],
  unsupported: [],
);

const notReady = VideoReadiness(
  ready: false,
  missingPhotos: [
    MissingPhoto(
      assetKey: 'board',
      priority: 'must',
      reason: '說明圖板上的兩個區域',
      shot: '整張圖板，從正上方拍',
    ),
    MissingPhoto(
      assetKey: 'card',
      priority: 'optional',
      reason: '一張代表牌',
      shot: null,
    ),
  ],
  missingRegions: [
    MissingRegion(assetKey: 'board', region: 'zone_a'),
    MissingRegion(assetKey: 'board', region: 'zone_b'),
  ],
  unsupported: [
    UnsupportedAsset(
      assetKey: 'map',
      kind: 'drawn',
      message: '本版不支援繪製素材，請改成拍照',
    ),
  ],
);

/// 有草稿、圖板（board）素材的假 repository。
FakeVideoStudioRepository assetsRepo({
  VideoAsset? asset,
  Uint8List? photo,
  VideoReadiness readiness = notReady,
}) {
  final repo = FakeVideoStudioRepository(
    projects: [sampleVideoProject(step: 'draft')],
  );
  final a = asset ?? sampleAsset();
  repo.assets['p1/${a.assetKey}'] = a;
  if (photo != null) repo.photos['p1/${a.assetKey}'] = photo;
  repo.readiness['p1'] = readiness;
  return repo;
}
