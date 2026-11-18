/// 訂位相關 DTO。JSON 欄位為後端 snake_case，Dart 內部用 camelCase。
class Fee {
  const Fee({required this.billableHours, required this.venueFee});

  factory Fee.fromJson(Map<String, dynamic> json) => Fee(
    billableHours: json['billable_hours'].toString(),
    venueFee: json['venue_fee'].toString(),
  );

  final String billableHours;
  final String venueFee;
}

class Booking {
  const Booking({
    required this.id,
    required this.reservationCode,
    required this.shopId,
    required this.shopName,
    required this.startAt,
    required this.endAt,
    required this.partySize,
    required this.status,
    required this.tableCodes,
    required this.estimatedFee,
    this.finalFee,
    this.notice,
  });

  factory Booking.fromJson(Map<String, dynamic> json) => Booking(
    id: json['id'] as int,
    reservationCode: json['reservation_code'] as String,
    shopId: json['shop_id'] as String,
    shopName: json['shop_name'] as String? ?? '',
    startAt: json['start_at'] as String,
    endAt: json['end_at'] as String,
    partySize: json['party_size'] as int,
    status: json['status'] as String,
    tableCodes: [
      for (final t in json['tables'] as List) (t as Map)['table_code'] as String,
    ],
    estimatedFee: Fee.fromJson(json['estimated_fee'] as Map<String, dynamic>),
    finalFee: json['final_fee']?.toString(),
    notice: json['notice'] as String?,
  );

  final int id;
  final String reservationCode;
  final String shopId;
  final String shopName;
  final String startAt;
  final String endAt;
  final int partySize;
  final String status;
  final List<String> tableCodes;
  final Fee estimatedFee;
  final String? finalFee;
  final String? notice;
}

class BookingPage {
  const BookingPage({required this.items, required this.total});

  factory BookingPage.fromJson(Map<String, dynamic> json) => BookingPage(
    items: [
      for (final i in json['items'] as List)
        Booking.fromJson(i as Map<String, dynamic>),
    ],
    total: json['total'] as int,
  );

  final List<Booking> items;
  final int total;
}

class QuoteResult {
  const QuoteResult({
    required this.startAt,
    required this.endAt,
    required this.fee,
    this.tableCodes = const [],
  });

  factory QuoteResult.fromJson(Map<String, dynamic> json) => QuoteResult(
    startAt: json['start_at'] as String,
    endAt: json['end_at'] as String,
    fee: Fee.fromJson(json['fee'] as Map<String, dynamic>),
    tableCodes: (json['table_codes'] as List?)?.cast<String>() ?? [],
  );

  final String startAt;
  final String endAt;
  final Fee fee;
  final List<String> tableCodes;
}



/// 桌位資訊（座位圖上的單張桌子）。
class TableInfo {
  const TableInfo({
    required this.id,
    required this.tableCode,
    this.name,
    required this.maxCapacity,
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    required this.shape,
    required this.status,
    this.booking,
  });

  factory TableInfo.fromJson(Map<String, dynamic> json) => TableInfo(
    id: json['id'] as int,
    tableCode: json['table_code'] as String,
    name: json['name'] as String?,
    maxCapacity: json['max_capacity'] as int,
    x: json['x'] as int,
    y: json['y'] as int,
    width: json['width'] as int,
    height: json['height'] as int,
    shape: json['shape'] as String,
    status: json['status'] as String,
    booking: json['booking'] != null
        ? BookingSummary.fromJson(json['booking'] as Map<String, dynamic>)
        : null,
  );

  final int id;
  final String tableCode;
  final String? name;
  final int maxCapacity;
  final int x;
  final int y;
  final int width;
  final int height;
  final String shape;
  final String status; // "available" | "unavailable"
  final BookingSummary? booking;

  /// 是否被自己佔用（玩家自己的訂位）。
  bool get isMine => booking != null;
}

/// 訂位摘要（附在桌位狀態上）。
class BookingSummary {
  const BookingSummary({
    required this.id,
    required this.reservationCode,
    required this.userId,
    required this.startAt,
    required this.endAt,
    required this.partySize,
    required this.status,
  });

  factory BookingSummary.fromJson(Map<String, dynamic> json) => BookingSummary(
    id: json['id'] as int,
    reservationCode: json['reservation_code'] as String,
    userId: json['user_id'] as String,
    startAt: json['start_at'] as String,
    endAt: json['end_at'] as String,
    partySize: json['party_size'] as int,
    status: json['status'] as String,
  );

  final int id;
  final String reservationCode;
  final String userId;
  final String startAt;
  final String endAt;
  final int partySize;
  final String status;
}

/// 一個樓層的座位圖。
class SeatingPlan {
  const SeatingPlan({required this.floor, required this.tables});

  factory SeatingPlan.fromJson(Map<String, dynamic> json) => SeatingPlan(
    floor: json['floor'] as int,
    tables: [
      for (final t in json['tables'] as List)
        TableInfo.fromJson(t as Map<String, dynamic>),
    ],
  );

  final int floor;
  final List<TableInfo> tables;
}
