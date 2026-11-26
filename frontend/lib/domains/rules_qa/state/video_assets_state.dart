import 'dart:typed_data';
import 'dart:ui';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/platform/image_picker.dart';
import '../data/video_studio_models.dart';
import '../data/video_studio_repository.dart';
import 'video_draft_state.dart';
import 'video_projects_state.dart';

/// 一個素材：哪個專案的哪個 asset_key。
typedef VideoAssetRef = ({String projectId, String assetKey});

/// 區域寬或高小於這個比例就太小（design.md D14：框太小不能儲存）。
const minRegionSize = 0.01;

/// 產生影片前還缺什麼；拍照、改區域後重新讀取。
final videoReadinessProvider = FutureProvider.family<VideoReadiness, String>(
  (ref, projectId) =>
      ref.read(videoStudioRepositoryProvider).getReadiness(projectId),
  retry: (_, _) => null,
);

class VideoAssetState {
  const VideoAssetState({
    this.asset,
    this.photo,
    this.loading = false,
    this.busy = false,
    this.photoReplaced = false,
    this.error,
  });

  final VideoAsset? asset;

  /// 照片內容（後端存的版本，已轉正）。
  final Uint8List? photo;
  final bool loading;

  /// 上傳或旋轉中。
  final bool busy;

  /// 換了照片而且素材有區域：提示重新確認區域。
  final bool photoReplaced;
  final String? error;

  VideoAssetState copyWith({
    VideoAsset? asset,
    Uint8List? photo,
    bool? loading,
    bool? busy,
    bool? photoReplaced,
    String? error,
    bool clearError = false,
  }) => VideoAssetState(
    asset: asset ?? this.asset,
    photo: photo ?? this.photo,
    loading: loading ?? this.loading,
    busy: busy ?? this.busy,
    photoReplaced: photoReplaced ?? this.photoReplaced,
    error: clearError ? null : error ?? this.error,
  );
}

/// 單一素材：拍照或選圖上傳、看原圖、旋轉（design.md D14）。
class VideoAssetNotifier extends Notifier<VideoAssetState> {
  VideoAssetNotifier(this.target);

  final VideoAssetRef target;

  VideoStudioRepository get _repo => ref.read(videoStudioRepositoryProvider);

  @override
  VideoAssetState build() => const VideoAssetState();

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final asset = await _repo.getAsset(target.projectId, target.assetKey);
      final photo = asset.hasPhoto
          ? await _repo.getPhoto(target.projectId, target.assetKey)
          : null;
      if (!ref.mounted) return;
      state = VideoAssetState(asset: asset, photo: photo);
    } on ApiException catch (error) {
      if (ref.mounted) {
        state = state.copyWith(loading: false, error: error.message);
      }
    }
  }

  /// 拍照或選一張圖上傳；取消時什麼都不做。
  Future<void> pickAndUpload() async {
    final List<PickedImage>? images;
    try {
      images = await ref.read(imagePickerProvider).pickImages();
    } on Object {
      state = state.copyWith(error: '讀不到這張圖片，請換一張');
      return;
    }
    if (images == null || images.isEmpty) return;
    final before = state.asset;
    state = state.copyWith(busy: true, clearError: true);
    try {
      final asset = await _repo.uploadPhoto(
        target.projectId,
        target.assetKey,
        images.first,
      );
      final photo = await _repo.getPhoto(target.projectId, target.assetKey);
      if (!ref.mounted) return;
      state = VideoAssetState(
        asset: asset,
        photo: photo,
        photoReplaced:
            (before?.hasPhoto ?? false) &&
            asset.regions.values.any((b) => b != null),
      );
      _changed();
    } on ApiException catch (error) {
      if (ref.mounted) {
        state = state.copyWith(busy: false, error: error.message);
      }
    }
  }

  /// 順時針轉 90 度（後端把區域改回待量測）。
  Future<void> rotate() async {
    final asset = state.asset;
    if (asset == null) return;
    state = state.copyWith(busy: true, clearError: true);
    try {
      final updated = await _repo.updateAsset(
        target.projectId,
        target.assetKey,
        VideoAssetUpdate(orientation: (asset.orientation + 90) % 360),
      );
      if (!ref.mounted) return;
      state = state.copyWith(asset: updated, busy: false);
      _changed();
    } on ApiException catch (error) {
      if (ref.mounted) {
        state = state.copyWith(busy: false, error: error.message);
      }
    }
  }

  /// 略過（true）或取消略過（false）這個選拍素材；成功回傳 true（MR 10）。
  Future<bool> setSkipped(bool skipped) async {
    if (state.asset == null) return false;
    state = state.copyWith(busy: true, clearError: true);
    try {
      final updated = await _repo.updateAsset(
        target.projectId,
        target.assetKey,
        VideoAssetUpdate(skipped: skipped),
      );
      if (!ref.mounted) return true;
      state = state.copyWith(asset: updated, busy: false);
      _changed();
      return true;
    } on ApiException catch (error) {
      if (ref.mounted) {
        state = state.copyWith(busy: false, error: error.message);
      }
      return false;
    }
  }

  /// 照片或方向改了：素材清單、缺什麼、標區域頁、專案總覽的步驟都要重新讀。
  void _changed() {
    ref
      ..invalidate(videoReadinessProvider(target.projectId))
      ..invalidate(videoDraftProvider(target.projectId))
      ..invalidate(videoProjectProvider(target.projectId))
      ..invalidate(videoRegionsProvider(target));
  }
}

final videoAssetProvider =
    NotifierProvider.family<VideoAssetNotifier, VideoAssetState, VideoAssetRef>(
      VideoAssetNotifier.new,
    );

/// 標區域畫面的「第 N 段會用到」。
String regionSegmentsText(List<int> segments) =>
    segments.isEmpty ? '目前沒有段用到這個區域' : '第 ${segments.join('、')} 段會用到';

class VideoRegionsState {
  const VideoRegionsState({
    this.names = const [],
    this.boxes = const {},
    this.saved = const {},
    this.hints = const {},
    this.segments = const {},
    this.skipped = const {},
    this.current,
    this.loading = false,
    this.saving = false,
    this.error,
  });

  /// 草稿列的區域名稱（照順序）。
  final List<String> names;

  /// 畫面上目前的框（0–1 的比例，以套用方向之後的圖為準）；null＝還沒標。
  final Map<String, Rect?> boxes;

  /// 最近一次儲存（或讀取）時的框。
  final Map<String, Rect?> saved;

  /// 區域名稱 → 給店員的白話說明（取自規則書的場地清單）。
  final Map<String, String> hints;

  /// 區域名稱 → 用到它的段。
  final Map<String, List<int>> segments;

  /// 照片拍不到、略過的區域（略過了就算處理好了）。
  final Set<String> skipped;

  /// 目前在標的區域。
  final String? current;
  final bool loading;
  final bool saving;
  final String? error;

  int get doneCount => names
      .where((name) => boxes[name] != null || skipped.contains(name))
      .length;

  /// 有還沒儲存的框。
  bool get dirty => names.any((name) => boxes[name] != saved[name]);

  /// 寬或高小於 1% 的區域。
  List<String> get tooSmall => [
    for (final name in names)
      if (boxes[name] case final box?)
        if (box.width < minRegionSize || box.height < minRegionSize) name,
  ];

  bool get canSave => dirty && tooSmall.isEmpty && !saving;

  VideoRegionsState copyWith({
    List<String>? names,
    Map<String, Rect?>? boxes,
    Map<String, Rect?>? saved,
    Set<String>? skipped,
    String? current,
    bool? loading,
    bool? saving,
    String? error,
    bool clearError = false,
  }) => VideoRegionsState(
    names: names ?? this.names,
    boxes: boxes ?? this.boxes,
    saved: saved ?? this.saved,
    hints: hints,
    segments: segments,
    skipped: skipped ?? this.skipped,
    current: current ?? this.current,
    loading: loading ?? this.loading,
    saving: saving ?? this.saving,
    error: clearError ? null : error ?? this.error,
  );
}

/// 標區域：一次一個區域，拖出矩形、拖角落微調、拖中間移動（design.md D14）。
/// 離開頁面就清掉沒儲存的框（autoDispose）；畫面先提示。
class VideoRegionsNotifier extends Notifier<VideoRegionsState> {
  VideoRegionsNotifier(this.target);

  final VideoAssetRef target;

  @override
  VideoRegionsState build() => const VideoRegionsState();

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final asset = await ref
          .read(videoStudioRepositoryProvider)
          .getAsset(target.projectId, target.assetKey);
      if (!ref.mounted) return;
      final boxes = {
        for (final entry in asset.regions.entries)
          entry.key: entry.value == null ? null : _rect(entry.value!),
      };
      final names = asset.regions.keys.toList();
      final skipped = asset.skippedRegions.toSet();
      state = VideoRegionsState(
        names: names,
        boxes: boxes,
        saved: boxes,
        hints: asset.regionHints,
        segments: asset.regionSegments,
        skipped: skipped,
        current:
            _nextUndone(names, boxes, skipped) ??
            (names.isEmpty ? null : names.first),
      );
    } on ApiException catch (error) {
      if (ref.mounted) {
        state = state.copyWith(loading: false, error: error.message);
      }
    }
  }

  void select(String name) => state = state.copyWith(current: name);

  /// 設定一個區域的框（裁在照片之內）；設好後目前區域換到下一個還沒標的。
  void setBox(String name, Rect box) {
    final clipped = Rect.fromLTRB(
      box.left.clamp(0, 1),
      box.top.clamp(0, 1),
      box.right.clamp(0, 1),
      box.bottom.clamp(0, 1),
    );
    final boxes = {...state.boxes, name: clipped};
    final wasNew = state.boxes[name] == null;
    state = state.copyWith(
      boxes: boxes,
      current: wasNew
          ? _nextUndone(state.names, boxes, state.skipped) ?? name
          : name,
      clearError: true,
    );
  }

  /// 只送改過的區域。成功回傳 true。
  Future<bool> save() async {
    if (!state.canSave) return false;
    final changed = {
      for (final name in state.names)
        if (state.boxes[name] != state.saved[name])
          name: switch (state.boxes[name]) {
            final box? => [box.left, box.top, box.width, box.height],
            null => null,
          },
    };
    state = state.copyWith(saving: true, clearError: true);
    try {
      await ref
          .read(videoStudioRepositoryProvider)
          .updateAsset(
            target.projectId,
            target.assetKey,
            VideoAssetUpdate(regions: changed),
          );
      if (!ref.mounted) return true;
      state = state.copyWith(saving: false, saved: state.boxes);
      ref
        ..invalidate(videoReadinessProvider(target.projectId))
        ..invalidate(videoDraftProvider(target.projectId))
        ..invalidate(videoProjectProvider(target.projectId));
      return true;
    } on ApiException catch (error) {
      if (ref.mounted) {
        state = state.copyWith(saving: false, error: error.message);
      }
      return false;
    }
  }

  static Rect _rect(List<double> box) =>
      Rect.fromLTWH(box[0], box[1], box[2], box[3]);

  /// 照片拍不到這個區域：略過（true）或取消略過（false），立刻存；成功回傳 true。
  /// 產生影片時會拿掉指向它的框選、標籤與移動（2026-11-22 永傑決定）。
  Future<bool> setRegionSkipped(String name, bool skip) async {
    final skipped = {...state.skipped};
    skip ? skipped.add(name) : skipped.remove(name);
    state = state.copyWith(saving: true, clearError: true);
    try {
      await ref
          .read(videoStudioRepositoryProvider)
          .updateAsset(
            target.projectId,
            target.assetKey,
            VideoAssetUpdate(
              skippedRegions: [
                for (final n in state.names)
                  if (skipped.contains(n)) n,
              ],
            ),
          );
      if (!ref.mounted) return true;
      state = state.copyWith(saving: false, skipped: skipped);
      ref
        ..invalidate(videoReadinessProvider(target.projectId))
        ..invalidate(videoDraftProvider(target.projectId))
        ..invalidate(videoProjectProvider(target.projectId));
      return true;
    } on ApiException catch (error) {
      if (ref.mounted) {
        state = state.copyWith(saving: false, error: error.message);
      }
      return false;
    }
  }

  static String? _nextUndone(
    List<String> names,
    Map<String, Rect?> boxes,
    Set<String> skipped,
  ) {
    for (final name in names) {
      if (boxes[name] == null && !skipped.contains(name)) return name;
    }
    return null;
  }
}

final videoRegionsProvider = NotifierProvider.autoDispose
    .family<VideoRegionsNotifier, VideoRegionsState, VideoAssetRef>(
      VideoRegionsNotifier.new,
    );
