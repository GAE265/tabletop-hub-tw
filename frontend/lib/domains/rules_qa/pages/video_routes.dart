import 'package:go_router/go_router.dart';

import 'video_asset_page.dart';
import 'video_assets_page.dart';
import 'video_draft_page.dart';
import 'video_project_form_page.dart';
import 'video_project_page.dart';
import 'video_projects_page.dart';
import 'video_regions_page.dart';
import 'video_render_page.dart';
import 'video_rulebook_page.dart';
import 'video_watch_page.dart';
import 'widgets/video_studio_widgets.dart';

/// 規則影片生產器的路由（add-rules-video-mobile design.md D12；D17 拿掉選頁與確認差異）。
/// 每一頁都先檢查身分。
final videoStudioRoute = GoRoute(
  path: '/videos',
  builder: (context, state) =>
      const VideoAccessGuard(child: VideoProjectsPage()),
  routes: [
    GoRoute(
      path: 'new',
      builder: (context, state) =>
          const VideoAccessGuard(child: VideoProjectFormPage()),
    ),
    GoRoute(
      path: ':id',
      builder: (context, state) => VideoAccessGuard(
        child: VideoProjectPage(projectId: state.pathParameters['id']!),
      ),
      routes: [
        GoRoute(
          path: 'rulebook',
          builder: (context, state) => VideoAccessGuard(
            child: VideoRulebookPage(projectId: state.pathParameters['id']!),
          ),
        ),
        GoRoute(
          path: 'draft',
          builder: (context, state) => VideoAccessGuard(
            child: VideoDraftPage(projectId: state.pathParameters['id']!),
          ),
        ),
        GoRoute(
          path: 'render',
          builder: (context, state) => VideoAccessGuard(
            child: VideoRenderPage(projectId: state.pathParameters['id']!),
          ),
        ),
        GoRoute(
          path: 'watch',
          builder: (context, state) => VideoAccessGuard(
            child: VideoWatchPage(projectId: state.pathParameters['id']!),
          ),
        ),
        GoRoute(
          path: 'assets',
          builder: (context, state) => VideoAccessGuard(
            child: VideoAssetsPage(projectId: state.pathParameters['id']!),
          ),
          routes: [
            GoRoute(
              path: ':key',
              builder: (context, state) => VideoAccessGuard(
                child: VideoAssetPage(
                  projectId: state.pathParameters['id']!,
                  assetKey: state.pathParameters['key']!,
                ),
              ),
              routes: [
                GoRoute(
                  path: 'regions',
                  builder: (context, state) => VideoAccessGuard(
                    child: VideoRegionsPage(
                      projectId: state.pathParameters['id']!,
                      assetKey: state.pathParameters['key']!,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ],
    ),
  ],
);
