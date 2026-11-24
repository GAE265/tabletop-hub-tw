// 新的品牌 logo（2026-11-24 永傑決定）：回到放 logo 之前的排法，左邊是正方形的 logo 圖案，
// 右邊用文字顯示「遊任有娛」（titleLarge、w700，系統字型），不放「PLAY · GAME · FUN」。
// 網站分頁圖示與加到手機主畫面的圖示也換成新的正方形 logo。
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/app/navigation.dart';

import 'navigation_test.dart' show logoImage, pumpShell;

/// 收集這次畫面的所有錯誤（例如 RenderFlex overflowed）。
List<String> takeErrors(WidgetTester tester) {
  final errors = <String>[];
  for (var e = tester.takeException(); e != null; e = tester.takeException()) {
    errors.add('$e'.split('\n').first);
  }
  return errors;
}

/// 解出圖檔的寬、高與每個像素的 RGBA。
Future<(int, int, ByteData)> decode(WidgetTester tester, String path) async {
  return (await tester.runAsync(() async {
    final codec = await ui.instantiateImageCodec(File(path).readAsBytesSync());
    final image = (await codec.getNextFrame()).image;
    final rgba = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
    return (image.width, image.height, rgba!);
  }))!;
}

int alphaAt(ByteData rgba, int width, int x, int y) =>
    rgba.getUint8((y * width + x) * 4 + 3);

void main() {
  test('logo 圖檔換成正方形的 logo-mark.webp，舊的橫式 logo 已移除', () {
    expect(BrandMark.asset, 'assets/images/logo-mark.webp');
    expect(File(BrandMark.asset).existsSync(), isTrue);
    expect(File('assets/images/logo-full.webp').existsSync(), isFalse);
    final pubspec = File('pubspec.yaml').readAsStringSync();
    expect(pubspec, contains('assets/images/logo-mark.webp'));
    expect(pubspec, isNot(contains('logo-full.webp')));
  });

  testWidgets('logo 圖檔是正方形、背景透明', (tester) async {
    final (width, height, rgba) = await decode(tester, BrandMark.asset);
    expect(width, height);
    expect(width, greaterThanOrEqualTo(256));
    expect(alphaAt(rgba, width, 0, 0), 0);
  });

  group('手機頂部列', () {
    testWidgets('正方形 logo（高 60）加上「遊任有娛」，沒有 PLAY · GAME · FUN', (tester) async {
      await pumpShell(tester, size: const Size(400, 900));
      final bar = find.byType(MobileTopBar);
      final logo = find.descendant(of: bar, matching: logoImage);
      expect(tester.getSize(logo), const Size(60, 60));
      final name = find.descendant(of: bar, matching: find.text('遊任有娛'));
      expect(name, findsOneWidget);
      expect(tester.widget<Text>(name).style!.fontWeight, FontWeight.w700);
      expect(find.textContaining('PLAY'), findsNothing);
      // 名稱在 logo 右邊
      expect(
        tester.getTopLeft(name).dx,
        greaterThan(tester.getTopRight(logo).dx),
      );
    });

    testWidgets('讀屏只念一次「遊任有娛」', (tester) async {
      final handle = tester.ensureSemantics();
      await pumpShell(tester, size: const Size(400, 900));
      expect(
        find.descendant(
          of: find.byType(MobileTopBar),
          matching: find.bySemanticsLabel('遊任有娛'),
        ),
        findsOneWidget,
      );
      handle.dispose();
    });

    for (final width in [320.0, 360.0, 390.0, 430.0]) {
      testWidgets('手機寬 $width：頂部列不超出，鈴鐺與登入都在畫面內', (tester) async {
        await pumpShell(tester, size: Size(width, 900));
        expect(takeErrors(tester), isEmpty);
        final login = find.byKey(const Key('shell-login'));
        expect(tester.getTopRight(login).dx, lessThanOrEqualTo(width));
        expect(
          find.descendant(
            of: find.byType(MobileTopBar),
            matching: find.text('遊任有娛'),
          ),
          findsOneWidget,
        );
      });
    }

    testWidgets('字放大（1.3 倍）、手機寬 320：不超出', (tester) async {
      tester.platformDispatcher.textScaleFactorTestValue = 1.3;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await pumpShell(tester, size: const Size(320, 900));
      expect(takeErrors(tester), isEmpty);
    });
  });

  testWidgets('桌機頂部導覽列：正方形 logo（高 44）加上「遊任有娛」', (tester) async {
    await pumpShell(tester, size: const Size(1280, 900));
    final nav = find.byType(TopNavigation);
    final logo = find.descendant(of: nav, matching: logoImage);
    expect(tester.getSize(logo), const Size(44, 44));
    expect(
      find.descendant(of: nav, matching: find.text('遊任有娛')),
      findsOneWidget,
    );
  });

  group('網站圖示', () {
    for (final (path, size) in [
      ('web/favicon.png', 64),
      ('web/icons/Icon-192.png', 192),
      ('web/icons/Icon-512.png', 512),
      ('web/icons/Icon-maskable-192.png', 192),
      ('web/icons/Icon-maskable-512.png', 512),
    ]) {
      testWidgets('$path 是 $size×$size 的正方形', (tester) async {
        final (width, height, _) = await decode(tester, path);
        expect((width, height), (size, size));
      });
    }

    for (final path in [
      'web/icons/Icon-maskable-192.png',
      'web/icons/Icon-maskable-512.png',
    ]) {
      testWidgets('$path 有底色（四個角不透明，Android 裁成圓形也不會露出透明）', (tester) async {
        final (width, height, rgba) = await decode(tester, path);
        for (final (x, y) in [
          (0, 0),
          (width - 1, 0),
          (0, height - 1),
          (width - 1, height - 1),
        ]) {
          expect(alphaAt(rgba, width, x, y), 255, reason: '($x, $y)');
        }
      });
    }

    testWidgets('一般圖示與分頁圖示：四個角透明，至少兩成的面積有圖', (tester) async {
      for (final path in [
        'web/favicon.png',
        'web/icons/Icon-192.png',
        'web/icons/Icon-512.png',
      ]) {
        final (width, height, rgba) = await decode(tester, path);
        expect(alphaAt(rgba, width, 0, 0), 0, reason: path);
        var opaque = 0;
        for (var i = 3; i < rgba.lengthInBytes; i += 4) {
          if (rgba.getUint8(i) > 0) opaque++;
        }
        expect(opaque / (width * height), greaterThan(0.2), reason: path);
      }
    });
  });
}
