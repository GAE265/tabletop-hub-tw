import '../data/host_models.dart';
import 'host_controller.dart';

/// 目前唯一支援語音主持的遊戲（規則教學頁用遊戲名稱判斷要不要顯示入口）。
const hostGameName = '血與刃的白薔薇';

/// 回合內三個階段的名稱（spec §3.1）。
const hostPhaseNames = {1: '傳金幣、放水晶', 2: '決定出牌', 3: '翻牌結算'};

const _stepNames = {
  HostStep.opening: '開場',
  HostStep.setup: '開局準備',
  HostStep.night1: '夜晚第一步',
  HostStep.night2: '夜晚第二步',
  HostStep.turn: '回合',
  HostStep.ended: '結束',
};

/// 目前進度：回合內是「第 N 回合某階段」，開場到夜晚是節點名稱。
/// 已結束時保留結束前的回合與階段，所以也照回合顯示。
String hostProgressLabel(HostStep step, int? turnNumber, int? phaseNumber) {
  if (turnNumber != null && phaseNumber != null) {
    return '第 $turnNumber 回合${hostPhaseNames[phaseNumber] ?? '階段 $phaseNumber'}';
  }
  return _stepNames[step]!;
}

/// 「暫停／繼續」那顆按鍵的文字：暫停中變成「繼續」。
String pauseButtonLabel(HostState state) => state.paused ? '繼續' : '暫停';
