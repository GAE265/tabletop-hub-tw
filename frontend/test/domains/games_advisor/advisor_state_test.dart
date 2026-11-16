import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tabletop_hub/core/api/api_exception.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_message.dart';
import 'package:tabletop_hub/domains/games_advisor/data/advisor_repository.dart';
import 'package:tabletop_hub/domains/games_advisor/state/advisor_state.dart';

import '../../support/fakes.dart';

// spec §14.2 的 state/ 測試表，加上 MR 說明標 ➕ 的情境。

const card = AdvisorRecommendation(
  game: AdvisorGame(
    id: 1,
    name: '範例桌遊甲',
    minPlayers: 2,
    maxPlayers: 4,
    minPlaytime: 30,
    maxPlaytime: 45,
    minAge: 10,
    weight: 1.85,
  ),
  reason: '規則簡單、不燒腦，符合你想要的輕鬆路線。',
  excerpts: [AdvisorExcerpt(id: 'e1', text: '一局節奏很快', language: 'zh-TW')],
);

AdvisorMessageResponse reply({
  String? responseId = 'resp_1',
  String text = '幫你找到 1 款適合 4 個人的桌遊。',
  RelaxedConstraint? relaxedConstraint,
  List<AdvisorRecommendation> recommendations = const [],
}) => AdvisorMessageResponse(
  responseId: responseId,
  reply: text,
  relaxedConstraint: relaxedConstraint,
  recommendations: recommendations,
);

ApiException apiError(int statusCode, String code) =>
    ApiException(code: code, message: '測試用錯誤', statusCode: statusCode);

late FakeAdvisorRepository repo;
late ProviderContainer container;

/// 模擬畫面正在看這個狀態；關掉就等於離開頁面。
late ProviderSubscription<AdvisorState> screen;

AdvisorState get state => container.read(advisorProvider);
AdvisorNotifier get advisor => container.read(advisorProvider.notifier);

/// 送出一則訊息，並讓假的 repository 回 201。
Future<void> exchange(String content, AdvisorMessageResponse response) async {
  final done = advisor.sendMessage(content);
  repo.respond(response);
  await done;
}

/// 送出一則訊息，並讓假的 repository 拋出錯誤。
Future<void> failWith(String content, Object error) async {
  final done = advisor.sendMessage(content);
  repo.fail(error);
  await done;
}

void expectInitial(AdvisorState s, {String draft = '', AdvisorNotice? notice}) {
  expect(s.messages, isEmpty);
  expect(s.responseId, isNull);
  expect(s.status, AdvisorStatus.idle);
  expect(s.draft, draft);
  expect(s.notice, notice);
}

void main() {
  setUp(() {
    repo = FakeAdvisorRepository();
    container = ProviderContainer(
      overrides: [advisorRepositoryProvider.overrideWithValue(repo)],
    );
    screen = container.listen(advisorProvider, (_, _) {});
  });

  tearDown(() => container.dispose());

  test('新對話：全部是初始值，不能送出、不能開始新對話', () {
    expectInitial(state);
    expect(state.canSend, isFalse);
    expect(state.canStartNew, isFalse);
  });

  test('輸入「  4 人  」：可以送出', () {
    advisor.editDraft('  4 人  ');
    expect(state.draft, '  4 人  ');
    expect(state.canSend, isTrue);
    expect(state.canStartNew, isTrue);
  });

  group('字數限制（去掉前後空白後 1–500 字）', () {
    test('只有空白：不能送出，按了也不呼叫 repository', () async {
      advisor.editDraft('   ');
      expect(state.canSend, isFalse);
      await advisor.sendMessage(state.draft);
      expect(repo.requests, isEmpty);
      expect(state.messages, isEmpty);
    });

    test('501 字：不能送出，按了也不呼叫 repository', () async {
      advisor.editDraft('字' * 501);
      expect(state.canSend, isFalse);
      await advisor.sendMessage(state.draft);
      expect(repo.requests, isEmpty);
    });

    test('剛好 500 字：可以送出', () {
      advisor.editDraft('字' * 500);
      expect(state.canSend, isTrue);
    });

    test('emoji 算 1 字，和後端一樣：500 個可以、501 個不行', () {
      advisor.editDraft('🎲' * 500);
      expect(state.canSend, isTrue);
      advisor.editDraft('🎲' * 501);
      expect(state.canSend, isFalse);
    });
  });

  test('送出：帶去掉空白的文字與 null，玩家訊息加進去，清空輸入框與提示', () async {
    // 先讓上一次送出失敗，畫面上才有提示可以清
    await failWith('4 人', apiError(503, 'GAMES_ADVISOR_UNAVAILABLE'));
    expect(state.notice, AdvisorNotice.unavailable);

    advisor.editDraft('  4 人  ');
    unawaited(advisor.sendMessage(state.draft));

    final request = repo.requests.last;
    expect(request.content, '4 人');
    expect(request.previousResponseId, isNull);
    expect(state.status, AdvisorStatus.sending);
    expect(state.messages, hasLength(1));
    expect((state.messages.single as PlayerMessage).text, '4 人');
    expect(state.draft, '');
    expect(state.notice, isNull);
  });

  test('送出中再送：不呼叫 repository，訊息不變', () async {
    unawaited(advisor.sendMessage('4 人'));
    await advisor.sendMessage('2 個人約會玩');
    expect(repo.requests, hasLength(1));
    expect(state.messages, hasLength(1));
  });

  test('收到推薦：回到 idle、換成新的 responseId，推薦 Agent 的訊息有 reply、卡片、放寬的條件', () async {
    await exchange(
      '4 人',
      reply(
        responseId: 'resp_1',
        text: '幫你找到 1 款，放寬了時長。',
        relaxedConstraint: RelaxedConstraint.playtime,
        recommendations: [card],
      ),
    );

    expect(state.status, AdvisorStatus.idle);
    expect(state.responseId, 'resp_1');
    expect(state.messages, hasLength(2));
    final message = state.messages.last as AdvisorReplyMessage;
    expect(message.reply, '幫你找到 1 款，放寬了時長。');
    expect(message.recommendations, [card]);
    expect(message.relaxedConstraint, RelaxedConstraint.playtime);
  });

  test('第二則訊息：帶上一則的 responseId', () async {
    await exchange('4 人', reply(responseId: 'resp_1'));
    unawaited(advisor.sendMessage('想輕鬆聊天'));
    expect(repo.requests.last.previousResponseId, 'resp_1');
  });

  test('收到固定文字：responseId 是舊 id，訊息照常顯示', () async {
    await exchange('4 人', reply(responseId: 'resp_1'));
    await exchange('幫我寫作業', reply(responseId: 'resp_1', text: '固定文字'));

    expect(state.responseId, 'resp_1');
    expect(state.messages, hasLength(4));
    final message = state.messages.last as AdvisorReplyMessage;
    expect(message.reply, '固定文字');
    expect(message.recommendations, isEmpty);
  });

  test('對話過期（404）：回到初始狀態，剛剛那句放回輸入框，提示 expired', () async {
    await exchange('4 人', reply(responseId: 'resp_1'));
    await failWith(
      '  想輕鬆聊天 ',
      apiError(404, 'GAMES_ADVISOR_CONVERSATION_NOT_FOUND'),
    );
    expectInitial(state, draft: '想輕鬆聊天', notice: AdvisorNotice.expired);
  });

  group('暫時無法回應：拿掉剛剛那則、放回輸入框、responseId 不變', () {
    final errors = <String, Object>{
      '503': apiError(503, 'GAMES_ADVISOR_UNAVAILABLE'),
      '500': apiError(500, 'INTERNAL_ERROR'),
      '422': apiError(422, 'VALIDATION_ERROR'),
      '斷線': const ApiException(
        code: ApiException.networkErrorCode,
        message: '無法連線到伺服器',
      ),
      '回應格式不對（不是 ApiException 的錯誤）': const FormatException('回應格式不對'),
    };

    for (final MapEntry(key: name, value: error) in errors.entries) {
      test(name, () async {
        await exchange('4 人', reply(responseId: 'resp_1'));
        await failWith('想輕鬆聊天', error);

        expect(state.status, AdvisorStatus.idle);
        expect(state.messages, hasLength(2)); // 前面的對話保留
        expect((state.messages.first as PlayerMessage).text, '4 人');
        expect(state.draft, '想輕鬆聊天');
        expect(state.notice, AdvisorNotice.unavailable);
        expect(state.responseId, 'resp_1');
      });
    }
  });

  test('開始新對話：回到初始狀態，不呼叫 repository', () async {
    await exchange('4 人', reply(responseId: 'resp_1'));
    advisor.editDraft('還沒送出的字');
    expect(state.canStartNew, isTrue);

    advisor.startNewConversation();

    expectInitial(state);
    expect(repo.requests, hasLength(1));
  });

  test('送出中開始新對話：不動作', () {
    unawaited(advisor.sendMessage('4 人'));
    expect(state.canStartNew, isFalse);

    advisor.startNewConversation();

    expect(state.status, AdvisorStatus.sending);
    expect(state.messages, hasLength(1));
  });

  test('過期後：有提示與輸入框內容，可以開始新對話', () async {
    await failWith(
      '4 人',
      apiError(404, 'GAMES_ADVISOR_CONVERSATION_NOT_FOUND'),
    );
    expect(state.canStartNew, isTrue);

    advisor.editDraft(''); // 只剩提示也可以
    expect(state.canStartNew, isTrue);

    advisor.startNewConversation();
    expectInitial(state);
  });

  test('範例按鈕：和送出相同，不看輸入框原本的內容', () {
    advisor.editDraft('   ');
    expect(state.canSend, isFalse);

    unawaited(advisor.sendMessage('我們 4 個人，想輕鬆聊天'));

    final request = repo.requests.single;
    expect(request.content, '我們 4 個人，想輕鬆聊天');
    expect(request.previousResponseId, isNull);
    expect(state.status, AdvisorStatus.sending);
    expect((state.messages.single as PlayerMessage).text, '我們 4 個人，想輕鬆聊天');
    expect(state.draft, '');
  });

  group('離開頁面就是新對話', () {
    test('離開頁面再回來：回到初始狀態', () async {
      await exchange('4 人', reply(responseId: 'resp_1'));
      advisor.editDraft('還沒送出的字');

      screen.close();
      await container.pump();

      expectInitial(container.read(advisorProvider));
    });

    test('送出中離開頁面：回應之後才回來，不出錯，看到的是新對話', () async {
      final done = advisor.sendMessage('4 人');

      screen.close();
      await container.pump();
      repo.respond(reply(responseId: 'resp_1'));
      await done;

      expectInitial(container.read(advisorProvider));
    });
  });
}
