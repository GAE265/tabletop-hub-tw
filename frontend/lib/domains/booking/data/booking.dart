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

class QuoteItem {
  const QuoteItem({
    required this.startAt,
    required this.endAt,
    required this.fee,
  });

  factory QuoteItem.fromJson(Map<String, dynamic> json) => QuoteItem(
    startAt: json['start_at'] as String,
    endAt: json['end_at'] as String,
    fee: Fee.fromJson(json['fee'] as Map<String, dynamic>),
  );

  final String startAt;
  final String endAt;
  final Fee fee;
}

/// 一個時段，時間為 ISO 8601 字串（含時區）。
class Slot {
  const Slot({required this.startAt, required this.endAt});

  final String startAt;
  final String endAt;

  Map<String, dynamic> toJson() => {'start_at': startAt, 'end_at': endAt};
}
