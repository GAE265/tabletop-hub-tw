// 規則問答的對話（spec：rules-qa-page 的「問答」）。
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/rules_qa/state/rules_chat_state.dart';

import '../../support/fakes.dart';
import 'support.dart';

const gameId = 2;

void main() {
  late FakeRulesQaRepository repo;
  late RulesChatNotifier chat;
  late RulesChatState Function() state;

  setUp(() {
    repo = sampleRepo();
    final container = makeContainer(repo);
    container.listen(rulesChatProvider(gameId), (_, _) {});
    chat = container.read(rulesChatProvider(gameId).notifier);
    state = () => container.read(rulesChatProvider(gameId));
  });

  test('發問並得到答案：對話依序出現，回答附頁碼', () async {
    final pending = chat.send('怎麼計分？');
    repo.respond(answer(text: '依手牌分數加總。', pages: [12]));
    await pending;

    final messages = state().messages;
    expect((messages[0] as QuestionMessage).text, '怎麼計分？');
    final reply = messages[1] as AnswerMessage;
    expect(reply.answer, '依手牌分數加總。');
    expect(reply.citations.map(citationText), ['規則書第 12 頁']);
    expect(repo.requests.single.$1, gameId);
    expect(repo.requests.single.$2.previousResponseId, isNull);
  });

  test('追問：帶上一則回答的 response_id', () async {
    final first = chat.send('怎麼計分？');
    repo.respond(answer(responseId: 'r-1'));
    await first;
    final second = chat.send('那兩個人玩呢？');
    repo.respond(answer(responseId: 'r-2'));
    await second;
    expect(repo.requests[1].$2.previousResponseId, 'r-1');
    expect(state().responseId, 'r-2');
  });

  test('找不到答案：回答沒有出處', () async {
    final pending = chat.send('可以作弊嗎？');
    repo.respond(answer(answerable: false, pages: []));
    await pending;
    final reply = state().messages.last as AnswerMessage;
    expect(reply.answerable, isFalse);
    expect(reply.citations, isEmpty);
  });

  test('開始新對話：清空紀錄，下一題 previous_response_id 為 null', () async {
    final first = chat.send('怎麼計分？');
    repo.respond(answer());
    await first;
    chat.startNewConversation();
    expect(state().messages, isEmpty);
    expect(state().responseId, isNull);

    final next = chat.send('怎麼開始一局？');
    repo.respond(answer());
    await next;
    expect(repo.requests.last.$2.previousResponseId, isNull);
  });

  test('對話已失效：清空並提示，問題留在輸入框', () async {
    final first = chat.send('怎麼計分？');
    repo.respond(answer());
    await first;
    final second = chat.send('那兩個人玩呢？');
    repo.fail(
      const ApiException(
        code: rulesQaConversationNotFoundCode,
        message: '對話已過期',
        statusCode: 404,
      ),
    );
    await second;
    expect(state().messages, isEmpty);
    expect(state().responseId, isNull);
    expect(state().notice, RulesChatNotice.expired);
    expect(state().draft, '那兩個人玩呢？');
  });

  test('送出失敗：顯示後端訊息，問題留在輸入框，之前的對話保留', () async {
    final first = chat.send('怎麼計分？');
    repo.respond(answer());
    await first;
    final second = chat.send('那兩個人玩呢？');
    repo.fail(
      const ApiException(
        code: 'RULES_QA_UNAVAILABLE',
        message: '規則問答暫時無法使用，請稍後再試',
        statusCode: 503,
      ),
    );
    await second;
    expect(state().error, '規則問答暫時無法使用，請稍後再試');
    expect(state().draft, '那兩個人玩呢？');
    expect(state().messages, hasLength(2));
    expect(state().status, RulesChatStatus.idle);
  });

  test('送出中：不能重複送出', () async {
    final first = chat.send('怎麼計分？');
    expect(state().status, RulesChatStatus.sending);
    expect(state().canSend, isFalse);
    await chat.send('再問一次');
    expect(repo.requests, hasLength(1));
    repo.respond(answer());
    await first;
  });

  test('空白問題：不能送出，也不呼叫 API', () async {
    chat.editDraft('   ');
    expect(state().canSend, isFalse);
    await chat.send('   ');
    expect(repo.requests, isEmpty);
  });

  test('超過 500 字：不能送出', () async {
    chat.editDraft('字' * (rulesQaMaxContentLength + 1));
    expect(state().canSend, isFalse);
  });

  test('送出時清空輸入框，錯誤與提示也清掉', () async {
    chat.editDraft('怎麼計分？');
    final pending = chat.send('怎麼計分？');
    expect(state().draft, '');
    expect(state().error, isNull);
    repo.respond(answer());
    await pending;
  });
}
