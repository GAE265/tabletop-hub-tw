/// 一局的狀態與地點的顯示名稱。
String statusLabel(String status) => switch (status) {
  'in_progress' => '進行中',
  'finished' => '已結束',
  _ => status,
};

String locationLabel(String locationType) => switch (locationType) {
  'shop' => '桌遊店',
  'home' => '自家',
  _ => locationType,
};
