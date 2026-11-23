// 影片生產器各頁的 Stitch 版面：木紋背景，文字放在有厚度的卡片上（不再用 Card），
// 按鈕都是有厚度、按得下去的厚按鈕（不再用 OutlinedButton 與一般的 FilledButton）；
// 專案總覽加上步驟條；底部按鈕列也是厚卡片。
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/theme/thick_widgets.dart';
import 'package:tabletop_hub/app/theme/wood_background.dart';
import 'package:tabletop_hub/domains/rules_qa/pages/widgets/video_studio_widgets.dart';

import '../../../support/fakes.dart';
import '../video_assets_support.dart';
import 'video_pages_support.dart';
import 'video_render_pages_test.dart' show renderRepo, sampleRender;
import 'video_rulebook_pages_test.dart' show photoRepo;
import 'video_studio_pages_test.dart' show draftOf, draftRepo;

/// 每一頁要檢查的網址、頁面 Key 與假資料。
final pages = <(String, String, FakeVideoStudioRepository Function())>[
  (
    '/videos',
    'video-projects-page',
    () => FakeVideoStudioRepository(projects: [sampleVideoProject()]),
  ),
  ('/videos/new', 'video-project-form-page', FakeVideoStudioRepository.new),
  ('/videos/p1', 'video-project-page', () => draftRepo(draftOf())),
  ('/videos/p1/rulebook', 'video-rulebook-page', photoRepo),
  ('/videos/p1/draft', 'video-draft-page', () => draftRepo(draftOf())),
  ('/videos/p1/assets/board', 'video-asset-page', assetsRepo),
  (
    '/videos/p1/assets/board/regions',
    'video-regions-page',
    () => assetsRepo(asset: sampleAsset(hasPhoto: true), photo: pngBytes),
  ),
  ('/videos/p1/render', 'video-render-page', renderRepo),
  (
    '/videos/p1/watch',
    'video-watch-page',
    () =>
        renderRepo(step: 'done', render: sampleRender)
          ..renderVideos['p1'] = Uint8List.fromList(List.filled(2048, 1)),
  ),
];

void main() {
  for (final (location, pageKey, repo) in pages) {
    group(location, () {
      Finder inPage(Finder finder) =>
          find.descendant(of: find.byKey(Key(pageKey)), matching: finder);

      testWidgets('木紋背景', (tester) async {
        await pumpVideo(tester, location: location, repo: repo());
        expect(inPage(find.byType(WoodBackground)), findsOneWidget);
      });

      testWidgets('卡片都有厚度（不用 Card），沒有 OutlinedButton', (tester) async {
        await pumpVideo(tester, location: location, repo: repo());
        expect(inPage(find.byType(Card)), findsNothing);
        expect(inPage(find.byType(OutlinedButton)), findsNothing);
      });

      testWidgets('實心按鈕都是厚按鈕', (tester) async {
        await pumpVideo(tester, location: location, repo: repo());
        final buttons = inPage(find.byType(FilledButton));
        for (final element in buttons.evaluate()) {
          expect(
            find.ancestor(
              of: find.byWidget(element.widget),
              matching: find.byType(ThickButton),
            ),
            findsWidgets,
            reason: '${element.widget.key}',
          );
        }
      });
    });
  }

  testWidgets('專案總覽：步驟條標出目前這一步', (tester) async {
    await pumpVideo(
      tester,
      location: '/videos/p1',
      repo: FakeVideoStudioRepository(projects: [sampleVideoProject()]),
    );
    expect(find.byKey(const Key('video-stepper')), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('video-stepper-current')),
        matching: find.text('生成草稿'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('底部按鈕列是厚卡片', (tester) async {
    await pumpVideo(
      tester,
      location: '/videos/p1/draft',
      repo: draftRepo(draftOf()),
    );
    final bar = find.byType(VideoBottomActions);
    expect(bar, findsOneWidget);
    final decoration =
        tester
                .widget<DecoratedBox>(
                  find
                      .descendant(of: bar, matching: find.byType(DecoratedBox))
                      .first,
                )
                .decoration
            as BoxDecoration;
    final border = decoration.border! as Border;
    expect(border.bottom.width, greaterThan(border.top.width));
  });
}
