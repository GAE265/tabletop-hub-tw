// 素材清單（/videos/:id/assets）的 Stitch 版面：木紋背景、步驟條、專案卡與素材進度、
// 拍攝提示、「還缺這些」與「已完成」兩個區塊、卡片上的拍照／標區域／略過、底部列。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';

import '../video_assets_support.dart';
import 'video_assets_pages_test.dart' show inTile, listRepo;
import 'video_pages_support.dart';

const assets = '/videos/p1/assets';

void expectThick(WidgetTester tester, Finder box, [String? reason]) {
  final decoration =
      tester.widget<DecoratedBox>(box).decoration as BoxDecoration;
  final border = decoration.border! as Border;
  expect(border.bottom.width, greaterThan(border.top.width), reason: reason);
  expect(decoration.boxShadow, isNotEmpty, reason: reason);
}

Finder firstBoxIn(String key) => find
    .descendant(of: find.byKey(Key(key)), matching: find.byType(DecoratedBox))
    .first;

Finder boxAround(String key) => find
    .ancestor(of: find.byKey(Key(key)), matching: find.byType(DecoratedBox))
    .first;

Finder inKey(String key, Finder finder) =>
    find.descendant(of: find.byKey(Key(key)), matching: finder);

/// 只缺圖板的兩個區域（照片都有了）。
const onlyRegions = VideoReadiness(
  ready: false,
  missingPhotos: [],
  missingRegions: [MissingRegion(assetKey: 'board', region: 'zone_a')],
  unsupported: [],
);

/// 代表牌還沒拍、可以略過，略過會影響第 3 段。
const skippableCard = VideoReadiness(
  ready: false,
  missingPhotos: [
    MissingPhoto(
      assetKey: 'card',
      priority: 'optional',
      skippable: true,
      reason: '一張代表牌',
      skipAffectedSegments: [3],
    ),
  ],
  missingRegions: [],
  unsupported: [],
);

void main() {
  testWidgets('木紋背景；步驟條標出目前在「拍攝素材」', (tester) async {
    await pumpVideo(tester, location: assets, repo: listRepo(notReady));
    expect(
      find.descendant(
        of: find.byKey(const Key('video-assets-page')),
        matching: find.byType(WoodBackground),
      ),
      findsOneWidget,
    );
    for (final label in ['生成草稿', '拍攝素材', '產生影片']) {
      expect(inKey('video-stepper', find.text(label)), findsOneWidget);
    }
    expect(inKey('video-stepper-current', find.text('拍攝素材')), findsOneWidget);
  });

  testWidgets('專案卡有厚度：桌遊、專案名稱、最後修改、素材完成進度', (tester) async {
    await pumpVideo(tester, location: assets, repo: listRepo(notReady));
    expectThick(tester, firstBoxIn('video-assets-project'));
    for (final text in ['假遊戲 規則教學', '桌遊：假遊戲', '已完成 0／2 個素材']) {
      expect(
        inKey('video-assets-project', find.text(text)),
        findsOneWidget,
        reason: text,
      );
    }
    expect(
      inKey('video-assets-project', find.textContaining('最後修改')),
      findsOneWidget,
    );
  });

  testWidgets('提示可以隨時離開，照片選好就會上傳', (tester) async {
    await pumpVideo(tester, location: assets, repo: listRepo(notReady));
    expect(inKey('video-assets-tip', find.text('拍攝中隨時可以離開這頁')), findsOneWidget);
  });

  testWidgets('還缺這些：標題條寫剩幾項；每個缺的素材一張有厚度的卡片', (tester) async {
    await pumpVideo(tester, location: assets, repo: listRepo(notReady));
    final header = find.byKey(const Key('video-assets-pending-header'));
    expect(
      find.descendant(of: header, matching: find.text('還缺這些才能產生影片')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: header, matching: find.text('剩 2 項')),
      findsOneWidget,
    );
    await tester.ensureVisible(find.byKey(const Key('video-asset-tile-board')));
    expectThick(tester, firstBoxIn('video-asset-tile-board'));
    expect(find.byKey(const Key('video-assets-done-header')), findsNothing);
  });

  testWidgets('缺照片：卡片上的「拍照或選圖」進到這個素材', (tester) async {
    final h = await pumpVideo(
      tester,
      location: assets,
      repo: listRepo(notReady),
    );
    expect(
      inTile('board', find.byKey(const Key('video-asset-regions-board'))),
      findsNothing,
    );
    await tapKey(tester, 'video-asset-shoot-board');
    expect(h.path, '/videos/p1/assets/board');
  });

  testWidgets('只缺區域：卡片上的「標區域」直接進到標區域頁', (tester) async {
    final h = await pumpVideo(
      tester,
      location: assets,
      repo: listRepo(onlyRegions),
    );
    expect(find.byKey(const Key('video-asset-shoot-board')), findsNothing);
    final regions = find.byKey(const Key('video-asset-regions-board'));
    await tester.ensureVisible(regions);
    await tester.pumpAndSettle();
    await tester.tap(regions);
    // 標區域頁讀照片時一直在轉，不等它停
    await tester.pump();
    expect(h.path, '/videos/p1/assets/board/regions');
  });

  testWidgets('可以略過的素材：寫出略過會影響哪一段；略過先確認，取消不送出', (tester) async {
    final repo = listRepo(skippableCard);
    repo.assets['p1/card'] = sampleAsset(key: 'card', regions: const {});
    await pumpVideo(tester, location: assets, repo: repo);
    expect(inTile('card', find.text('略過會影響第 3 段')), findsOneWidget);
    expect(find.byKey(const Key('video-asset-skip-board')), findsNothing);

    await tapKey(tester, 'video-asset-skip-card');
    await tapKey(tester, 'video-asset-skip-cancel');
    expect(repo.updates, isEmpty);

    await tapKey(tester, 'video-asset-skip-card');
    await tapKey(tester, 'video-asset-skip-confirm');
    final (project, key, input) = repo.updates.single;
    expect((project, key, input.skipped), ('p1', 'card', true));
  });

  testWidgets('全部齊了：「可以產生影片」，素材都在「已完成」', (tester) async {
    await pumpVideo(tester, location: assets, repo: listRepo(readyNone));
    expect(find.text('可以產生影片'), findsOneWidget);
    expect(find.byKey(const Key('video-assets-pending-header')), findsNothing);
    final done = find.byKey(const Key('video-assets-done-header'));
    await tester.ensureVisible(done);
    expect(
      find.descendant(of: done, matching: find.text('2 項')),
      findsOneWidget,
    );
  });

  testWidgets('底部列：已略過幾個、目前完成幾 %；「下一步」是有厚度的按鈕，還缺時不能按', (tester) async {
    await pumpVideo(tester, location: assets, repo: listRepo(notReady));
    final bar = find.byKey(const Key('video-assets-bar'));
    expect(
      find.descendant(of: bar, matching: find.text('已略過 0 個素材')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: bar, matching: find.text('目前完成 0%')),
      findsOneWidget,
    );
    expectThick(tester, boxAround('video-assets-next'));
    final next = tester.widget<ButtonStyleButton>(
      find.byKey(const Key('video-assets-next')),
    );
    expect(next.onPressed, isNull);
  });
}
