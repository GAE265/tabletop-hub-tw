/// 訂位通知 DTO（add-booking-notifications）。JSON 欄位為後端 snake_case。
class BookingNotificationRef {
  const BookingNotificationRef({
    required this.id,
    required this.reservationCode,
    required this.shopName,
    required this.startAt,
    required this.endAt,
    required this.partySize,
  });

  factory BookingNotificationRef.fromJson(Map<String, dynamic> json) =>
      BookingNotificationRef(
        id: json['id'] as int,
        reservationCode: json['reservation_code'] as String,
        shopName: json['shop_name'] as String,
        startAt: DateTime.parse(json['start_at'] as String),
        endAt: DateTime.parse(json['end_at'] as String),
        partySize: json['party_size'] as int,
      );

  final int id;
  final String reservationCode;
  final String shopName;
  final DateTime startAt;
  final DateTime endAt;
  final int partySize;
}

class BookingNotification {
  const BookingNotification({
    required this.id,
    required this.type,
    required this.booking,
    required this.readAt,
    required this.createdAt,
  });

  factory BookingNotification.fromJson(Map<String, dynamic> json) =>
      BookingNotification(
        id: json['id'] as String,
        type: json['type'] as String,
        booking: BookingNotificationRef.fromJson(
          json['booking'] as Map<String, dynamic>,
        ),
        readAt: json['read_at'] == null
            ? null
            : DateTime.parse(json['read_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  final String id;

  /// `booking_confirmed`（給訂位的玩家）或 `shop_new_booking`（給店家人員）。
  final String type;
  final BookingNotificationRef booking;

  /// null 代表未讀。
  final DateTime? readAt;
  final DateTime createdAt;

  /// 只改已讀時間；傳 null 不會清掉（標回未讀請用原本的物件）。
  BookingNotification copyWith({DateTime? readAt}) => BookingNotification(
    id: id,
    type: type,
    booking: booking,
    readAt: readAt ?? this.readAt,
    createdAt: createdAt,
  );
}

class BookingNotificationPage {
  const BookingNotificationPage({
    required this.items,
    required this.total,
    required this.unreadCount,
  });

  factory BookingNotificationPage.fromJson(Map<String, dynamic> json) =>
      BookingNotificationPage(
        items: [
          for (final i in json['items'] as List)
            BookingNotification.fromJson(i as Map<String, dynamic>),
        ],
        total: json['total'] as int,
        unreadCount: json['unread_count'] as int,
      );

  final List<BookingNotification> items;
  final int total;

  /// 全部未讀數，不受分頁影響。
  final int unreadCount;
}
