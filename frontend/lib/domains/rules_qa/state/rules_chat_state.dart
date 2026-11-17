import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../data/rules_qa_models.dart';
import '../data/rules_qa_repository.dart';

/// 問題字數上限（與後端相同）。
const rulesQaMaxContentLength = 500;

/// 後端的「對話已過期」錯誤代碼。
const rulesQaConversationNotFoundCode = 'RULES_QA_CONVERSATION_NOT_FOUND';

int _contentLength(String text) => text.trim().runes.length;

bool _isSendable(String text) {
  final length = _contentLength(text);
  return length >= 1 && length <= rulesQaMaxContentLength;
}

/// 出處的顯示文字，例如「規則書第 12 頁」。
String citationText(Citation citation) => '規則書第 ${citation.page} 頁';

sealed class RulesChatMessage {
  const RulesChatMessage();
}

class QuestionMessage extends RulesChatMessage {
  const QuestionMessage(this.text);

  final String text;
}

class AnswerMessage extends RulesChatMessage {
  const AnswerMessage({
    required this.answer,
    required this.answerable,
    required this.citations,
  });

  final String answer;

  /// 教材中找不到答案時為 false，此時沒有出處。
  final bool answerable;
  final List<Citation> citations;
}

enum RulesChatStatus { idle, sending }

/// 需要提示玩家的狀況。
enum RulesChatNotice {
  /// 對話已過期，已經幫玩家開始新對話。
  expired,
}

class RulesChatState {
  const RulesChatState({
    this.messages = const [],
    this.responseId,
    this.status = RulesChatStatus.idle,
    this.draft = '',
    this.notice,
    this.error,
  });

  final List<RulesChatMessage> messages;

  /// 上一則回答的 id，追問時帶給後端；新對話是 null。
  final String? responseId;
  final RulesChatStatus status;

  /// 輸入框內容。送出時清空、失敗時放回，畫面要跟著更新輸入框。
  final String draft;
  final RulesChatNotice? notice;

  /// 後端回傳的錯誤訊息。
  final String? error;

  int get draftLength => _contentLength(draft);

  bool get canSend => status == RulesChatStatus.idle && _isSendable(draft);

  bool get canStartNew =>
      status == RulesChatStatus.idle && (messages.isNotEmpty || notice != null);

  RulesChatState copyWith({
    List<RulesChatMessage>? messages,
    String? Function()? responseId,
    RulesChatStatus? status,
    String? draft,
    RulesChatNotice? Function()? notice,
    String? Function()? error,
  }) => RulesChatState(
    messages: messages ?? this.messages,
    responseId: responseId == null ? this.responseId : responseId(),
    status: status ?? this.status,
    draft: draft ?? this.draft,
    notice: notice == null ? this.notice : notice(),
    error: error == null ? this.error : error(),
  );
}

/// 某款遊戲的規則問答對話。離開頁面就重置，對話不存進瀏覽器。
class RulesChatNotifier extends Notifier<RulesChatState> {
  RulesChatNotifier(this.gameId);

  final int gameId;

  @override
  RulesChatState build() => const RulesChatState();

  void editDraft(String text) => state = state.copyWith(draft: text);

  /// 送出問題；送出中或內容不合規定時不做任何事。
  Future<void> send(String content) async {
    if (state.status == RulesChatStatus.sending || !_isSendable(content)) {
      return;
    }
    final text = content.trim();
    final request = RulesMessageRequest(
      content: text,
      previousResponseId: state.responseId,
    );
    state = state.copyWith(
      messages: [...state.messages, QuestionMessage(text)],
      status: RulesChatStatus.sending,
      draft: '',
      notice: () => null,
      error: () => null,
    );

    try {
      final answer = await ref
          .read(rulesQaRepositoryProvider)
          .sendMessage(gameId, request);
      if (!ref.mounted) return;
      state = state.copyWith(
        status: RulesChatStatus.idle,
        responseId: () => answer.responseId,
        messages: [
          ...state.messages,
          AnswerMessage(
            answer: answer.answer,
            answerable: answer.answerable,
            citations: answer.answerable ? answer.citations : const [],
          ),
        ],
      );
    } catch (error) {
      if (!ref.mounted) return;
      state = _failed(error, text);
    }
  }

  void startNewConversation() {
    if (state.status == RulesChatStatus.sending) return;
    state = const RulesChatState();
  }

  RulesChatState _failed(Object error, String text) {
    if (error is ApiException &&
        error.code == rulesQaConversationNotFoundCode) {
      // 對話已過期：清空，幫玩家開始新對話，問題留在輸入框讓玩家重送
      return RulesChatState(draft: text, notice: RulesChatNotice.expired);
    }
    // 其他錯誤：拿掉剛剛那句、放回輸入框，前面的對話保留
    return state.copyWith(
      status: RulesChatStatus.idle,
      messages: state.messages.sublist(0, state.messages.length - 1),
      draft: text,
      error: () => error is ApiException ? error.message : '發生未知錯誤，請再試一次',
    );
  }
}

final rulesChatProvider = NotifierProvider.autoDispose
    .family<RulesChatNotifier, RulesChatState, int>(RulesChatNotifier.new);
