/// 《血與刃的白薔薇》的陣營（結果類型為 faction＝陣營勝負）。
///
/// 目前只有白薔薇有回合與結果的記錄格式；其他遊戲之後各自新增一份。
class Faction {
  const Faction(this.code, this.label);

  /// 後端使用的代碼。
  final String code;

  /// 畫面顯示的名稱。
  final String label;
}

const whiteRoseFactions = [
  Faction('rose', '薔薇陣營'),
  Faction('blood_blade', '血刃陣營'),
];

/// 陣營代碼對應的顯示名稱；沒有陣營（尚未記錄）顯示「尚未記錄」。
String factionLabel(String? code) {
  if (code == null) return '尚未記錄';
  for (final faction in whiteRoseFactions) {
    if (faction.code == code) return faction.label;
  }
  return code;
}
