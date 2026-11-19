// 請求內容。日期以 `yyyy-MM-dd` 送出（沒有時區的日曆日期）。
String _date(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';

/// `POST /api/v1/matches`：開局。
///
/// [locationType] 是 `shop` 時 [shopId] 必填；`home`（自家）時不可帶 [shopId]。
/// [seatNumber] 是開局者自己的座位，不帶時後端給最小的空位。
class MatchInput {
  const MatchInput({
    required this.gameId,
    required this.playedOn,
    required this.locationType,
    this.shopId,
    this.groupId,
    this.progress,
    this.seatNumber,
  });

  final int gameId;
  final DateTime playedOn;
  final String locationType;
  final String? shopId;
  final String? groupId;
  final String? progress;
  final int? seatNumber;

  Map<String, dynamic> toJson() => {
    'game_id': gameId,
    'played_on': _date(playedOn),
    'location_type': locationType,
    if (shopId != null) 'shop_id': shopId,
    if (groupId != null) 'group_id': groupId,
    if (progress != null) 'progress': progress,
    if (seatNumber != null) 'seat_number': seatNumber,
  };
}

/// `POST /api/v1/matches/{id}/participants`。
///
/// 不帶 [displayName]＝自己加入（有帳號）；帶 [displayName]＝新增沒有帳號的人（例如 Amy）。
class ParticipantInput {
  const ParticipantInput({this.displayName, this.seatNumber});

  final String? displayName;
  final int? seatNumber;

  Map<String, dynamic> toJson() => {
    if (displayName != null) 'display_name': displayName,
    if (seatNumber != null) 'seat_number': seatNumber,
  };
}

/// 《血與刃的白薔薇》一個回合的內容（幽魂不記）。
class WhiteRoseTurnData {
  const WhiteRoseTurnData({
    required this.playedSeatNumbers,
    this.doubleBladeCount = 0,
    this.darkBladeCount = 0,
    this.giantBladeCount = 0,
    this.faithfulCount = 0,
    this.hasWhiteRose = false,
  });

  /// 這回合出牌的座位編號，至少一個、不可重複。
  final List<int> playedSeatNumbers;
  final int doubleBladeCount;
  final int darkBladeCount;
  final int giantBladeCount;
  final int faithfulCount;
  final bool hasWhiteRose;

  Map<String, dynamic> toJson() => {
    'played_seat_numbers': playedSeatNumbers,
    'double_blade_count': doubleBladeCount,
    'dark_blade_count': darkBladeCount,
    'giant_blade_count': giantBladeCount,
    'faithful_count': faithfulCount,
    'has_white_rose': hasWhiteRose,
  };
}

/// `POST /api/v1/matches/{id}/turns`：記錄一個回合。
///
/// [seatNumber] 是本回合首家的座位，選填，沒選時送 null；[gameData] 的格式依遊戲而定。
class TurnInput {
  const TurnInput({
    required this.turnNumber,
    this.seatNumber,
    required this.gameData,
  });

  final int turnNumber;
  final int? seatNumber;
  final Map<String, dynamic> gameData;

  Map<String, dynamic> toJson() => {
    'turn_number': turnNumber,
    'seat_number': seatNumber,
    'game_data': gameData,
  };
}

/// `PUT /api/v1/matches/{id}/result`：陣營勝負的結果。
///
/// [factions] 的鍵是座位編號，必須涵蓋這局全部座位。是否獲勝由後端依陣營計算。
class ResultInput {
  const ResultInput({required this.winningFaction, required this.factions});

  final String winningFaction;
  final Map<int, String> factions;

  Map<String, dynamic> toJson() => {
    'winning_faction': winningFaction,
    'participants': [
      for (final entry in factions.entries)
        {'seat_number': entry.key, 'faction': entry.value},
    ],
  };
}
