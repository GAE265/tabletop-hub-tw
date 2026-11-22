// 規則影片的素材手機頁（add-rules-video-mobile MR 8，design.md D14 與外觀決定）。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';

import '../../../support/fakes.dart';
import '../video_assets_support.dart';
import 'video_pages_support.dart';

const draftWithAssets = VideoDraft(
  videoVersion: 1,
  segments: [
    DraftSegment(
      segmentKey: 's1',
      sourcePages: [7],
      beats: [DraftBeat(beatKey: 'b1', narration: '看圖板。', subtitle: '圖板')],
    ),
  ],
  assets: [
    DraftAsset(
      assetKey: 'board',
      label: '圖板',
      kind: 'flat_photo',
      priority: 'must',
      reason: '說明圖板上的兩個區域',
      shot: '整張圖板，從正上方拍',
      representative: false,
      regions: ['zone_a', 'zone_b'],
      hasPhoto: false,
    ),
    DraftAsset(
      assetKey: 'card',
      kind: 'flat_photo',
      priority: 'optional',
      reason: '一張代表牌',
      shot: null,
      representative: true,
      regions: [],
      hasPhoto: true,
      skippable: true,
    ),
  ],
  coverage: DraftCoverage(
    status: 'done',
    totalRules: 1,
    issues: [],
    problems: [],
    hints: [],
  ),
  terms: DraftTerms(status: 'used'),
  pagesStale: false,
);

FakeVideoStudioRepository listRepo(VideoReadiness readiness) =>
    assetsRepo(readiness: readiness)..drafts['p1'] = draftWithAssets;

Finder inTile(String key, Finder finder) => find.descendant(
  of: find.byKey(Key('video-asset-tile-$key')),
  matching: finder,
);

void main() {
  group('素材清單', () {
    testWidgets('最上方列出還缺什麼；每個素材標示可略過（程式判斷）、代表牌、已拍／未拍、區域', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/assets',
        repo: listRepo(notReady),
      );
      final missing = find.byKey(const Key('video-readiness'));
      expect(
        find.descendant(
          of: missing,
          matching: find.textContaining('說明圖板上的兩個區域'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(of: missing, matching: find.textContaining('zone_a')),
        findsOneWidget,
      );
      expect(
        find.descendant(of: missing, matching: find.text('本版不支援繪製素材，請改成拍照')),
        findsOneWidget,
      );
      // 2026-11-22 永傑決定：不再顯示 AI 標的必拍／選拍，改顯示程式判斷的「可略過」
      expect(inTile('board', find.text('必拍')), findsNothing);
      expect(inTile('board', find.text('可略過')), findsNothing);
      expect(
        find.descendant(of: missing, matching: find.textContaining('（可略過）')),
        findsOneWidget,
      );
      expect(inTile('board', find.text('未拍')), findsOneWidget);
      expect(inTile('board', find.text('區域 0／2')), findsOneWidget);
      expect(inTile('card', find.text('可略過')), findsOneWidget);
      expect(inTile('card', find.text('代表牌')), findsOneWidget);
      expect(inTile('card', find.text('已拍')), findsOneWidget);
    });

    testWidgets('全部齊了：顯示「可以產生影片」，區域已標好', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/assets',
        repo: listRepo(readyNone),
      );
      expect(find.text('可以產生影片'), findsOneWidget);
      expect(inTile('board', find.text('區域已標好')), findsOneWidget);
    });

    testWidgets('點素材：進到單一素材頁', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/assets',
        repo: listRepo(notReady),
      );
      await tapKey(tester, 'video-asset-tile-board');
      expect(h.path, '/videos/p1/assets/board');
    });
  });

  group('拍照與預覽', () {
    testWidgets('拍攝說明顯示在拍照畫面上方；還沒有照片時按「拍照或選圖」上傳', (tester) async {
      final picker = FakeImagePicker()..images = [picked()];
      final repo = assetsRepo();
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board',
        repo: repo,
        picker: picker,
      );
      final shot = find.byKey(const Key('video-asset-shot'));
      expect(
        find.descendant(of: shot, matching: find.text('整張圖板，從正上方拍')),
        findsOneWidget,
      );
      final pick = find.byKey(const Key('video-asset-pick'));
      expect(tester.getTopLeft(shot).dy, lessThan(tester.getTopLeft(pick).dy));
      expect(find.text('還沒有照片'), findsOneWidget);

      await tapText(tester, '拍照或選圖');
      expect(repo.uploads, hasLength(1));
      expect(find.byKey(const Key('video-asset-photo')), findsOneWidget);
      expect(find.text('重拍或換一張'), findsOneWidget);
    });

    testWidgets('上傳失敗：顯示原因', (tester) async {
      final picker = FakeImagePicker()..images = [picked()];
      final repo = assetsRepo()
        ..uploadError = const ApiException(
          code: 'RULES_VIDEO_PHOTO_INVALID',
          message: '只能上傳 JPEG 或 PNG 照片',
          statusCode: 422,
        );
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board',
        repo: repo,
        picker: picker,
      );
      await tapText(tester, '拍照或選圖');
      expect(find.text('只能上傳 JPEG 或 PNG 照片'), findsOneWidget);
    });

    testWidgets('換照片後：提示重新確認區域', (tester) async {
      final picker = FakeImagePicker()..images = [picked(jpegBytes)];
      final repo = assetsRepo(
        asset: sampleAsset(
          hasPhoto: true,
          regions: {
            'zone_a': [0.1, 0.1, 0.2, 0.2],
          },
        ),
        photo: pngBytes,
      );
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board',
        repo: repo,
        picker: picker,
      );
      await tapText(tester, '重拍或換一張');
      expect(find.text('換了照片，請重新確認區域'), findsOneWidget);
    });

    testWidgets('旋轉按鈕在照片右上角；按下存方向，預覽跟著轉', (tester) async {
      final repo = assetsRepo(
        asset: sampleAsset(hasPhoto: true),
        photo: pngBytes,
      );
      await pumpVideo(tester, location: '/videos/p1/assets/board', repo: repo);
      final photo = find.byKey(const Key('video-asset-photo'));
      final rotate = find.byKey(const Key('video-asset-rotate'));
      expect(
        tester.getCenter(rotate).dx,
        greaterThan(tester.getCenter(photo).dx),
      );
      expect(tester.getCenter(rotate).dy, lessThan(tester.getCenter(photo).dy));

      await tapKey(tester, 'video-asset-rotate');
      expect(repo.updates.single.$3.orientation, 90);
      final rotated = tester.widget<RotatedBox>(
        find.descendant(of: photo, matching: find.byType(RotatedBox)),
      );
      expect(rotated.quarterTurns, 1);
    });

    testWidgets('看原圖：全螢幕顯示', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board',
        repo: assetsRepo(asset: sampleAsset(hasPhoto: true), photo: pngBytes),
      );
      await tapText(tester, '看原圖');
      expect(find.byKey(const Key('video-asset-full-photo')), findsOneWidget);
    });

    testWidgets('有照片與區域：「標區域」前往標區域頁', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/assets/board',
        repo: assetsRepo(asset: sampleAsset(hasPhoto: true), photo: pngBytes),
      );
      await tapKey(tester, 'video-asset-regions');
      expect(h.path, '/videos/p1/assets/board/regions');
    });
  });

  group('標區域', () {
    FakeVideoStudioRepository regionsRepo() =>
        assetsRepo(asset: sampleAsset(hasPhoto: true), photo: pngBytes);

    Future<void> drag(WidgetTester tester, Offset from, Offset to) async {
      // 慢慢拖（分很多步），模擬手指拖框
      final gesture = await tester.startGesture(from);
      const steps = 10;
      for (var i = 1; i <= steps; i++) {
        await gesture.moveTo(Offset.lerp(from, to, i / steps)!);
        await tester.pump();
      }
      await gesture.up();
      await tester.pumpAndSettle();
    }

    Rect editorRect(WidgetTester tester) =>
        tester.getRect(find.byKey(const Key('video-region-editor')));

    testWidgets('每次都顯示「用四個角對齊框線」；區域清單顯示進度與名稱', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board/regions',
        repo: regionsRepo(),
      );
      expect(find.text('用四個角對齊框線'), findsOneWidget);
      expect(find.text('已標 0／2'), findsOneWidget);
      expect(find.byKey(const Key('video-region-chip-zone_a')), findsOneWidget);
      expect(find.byKey(const Key('video-region-chip-zone_b')), findsOneWidget);
    });

    testWidgets('依序拖出 2 個區域並儲存：存相對比例', (tester) async {
      final repo = regionsRepo();
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/assets/board/regions',
        repo: repo,
      );
      final rect = editorRect(tester);
      Offset at(double x, double y) =>
          rect.topLeft + Offset(rect.width * x, rect.height * y);

      await drag(tester, at(0.1, 0.1), at(0.4, 0.6));
      expect(find.text('已標 1／2'), findsOneWidget);
      // 標完一個自動換到下一個還沒標的
      await drag(tester, at(0.6, 0.2), at(0.9, 0.8));
      expect(find.text('已標 2／2'), findsOneWidget);

      await tapKey(tester, 'video-regions-save');
      final regions = repo.updates.single.$3.regions!;
      expect(regions['zone_a']![0], closeTo(0.1, 0.02));
      expect(regions['zone_a']![2], closeTo(0.3, 0.02));
      expect(regions['zone_b']![1], closeTo(0.2, 0.02));
      expect(regions['zone_b']![3], closeTo(0.6, 0.02));
      expect(h.path, '/videos/p1/assets/board');
    });

    testWidgets('拖角落微調、拖中間移動', (tester) async {
      final repo = assetsRepo(
        asset: sampleAsset(
          hasPhoto: true,
          regions: {
            'zone_a': [0.2, 0.2, 0.4, 0.4],
          },
        ),
        photo: pngBytes,
      );
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board/regions',
        repo: repo,
      );
      final rect = editorRect(tester);
      Offset at(double x, double y) =>
          rect.topLeft + Offset(rect.width * x, rect.height * y);

      // 右下角 (0.6, 0.6) 拖到 (0.8, 0.7)
      await drag(tester, at(0.6, 0.6), at(0.8, 0.7));
      // 中間 (0.4, 0.4) 往左移 0.1
      await drag(tester, at(0.4, 0.4), at(0.3, 0.4));
      await tapKey(tester, 'video-regions-save');
      final box = repo.updates.single.$3.regions!['zone_a']!;
      expect(box[0], closeTo(0.1, 0.02));
      expect(box[1], closeTo(0.2, 0.02));
      expect(box[2], closeTo(0.6, 0.02));
      expect(box[3], closeTo(0.5, 0.02));
    });

    testWidgets('角的把手看得到 24px、可點範圍至少 44px', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board/regions',
        repo: assetsRepo(
          asset: sampleAsset(
            hasPhoto: true,
            regions: {
              'zone_a': [0.2, 0.2, 0.4, 0.4],
            },
          ),
          photo: pngBytes,
        ),
      );
      final handle = find.byKey(const Key('video-region-handle-0'));
      expect(tester.getSize(handle), const Size(24, 24));
      final hit = find.byKey(const Key('video-region-handle-hit-0'));
      expect(tester.getSize(hit).width, greaterThanOrEqualTo(44));
      expect(tester.getSize(hit).height, greaterThanOrEqualTo(44));
    });

    testWidgets('框太小：不能儲存並提示', (tester) async {
      await pumpVideo(
        tester,
        location: '/videos/p1/assets/board/regions',
        repo: regionsRepo(),
      );
      final rect = editorRect(tester);
      final from = rect.topLeft + Offset(rect.width * 0.5, rect.height * 0.5);
      await drag(tester, from, from + const Offset(1, 40));
      expect(find.text('框太小，請拉大一點'), findsOneWidget);
      final save = find.byKey(const Key('video-regions-save'));
      expect(tester.widget<FilledButton>(save).onPressed, isNull);
    });

    testWidgets('標到一半離開：提示還沒儲存；已儲存的保留', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/assets/board',
        repo: regionsRepo(),
      );
      await tapKey(tester, 'video-asset-regions');
      final rect = editorRect(tester);
      await drag(
        tester,
        rect.topLeft + Offset(rect.width * 0.1, rect.height * 0.1),
        rect.topLeft + Offset(rect.width * 0.5, rect.height * 0.5),
      );
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      expect(find.text('還有沒儲存的區域，要離開嗎？'), findsOneWidget);
      await tapText(tester, '繼續標');
      expect(h.path, '/videos/p1/assets/board/regions');

      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      await tapText(tester, '離開');
      expect(h.path, '/videos/p1/assets/board');
    });
  });

  group('草稿之後', () {
    // 整本範圍（D17）：草稿只顯示摘要、不擋流程；「確認草稿」改成「下一步：拍素材」
    testWidgets('「下一步：拍素材」前往素材清單', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1/draft',
        repo: listRepo(notReady),
      );
      await tapKey(tester, 'video-draft-next');
      expect(h.path, '/videos/p1/assets');
    });

    testWidgets('專案總覽：有草稿時可以點「素材」', (tester) async {
      final h = await pumpVideo(
        tester,
        location: '/videos/p1',
        repo: listRepo(notReady),
      );
      // 整本範圍（D17）：步驟只剩草稿、素材、影片，「素材」是第 2 個（index 1）
      await tapKey(tester, 'video-step-1');
      expect(h.path, '/videos/p1/assets');
    });
  });
}
