import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_client.dart';
import 'package:tabletop_hub/core/config/app_config.dart';
import 'package:tabletop_hub/core/dev/data/dev_users_repository.dart';
import 'package:tabletop_hub/core/dev/state/dev_user_state.dart';

import '../../support/fakes.dart';

ProviderContainer makeContainer({
  bool dev = true,
  FakeDevUsersRepository? repo,
}) {
  final container = ProviderContainer(
    overrides: [
      appConfigProvider.overrideWithValue(
        AppConfig(
          apiBaseUrl: 'http://api.test',
          showPrototypes: false,
          devUserEnabled: dev,
        ),
      ),
      devUsersRepositoryProvider.overrideWithValue(
        repo ?? FakeDevUsersRepository(),
      ),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

Future<String?> sendAndGetHeader(ProviderContainer container) async {
  final dio = container.read(dioProvider);
  final adapter = RecordingAdapter();
  dio.httpClientAdapter = adapter;
  await dio.get<dynamic>('/api/v1/health');
  return adapter.requests.single.headers['X-Dev-User'] as String?;
}

void main() {
  test('開發環境預設身分是 player，不帶店家', () async {
    final container = makeContainer();
    await container.read(devUsersProvider.future);
    expect(await sendAndGetHeader(container), 'u-player:player');
  });

  test('切換為 shop_staff 時帶 :<shop_id>', () async {
    final container = makeContainer();
    await container.read(devUsersProvider.future);
    container.read(selectedDevUserIdProvider.notifier).select('u-staff');
    expect(await sendAndGetHeader(container), 'u-staff:shop_staff:s-shop');
  });

  test('切換為 admin 時不帶店家', () async {
    final container = makeContainer();
    await container.read(devUsersProvider.future);
    container.read(selectedDevUserIdProvider.notifier).select('u-admin');
    expect(await sendAndGetHeader(container), 'u-admin:admin');
  });

  test('正式環境不帶標頭，也不呼叫 /dev/users', () async {
    final repo = FakeDevUsersRepository();
    final container = makeContainer(dev: false, repo: repo);
    expect(await sendAndGetHeader(container), isNull);
    expect(repo.callCount, 0);
  });

  test('清單載入失敗時不帶標頭，請求仍可送出', () async {
    final container = makeContainer(
      repo: FakeDevUsersRepository(error: Exception('boom')),
    );
    expect(await sendAndGetHeader(container), isNull);
  });

  test('清單尚未載入完成時不帶標頭', () async {
    final container = makeContainer();
    // 不等待 devUsersProvider：請求當下仍在載入。
    expect(await sendAndGetHeader(container), isNull);
  });

  test('清單為空時不帶標頭', () async {
    final container = makeContainer(repo: FakeDevUsersRepository(users: []));
    await container.read(devUsersProvider.future);
    expect(await sendAndGetHeader(container), isNull);
  });
}
