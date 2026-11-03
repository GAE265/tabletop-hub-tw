import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/layout/breakpoints.dart';

void main() {
  test('斷點邊界：599、600、1023、1024', () {
    expect(screenSizeForWidth(599), ScreenSize.mobile);
    expect(screenSizeForWidth(600), ScreenSize.tablet);
    expect(screenSizeForWidth(1023), ScreenSize.tablet);
    expect(screenSizeForWidth(1024), ScreenSize.desktop);
  });
}
