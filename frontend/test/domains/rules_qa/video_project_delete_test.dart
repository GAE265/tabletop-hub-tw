// 刪除影片專案的 state（2026-11-24 永傑決定，最小版）：成功後重新載入專案列表；
// 正在產生草稿或影片時後端回 409，顯示後端的說明。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_repository.dart';
import 'package:tabletop_hub/domains/rules_qa/state/video_projects_state.dart';

import '../../support/fakes.dart';

ProviderContainer makeContainer(FakeVideoStudioRepository repo) {
  final container = ProviderContainer(
    overrides: [videoStudioRepositoryProvider.overrideWithValue(repo)],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('刪除成功：呼叫 deleteProject，回傳 true，專案列表重新載入', () async {
    final repo = FakeVideoStudioRepository(
      projects: [
        sampleVideoProject(),
        sampleVideoProject(id: 'p2'),
      ],
    );
    final container = makeContainer(repo);
    expect(await container.read(videoProjectsProvider.future), hasLength(2));
    final sub = container.listen(videoProjectDeleteProvider('p1'), (_, _) {});
    addTearDown(sub.close);

    final ok = await container
        .read(videoProjectDeleteProvider('p1').notifier)
        .delete();

    expect(ok, isTrue);
    expect(repo.deletedProjects, ['p1']);
    final state = container.read(videoProjectDeleteProvider('p1'));
    expect(state.deleting, isFalse);
    expect(state.error, isNull);
    final projects = await container.read(videoProjectsProvider.future);
    expect(projects.map((p) => p.id), ['p2']);
  });

  test('正在產生草稿或影片（409）：回傳 false，顯示後端的說明', () async {
    final repo = FakeVideoStudioRepository(projects: [sampleVideoProject()])
      ..deleteProjectError = const ApiException(
        code: 'RULES_VIDEO_PROJECT_BUSY',
        message: '正在產生草稿或影片，完成後再刪除',
        statusCode: 409,
      );
    final container = makeContainer(repo);
    final sub = container.listen(videoProjectDeleteProvider('p1'), (_, _) {});
    addTearDown(sub.close);

    final ok = await container
        .read(videoProjectDeleteProvider('p1').notifier)
        .delete();

    expect(ok, isFalse);
    expect(repo.deletedProjects, isEmpty);
    final state = container.read(videoProjectDeleteProvider('p1'));
    expect(state.deleting, isFalse);
    expect(state.error, '正在產生草稿或影片，完成後再刪除');
  });

  test('刪除中再按一次：不重複送出', () async {
    final repo = FakeVideoStudioRepository(projects: [sampleVideoProject()]);
    final container = makeContainer(repo);
    final sub = container.listen(videoProjectDeleteProvider('p1'), (_, _) {});
    addTearDown(sub.close);
    final notifier = container.read(videoProjectDeleteProvider('p1').notifier);

    final results = await Future.wait([notifier.delete(), notifier.delete()]);

    expect(results, [isTrue, isFalse]);
    expect(repo.deletedProjects, ['p1']);
  });
}
