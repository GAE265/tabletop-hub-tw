import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/config/app_config.dart';
import '../domains/health/pages/health_page.dart';
import '../prototypes/health/health_proto_page.dart';
import 'shell.dart';

/// 路由表。`/proto/...` 只有在 `SHOW_PROTOTYPES=true` 時才註冊，正式部署看不到。
GoRouter createRouter(AppConfig config) => GoRouter(
  routes: [
    ShellRoute(
      builder: (context, state, child) => AppShell(child: child),
      routes: [
        GoRoute(path: '/', builder: (context, state) => const HealthPage()),
        if (config.showPrototypes)
          GoRoute(
            path: '/proto/health',
            builder: (context, state) => const HealthProtoPage(),
          ),
      ],
    ),
  ],
  errorBuilder: (context, state) =>
      const Scaffold(body: Center(child: Text('找不到頁面'))),
);

final routerProvider = Provider<GoRouter>((ref) {
  final router = createRouter(ref.watch(appConfigProvider));
  ref.onDispose(router.dispose);
  return router;
});
