// 用一句話修改（MR 12）的測試共用資料（自編）。草稿沿用換素材的 swapDraft()（s1、s2 兩段）。
import 'package:tabletop_hub/domains/rules_qa/data/video_studio_models.dart';

import '../../support/fakes.dart';

/// s1 的金框改成紅框；s2 的字幕改了、旁白也被改了（沒被要求）。
const proposalSegments = [
  RevisionSegment(
    segmentKey: 's1',
    segmentNumber: 1,
    summary: 'h1 的框線由金色改為紅色',
    changed: ['highlights'],
    unrequested: [],
  ),
  RevisionSegment(
    segmentKey: 's2',
    segmentNumber: 2,
    summary: '字幕改短',
    changed: ['narration', 'subtitle'],
    unrequested: ['narration'],
    beats: [
      RevisionBeat(
        beatKey: 'b2',
        before: RevisionText(narration: '再看一次紅牌。', subtitle: '紅牌'),
        after: RevisionText(narration: '再看紅牌。', subtitle: '看紅牌'),
      ),
    ],
  ),
];

VideoRevision proposalRevision({bool many = false}) => sampleVideoRevision(
  status: VideoJobStatus.succeeded,
  outcome: 'proposal',
  segments: proposalSegments,
  manySegments: many,
);

VideoRevision unsupportedRevision() => sampleVideoRevision(
  request: '標題旋轉著飛進來',
  status: VideoJobStatus.succeeded,
  outcome: 'unsupported',
  reason: '沒有旋轉動作',
  alternatives: const [
    RevisionAlternative(
      number: 1,
      title: '改成淡入',
      description: '標題用淡入出現',
      segments: [
        RevisionSegment(
          segmentKey: 's1',
          segmentNumber: 1,
          summary: '標題改成淡入',
          changed: ['cues'],
          unrequested: [],
        ),
      ],
    ),
    RevisionAlternative(number: 2, title: '改成彈出', description: '標題用彈出出現'),
  ],
);

VideoRevision ambiguousRevision() => sampleVideoRevision(
  request: '移除藍牌講慢一點',
  status: VideoJobStatus.succeeded,
  outcome: 'ambiguous',
  reason: '兩段都在講移除藍牌',
  candidates: const [
    RevisionCandidate(segmentKey: 's1', segmentNumber: 1, reason: '情況一移除藍牌'),
    RevisionCandidate(segmentKey: 's2', segmentNumber: 2, reason: '情況二移除藍牌'),
  ],
);

VideoRevision failedRevision() => sampleVideoRevision(
  status: VideoJobStatus.failed,
  error: 'AI 改了兩次都沒有通過檢查，請換個說法，或指定要改哪一段再試一次',
);

VideoRevision runningRevision() =>
    sampleVideoRevision(status: VideoJobStatus.running, message: 'AI 修改中');
