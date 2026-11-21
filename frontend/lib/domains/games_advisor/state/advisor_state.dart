import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:freezed_annotation/freezed_annotation.dart';

import '../../../core/api/api_exception.dart';
import '../data/advisor_message.dart';
import '../data/advisor_repository.dart';

part 'advisor_state.freezed.dart';

/// ⚠️ 和後端 MESSAGE_MAX_CHARS 同步：去掉前後空白後最多 500 字。
const advisorMaxContentLength = 500;

/// ⚠️ 和後端 spec §13.2 同步：對話過期或 id 錯。
const advisorConversationNotFoundCode = 'GAMES_ADVISOR_CONVERSATION_NOT_FOUND';

/// 字數：去掉前後空白後計算，一個 emoji 算 1 字，和後端的算法一樣。
int advisorContentLength(String text) => text.trim().runes.length;

bool _isSendable(String text) {
  final length = advisorContentLength(text);
  return length >= 1 && length <= advisorMaxContentLength;
}

enum AdvisorStatus { idle, sending }

/// 錯誤提示。推薦 Agent 不用登入就能用，所以沒有「請先登入」。
enum AdvisorNotice {
  /// 對話已失效，請開始新對話。
  expired,

  /// 推薦 Agent 暫時無法回應，請再送一次。
  unavailable,
}

/// 對話裡的一則訊息：玩家的，或推薦 Agent 的。
sealed class AdvisorChatMessage {
  const AdvisorChatMessage();
}

/// 玩家送出的訊息，文字已去掉前後空白。
class PlayerMessage extends AdvisorChatMessage {
  const PlayerMessage(this.text);

  final String text;
}

/// 推薦 Agent 的回覆。追問、離題、固定文字時 [recommendations] 是空的。
class AdvisorReplyMessage extends AdvisorChatMessage {
  const AdvisorReplyMessage({
    required this.reply,
    required this.recommendations,
    required this.relaxedConstraint,
  });

  final String reply;
  final List<AdvisorRecommendation> recommendations;
  final RelaxedConstraint? relaxedConstraint;
}

/// 推薦 Agent 畫面的狀態（spec §14.2）。
@freezed
abstract class AdvisorState with _$AdvisorState {
  const AdvisorState._();

  const factory AdvisorState({
    @Default(<AdvisorChatMessage>[]) List<AdvisorChatMessage> messages,

    /// 前端保管的最新 `response_id`，下一則訊息帶回去。
    String? responseId,
    @Default(AdvisorStatus.idle) AdvisorStatus status,

    /// 輸入框內容。
    @Default('') String draft,
    AdvisorNotice? notice,
  }) = _AdvisorState;

  /// 輸入框下方顯示的字數。
  int get draftLength => advisorContentLength(draft);

  /// 送出鈕能不能按：不在送出中，而且去掉空白後 1–500 字。
  bool get canSend => status == AdvisorStatus.idle && _isSendable(draft);

  /// 「開始新對話」能不能按：不在送出中，而且有訊息、提示或輸入框內容。
  bool get canStartNew =>
      status == AdvisorStatus.idle &&
      (messages.isNotEmpty || notice != null || draft.isNotEmpty);
}

/// 推薦 Agent 的對話與操作。參考畫面（prototypes）與正式頁面（pages）共用這一份。
class AdvisorNotifier extends Notifier<AdvisorState> {
  AdvisorNotifier([this.shopId]);

  /// 玩家是從哪間店進到推薦頁的；這段對話的每一則訊息都帶上，開始新對話也不變。
  /// 沒有店家時是 null。
  final String? shopId;

  @override
  AdvisorState build() => const AdvisorState();

  /// 輸入框內容改變。
  void editDraft(String text) => state = state.copyWith(draft: text);

  /// 送出一則訊息。送出鈕傳 `draft`，範例按鈕傳範例文字。
  /// 正在送出中、或去掉空白後不是 1–500 字時不動作。
  Future<void> sendMessage(String content) async {
    if (state.status == AdvisorStatus.sending || !_isSendable(content)) return;

    final text = content.trim();
    final request = AdvisorMessageRequest(
      content: text,
      previousResponseId: state.responseId,
      shopId: shopId,
    );
    state = state.copyWith(
      messages: [...state.messages, PlayerMessage(text)],
      status: AdvisorStatus.sending,
      draft: '',
      notice: null,
    );

    try {
      final response = await ref
          .read(advisorRepositoryProvider)
          .sendMessage(request);
      // 送出中離開頁面：狀態已經丟掉，回應不用接上去
      if (!ref.mounted) return;
      // ✅ 201：推薦、追問、固定文字都走這裡；固定文字時 responseId 是舊 id
      state = state.copyWith(
        status: AdvisorStatus.idle,
        responseId: response.responseId,
        messages: [
          ...state.messages,
          AdvisorReplyMessage(
            reply: response.reply,
            recommendations: response.recommendations,
            relaxedConstraint: response.relaxedConstraint,
          ),
        ],
      );
    } catch (error) {
      if (!ref.mounted) return;
      state = _failed(error, text);
    }
  }

  /// 回到初始狀態，不呼叫 API。送出中不動作，避免回應接到新的對話上。
  void startNewConversation() {
    if (state.status == AdvisorStatus.sending) return;
    state = const AdvisorState();
  }

  /// 送出失敗：剛剛那句放回輸入框。
  /// 對話過期就整個清空；其他錯誤只拿掉剛剛那則，前面的對話與 responseId 保留。
  AdvisorState _failed(Object error, String text) {
    if (error is ApiException &&
        error.code == advisorConversationNotFoundCode) {
      return AdvisorState(draft: text, notice: AdvisorNotice.expired);
    }
    return state.copyWith(
      status: AdvisorStatus.idle,
      messages: state.messages.sublist(0, state.messages.length - 1),
      draft: text,
      notice: AdvisorNotice.unavailable,
    );
  }
}

/// 網址的 `shop_id` 轉成對話要帶的店家 id：沒帶或是空的就是沒有店家（null）。
String? advisorShopIdFromQuery(Map<String, String> query) {
  final shopId = query['shop_id']?.trim() ?? '';
  return shopId.isEmpty ? null : shopId;
}

/// 帶著某間店的對話；參數是店家 id，沒有店家給 null。
/// 離開頁面就丟掉（autoDispose）；也不存進瀏覽器，所以重新整理或換頁回來都是新對話。
final advisorForShopProvider = NotifierProvider.autoDispose
    .family<AdvisorNotifier, AdvisorState, String?>(AdvisorNotifier.new);

/// 沒有店家的對話。
final advisorProvider = advisorForShopProvider(null);
