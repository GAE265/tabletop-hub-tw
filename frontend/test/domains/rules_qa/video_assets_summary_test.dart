// 素材清單的摘要（Stitch 版面）：完成進度、每格幾段、還缺的素材，以及在清單上直接略過。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_assets_summary.dart';

import '../../support/fakes.dart';
import 'video_assets_support.dart';

DraftAsset asset(
  String key, {
  bool hasPhoto = false,
  bool skipped = false,
  List<String> regions = const [],
}) => DraftAsset(
  assetKey: key,
  kind: 'flat_photo',
  priority: 'must',
  reason: '',
  representative: false,
  regions: regions,
  hasPhoto: hasPhoto,
  skipped: skipped,
);

DraftSegment segment(String key, String chapter) => DraftSegment(
  segmentKey: key,
  chapter: chapter,
  sourcePages: const [],
  beats: const [],
);

VideoDraft draftOf(List<DraftAsset> assets, [List<DraftSegment>? segments]) =>
    VideoDraft(
      videoVersion: 1,
      segments: segments ?? const [],
      assets: assets,
      coverage: const DraftCoverage(
        status: 'done',
        totalRules: 0,
        issues: [],
        problems: [],
        hints: [],
      ),
      terms: const DraftTerms(status: 'used'),
      pagesStale: false,
    );

VideoReadiness readinessOf({
  List<String> photos = const [],
  List<(String, String)> regions = const [],
}) => VideoReadiness(
  ready: photos.isEmpty && regions.isEmpty,
  missingPhotos: [
    for (final key in photos)
      MissingPhoto(assetKey: key, priority: 'must', reason: ''),
  ],
  missingRegions: [
    for (final (key, region) in regions)
      MissingRegion(assetKey: key, region: region),
  ],
  unsupported: const [],
);

void main() {
  group('完成進度', () {
    test('已拍且區域都標好、或已略過，算完成；照片或區域還缺的不算', () {
      final draft = draftOf([
        asset('a', hasPhoto: true),
        asset('b', hasPhoto: true, regions: ['z']),
        asset('c', skipped: true),
        asset('d'),
      ]);
      final p = assetsProgress(
        draft,
        readinessOf(photos: ['d'], regions: [('b', 'z')]),
      );
      expect(p.total, 4);
      expect(p.done, 2);
      expect(p.skipped, 1);
      expect(p.pending, 2);
      expect(p.percent, 50);
    });

    test('還沒讀到缺什麼：只看有沒有照片或略過', () {
      final p = assetsProgress(
        draftOf([asset('a', hasPhoto: true), asset('b')]),
        null,
      );
      expect(p.done, 1);
      expect(p.percent, 50);
    });

    test('沒有任何素材：完成 100%', () {
      expect(assetsProgress(draftOf(const []), null).percent, 100);
    });
  });

  group('哪些素材還缺', () {
    test('缺照片或缺區域的素材都算，依素材清單的順序', () {
      final draft = draftOf([asset('a'), asset('b'), asset('c')]);
      expect(
        pendingAssetKeys(
          draft,
          readinessOf(photos: ['c'], regions: [('a', 'z')]),
        ),
        ['a', 'c'],
      );
    });
  });

  group('每格幾段', () {
    test('依開局、走完一輪、獲勝方式的順序數段數', () {
      final draft = draftOf(const [], [
        segment('s1', 'round'),
        segment('s2', 'setup'),
        segment('s3', 'round'),
        segment('s4', 'win'),
      ]);
      expect(chapterSegmentCounts(draft), [
        ('開局擺放', 1),
        ('走完一輪', 2),
        ('獲勝方式', 1),
      ]);
    });

    test('舊的草稿沒有標格：沒有資料', () {
      final draft = draftOf(const [], [segment('s1', '')]);
      expect(chapterSegmentCounts(draft), isEmpty);
    });
  });

  group('在清單上略過素材', () {
    ProviderContainer makeContainer(FakeVideoStudioRepository repo) {
      final container = ProviderContainer(
        overrides: [videoStudioRepositoryProvider.overrideWithValue(repo)],
      );
      addTearDown(container.dispose);
      return container;
    }

    test('成功：送出略過，回傳 true', () async {
      final repo = assetsRepo();
      final container = makeContainer(repo);
      final ok = await container
          .read(videoAssetListProvider('p1').notifier)
          .skip('board');
      expect(ok, isTrue);
      final (project, key, input) = repo.updates.single;
      expect((project, key, input.skipped), ('p1', 'board', true));
      expect(container.read(videoAssetListProvider('p1')).error, isNull);
    });

    test('失敗：記下原因，回傳 false', () async {
      final repo = assetsRepo()
        ..updateError = const ApiException(code: 'X', message: '這個素材不能略過');
      final container = makeContainer(repo);
      final ok = await container
          .read(videoAssetListProvider('p1').notifier)
          .skip('board');
      expect(ok, isFalse);
      final state = container.read(videoAssetListProvider('p1'));
      expect(state.error, '這個素材不能略過');
      expect(state.busyKey, isNull);
    });
  });
}
