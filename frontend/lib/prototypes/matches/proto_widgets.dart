import 'package:flutter/material.dart';

import '../../core/api/api_exception.dart';

String formatDate(DateTime value) =>
    '${value.year}-${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';

/// 後端回的錯誤：訊息與錯誤碼；座位被回合擋下時多顯示回合編號。
class ErrorLine extends StatelessWidget {
  const ErrorLine(this.error, {super.key});

  final ApiException error;

  @override
  Widget build(BuildContext context) {
    final turns = error.details['turn_numbers'];
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Text(
        '錯誤：${error.message}（${error.code}）'
        '${turns is List ? '　相關回合：${turns.join('、')}' : ''}',
        key: const Key('error-line'),
      ),
    );
  }
}

class SuccessLine extends StatelessWidget {
  const SuccessLine(this.message, {super.key});

  final String message;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Text('完成：$message', key: const Key('message-line')),
  );
}

/// 欄位的錯誤訊息（小字）。
class FieldErrorText extends StatelessWidget {
  const FieldErrorText(this.message, {super.key});

  final String? message;

  @override
  Widget build(BuildContext context) =>
      message == null ? const SizedBox.shrink() : Text(message!);
}

/// 「已經有人記錄了，要更新嗎？」的提示與兩個按鈕。
class OverwritePromptCard extends StatelessWidget {
  const OverwritePromptCard({
    required this.text,
    required this.existing,
    required this.onConfirm,
    required this.onCancel,
    this.busy = false,
    super.key,
  });

  final String text;

  /// 既有紀錄的簡述，讓使用者知道要蓋掉什麼。
  final String existing;
  final VoidCallback onConfirm;
  final VoidCallback onCancel;
  final bool busy;

  @override
  Widget build(BuildContext context) => Card(
    key: const Key('overwrite-prompt'),
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(text),
          Text('既有紀錄：$existing'),
          Row(
            children: [
              FilledButton(
                key: const Key('overwrite-confirm'),
                onPressed: busy ? null : onConfirm,
                child: const Text('更新'),
              ),
              TextButton(
                key: const Key('overwrite-cancel'),
                onPressed: busy ? null : onCancel,
                child: const Text('取消'),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}
