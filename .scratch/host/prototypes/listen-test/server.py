"""Ticket 07 listening test: talk to a Qwen-Audio realtime "host" from the browser.

PROTOTYPE, throwaway. Not project code; nothing here goes into backend/ or frontend/.

    browser (mic + speaker, index.html)  <->  this relay (holds the key)  <->  Qwen realtime (wss)

The relay also plays "backend": it runs the fake rule-lookup tool and the "ask the referee"
tool (a text model), so we can hear how waiting, interruptions and delegation feel.

Settings (names are proposals from ticket 06):
  worktree .env: HOST_REALTIME_API_KEY, HOST_REALTIME_WORKSPACE_ID (or the whole API Host)
  referee via Azure: LLM_ENDPOINT, LLM_API_KEY, LLM_MODEL from the worktree .env or,
                     if missing there, the main checkout's .env
Secrets are never printed or sent to the browser.

Run from the worktree root, then open http://localhost:8787 in Chrome:
  uv run --no-project --with 'websockets>=14' python .scratch/host/prototypes/listen-test/server.py

Event log (no audio) goes to the system temp folder, never into the repo.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import random
import struct
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.http11 import Response

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[3]
MAIN_CHECKOUT = WORKTREE.parents[3]  # .orca/worktrees/<repo>/<worktree> -> repo root

MODELS = {
    "flash": "qwen-audio-3.1-realtime-flash",
    "plus": "qwen-audio-3.1-realtime-plus",
}

# Self-written rule notes for the test, in our own words (NOT rulebook text).
# Thresholds marked 測試用 are made up: the real numbers are printed on images we cannot read.
RULES = [
    {
        "topic": "人數與陣營",
        "keywords": ["人數", "幾個人", "幾人", "陣營", "血刃", "白薔薇陣營", "牌組", "角色", "七個", "7"],
        "text": (
            "5 到 10 人。依人數組角色牌：5 人＝白薔薇1、司教1、信者1、雙刃1、暗刃1；"
            "6 人＝信者改 2；7 人＝白薔薇1、司教1、信者2、巨刃1、雙刃1、暗刃1；"
            "8 人＝信者3、巨刃1；9 人＝信者3、巨刃2；10 人＝信者4、巨刃2（其他角色各 1）。"
            "白薔薇、司教、信者是白薔薇陣營；巨刃、雙刃、暗刃是血刃陣營。陣營整局不變。"
        ),
    },
    {
        "topic": "開局準備",
        "keywords": ["開局", "準備", "發牌", "手牌", "水晶", "魔法之書", "幽魂", "金幣"],
        "text": (
            "每人拿自己的幽魂牌、信者牌、魔法之書，再抽 1 顆白水晶（數字保密）。"
            "角色牌洗勻蓋著發，每人 1 張，所以每人手上 3 張牌。桌上另放 1 張備用雙刃。"
            "金幣先交給一位玩家。"
        ),
    },
    {
        "topic": "夜晚階段",
        "keywords": ["夜晚", "閉眼", "睜眼", "相認", "換牌", "雙刃換"],
        "text": (
            "只在開局做一次。全員閉眼；白薔薇、司教、雙刃、巨刃睜眼互看約 3 秒再閉眼。"
            "接著大家敲桌子掩護，雙刃玩家把手上的幽魂換成桌上的備用雙刃。"
        ),
    },
    {
        "topic": "階段 1：傳金幣、放水晶",
        "keywords": ["金幣", "傳", "交給", "放水晶", "階段1", "階段一", "自己"],
        "text": (
            "持幣者把金幣交給另一位手上還有水晶的玩家，不能交給自己。"
            "拿到金幣的人放出水晶，照水晶數字執行魔法之書同編號的效果。"
            "大家可以討論，但不能明講自己的水晶數字。所有人都沒水晶時遊戲結束。"
        ),
    },
    {
        "topic": "階段 2：決定出牌",
        "keywords": ["出牌", "順序", "誰先", "不出", "蓋牌", "階段2", "階段二"],
        "text": (
            "從放水晶的人開始，順時針每人決定：蓋 1 張牌在面前，或宣布不出。每人只有一個機會。"
            "後面的人看得到前面誰出了。魔法之書第 6 項會讓放水晶的人改成最後一個決定。"
        ),
    },
    {
        "topic": "階段 3：翻牌結算",
        "keywords": ["翻牌", "結算", "刃牌", "白薔薇", "死亡區", "獻祭區", "幽魂", "階段3", "階段三"],
        "text": (
            "放水晶的人收齊蓋牌、混洗、全部翻開。沒有刃牌：幽魂移出遊戲，信者和司教進獻祭區，"
            "白薔薇進白薔薇區。有刃牌但沒有白薔薇：幽魂移出，白薔薇陣營的信者和司教進死亡區。"
            "刃牌和白薔薇同時翻出：血刃陣營立刻獲勝。翻出兩張以上刃牌和一張的效果一樣。"
        ),
    },
    {
        "topic": "勝負",
        "keywords": ["贏", "勝", "輸", "獲勝", "結束", "門檻", "花苞", "白薔薇還沒出"],
        "text": (
            "（測試用門檻）死亡區累積 2 張就是血刃陣營獲勝。獻祭區花苞（信者與司教）累積 3 張，"
            "而且白薔薇已經打出並活著，白薔薇陣營獲勝；白薔薇還沒打出就算花苞夠了也還沒贏，遊戲繼續。"
            "水晶用完還沒分勝負：白薔薇陣營手上還有花苞或白薔薇就是血刃贏，沒有就是白薔薇贏。"
            "每個回合結算完才檢查勝負。"
        ),
    },
    {
        "topic": "魔法之書效果",
        "keywords": ["魔法之書", "效果", "第", "號", "編號", "水晶數字"],
        "text": (
            "1 點名一人必須出牌；2 這回合不混洗直接翻，大家知道誰出哪張；3 抽右鄰一張牌，他只能出那張；"
            "4 同 3 但抽左鄰；5 綁定兩人，甲出乙就得出；6 放水晶的人最後決定；7 指定一人領備用幽魂；"
            "8 左右兩位有牌就必須出；9 夜間指定一人偷看；10 出完牌後可讓別人換掉打出的牌（可不發動）；"
            "11 抽一人一張牌偷看再還他；12 同 1。除了 10，其他效果條件成立就一定要發動。"
        ),
    },
    {
        "topic": "公開與私密資訊",
        "keywords": ["公開", "私密", "可以說", "能不能講", "亮牌", "誠實", "幾張"],
        "text": (
            "不能亮手牌，也不能明講水晶數字與效果。每人手牌剩幾張、誰還有水晶是公開的，被問要誠實回答。"
            "誰出牌、誰不出是公開的；翻開的牌公開，但不知道是誰出的（第 2 項效果例外）。"
        ),
    },
]

REFEREE_INSTRUCTIONS = (
    "你是桌遊《血與刃的白薔薇》的裁判，幫語音主持人回答規則問題。"
    "只根據下面的規則摘要與玩家描述的局面推理，不要用你自己的記憶補規則。"
    "答案會被直接唸給玩家聽：用繁體中文、口語、兩到三句，先講結論再講理由。"
    "規則摘要沒寫的，直接說「規則摘要沒寫」，不要猜。"
)

TOOL_LOOKUP = {
    "type": "function",
    "function": {
        "name": "lookup_rule",
        "description": "查《血與刃的白薔薇》的規則摘要。玩家問規則時先查再回答。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "要查的主題，例如：人數與陣營、出牌順序、翻牌結算、勝負、魔法之書第幾項",
                },
                "question": {"type": "string", "description": "玩家原本的問題"},
            },
            "required": ["topic", "question"],
        },
    },
}

TOOL_REFEREE = {
    "type": "function",
    "function": {
        "name": "ask_referee",
        "description": (
            "把需要多步推理的規則題交給裁判（後端的文字模型）。"
            "例如牽涉人數、多個效果同時發生、順序推算、勝負判定。拿到答案後用主持人的口吻唸出來。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "玩家的問題，完整寫出"},
                "situation": {
                    "type": "string",
                    "description": "目前局面：人數、座位、誰放水晶、翻出什麼等，玩家說過的都寫進來",
                },
            },
            "required": ["question"],
        },
    },
}


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings() -> dict[str, str]:
    values = read_env(WORKTREE / ".env")
    for key, value in os.environ.items():
        if key.startswith(("HOST_REALTIME_", "LLM_")) and value:
            values[key] = value
    if not values.get("HOST_REALTIME_API_KEY"):
        sys.exit(f"缺少 HOST_REALTIME_API_KEY（放在 {WORKTREE / '.env'}）")
    raw = values.get("HOST_REALTIME_API_HOST") or values.get("HOST_REALTIME_WORKSPACE_ID", "")
    host = raw.removeprefix("https://").removeprefix("wss://").split("/")[0]
    if not host:
        sys.exit("缺少 HOST_REALTIME_WORKSPACE_ID 或 HOST_REALTIME_API_HOST")
    if "." not in host:
        host = f"{host}.{values.get('HOST_REALTIME_REGION', 'ap-southeast-1')}.maas.aliyuncs.com"
    values["_HOST"] = host
    if not values.get("LLM_ENDPOINT"):
        main_env = read_env(MAIN_CHECKOUT / ".env")
        for key in ("LLM_ENDPOINT", "LLM_API_KEY", "LLM_MODEL", "LLM_REASONING_EFFORT"):
            if main_env.get(key):
                values[key] = main_env[key]
    return values


def lookup_rules(topic: str, question: str) -> dict:
    text = f"{topic} {question}"
    scored = []
    for rule in RULES:
        score = sum(1 for k in rule["keywords"] if k in text)
        if rule["topic"] in text:
            score += 3
        if score:
            scored.append((score, rule))
    scored.sort(key=lambda pair: -pair[0])
    if not scored:
        return {"found": False, "note": "規則摘要裡找不到相關內容"}
    return {
        "found": True,
        "results": [{"topic": r["topic"], "text": r["text"]} for _, r in scored[:2]],
    }


def http_post_json(url: str, body: dict, api_key: str, timeout: float = 40) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def ask_referee_sync(settings: dict[str, str], cfg: dict, question: str, situation: str) -> dict:
    rules = "\n".join(f"【{r['topic']}】{r['text']}" for r in RULES)
    system = f"{REFEREE_INSTRUCTIONS}\n\n規則摘要：\n{rules}"
    user = f"玩家的問題：{question}\n目前局面：{situation or '（沒有提供）'}"
    backend = cfg.get("referee_backend", "azure")
    try:
        if backend == "azure":
            if not settings.get("LLM_ENDPOINT"):
                return {"error": "沒有 Azure 設定（LLM_ENDPOINT）"}
            body = {"model": settings["LLM_MODEL"], "instructions": system, "input": user}
            effort = cfg.get("referee_effort") or settings.get("LLM_REASONING_EFFORT")
            if effort:
                body["reasoning"] = {"effort": effort}
            data = http_post_json(
                settings["LLM_ENDPOINT"].rstrip("/") + "/responses", body, settings["LLM_API_KEY"]
            )
            answer = "".join(
                part.get("text", "")
                for item in data.get("output", [])
                if item.get("type") == "message"
                for part in item.get("content", [])
            )
            return {"answer": answer, "model": settings["LLM_MODEL"]}
        model = cfg.get("referee_qwen_model", "qwen3.8-flash")
        data = http_post_json(
            f"https://{settings['_HOST']}/compatible-mode/v1/chat/completions",
            {"model": model, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]},
            settings["HOST_REALTIME_API_KEY"],
        )
        return {"answer": data["choices"][0]["message"]["content"], "model": model}
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}"}
    except Exception as exc:  # noqa: BLE001 - prototype: report as-is
        return {"error": f"{type(exc).__name__}: {exc}"}


def quiet_pcm(seconds: float) -> str:
    """Near-silent 16 kHz PCM noise, base64. Used only to fill the history-audio budget."""
    n = int(16000 * seconds)
    return base64.b64encode(struct.pack(f"<{n}h", *(random.randint(-40, 40) for _ in range(n)))).decode()


SKIP_LOG = {
    "response.audio.delta",
    "response.audio_transcript.delta",
    "response.text.delta",
    "response.function_call_arguments.delta",
    "conversation.item.input_audio_transcription.delta",
    "conversation.item.ambient_audio_transcription.delta",
    "input_audio_buffer.append",
    "relay.sample_audio",
}


class Relay:
    def __init__(self, browser, settings: dict[str, str], log_dir: Path) -> None:
        self.browser = browser
        self.settings = settings
        self.log_dir = log_dir
        self.t0 = time.monotonic()
        self.upstream = None
        self.cfg: dict = {}
        self.idle = asyncio.Event()
        self.idle.set()
        self.done_count = 0
        self.speech_count = 0
        self.tool_tasks: dict[str, list[asyncio.Task]] = {}
        self.counts = {"append": 0, "audio_delta": 0}
        self.log_fh = None

    def ms(self) -> int:
        return int((time.monotonic() - self.t0) * 1000)

    def log(self, direction: str, event: dict) -> None:
        if not self.log_fh or event.get("type") in SKIP_LOG:
            return
        if event.get("type") == "conversation.item.create":
            event = json.loads(json.dumps(event))
            for part in event.get("item", {}).get("content", []) or []:
                if part.get("type") == "input_audio":
                    part["audio"] = f"<{len(part.get('audio', ''))} chars>"
        self.log_fh.write(json.dumps({"ms": self.ms(), "dir": direction, **event}, ensure_ascii=False) + "\n")
        self.log_fh.flush()

    async def to_browser(self, obj: dict) -> None:
        self.log("relay", obj)
        try:
            await self.browser.send(json.dumps(obj, ensure_ascii=False))
        except ConnectionClosed:
            pass

    async def send_up(self, obj: dict) -> None:
        self.log("down", obj)
        await self.upstream.send(json.dumps(obj, ensure_ascii=False))

    def build_session(self) -> dict:
        cfg = self.cfg
        tools = []
        if cfg.get("tools", True):
            tools.append(TOOL_LOOKUP)
        if cfg.get("delegate"):
            tools.append(TOOL_REFEREE)
        session = {
            "modalities": ["text", "audio"],
            "voice": cfg.get("voice", "longanqian_v3.1"),
            "instructions": cfg.get("instructions", ""),
            "input_audio_format": "pcm",
            "output_audio_format": "pcm",
            "input_audio_transcription": {"language": "zh"},
            "speech_rate": float(cfg.get("speech_rate", 1.0)),
            "enable_speech_emotion": bool(cfg.get("emotion", True)),
            "max_history_turns": int(cfg.get("max_history_turns", 20)),
        }
        if tools:
            session["tools"] = tools
        mode = cfg.get("mode", "smart_turn_v2")
        if mode == "ptt":
            session["turn_detection"] = None
        else:
            td = {"type": mode, "threshold": float(cfg.get("threshold", 0.5))}
            if mode == "server_vad":
                td["silence_duration_ms"] = int(cfg.get("silence_ms", 800))
            session["turn_detection"] = td
        return session

    async def run(self) -> None:
        first = json.loads(await self.browser.recv())
        if first.get("type") != "relay.start":
            return
        self.cfg = first.get("config", {})
        model = MODELS.get(self.cfg.get("model", "flash"), MODELS["flash"])
        stamp = time.strftime("%Y%m%d-%H%M%S")
        log_path = self.log_dir / f"{stamp}-{self.cfg.get('model', 'flash')}-{self.cfg.get('voice', '')}.jsonl"
        self.log_fh = log_path.open("w", encoding="utf-8")
        self.log("relay", {"type": "relay.config", "config": self.cfg, "model": model})
        print(f"[{stamp}] 連線 {model} voice={self.cfg.get('voice')} mode={self.cfg.get('mode')}  紀錄：{log_path}")

        url = f"wss://{self.settings['_HOST']}/api-ws/v1/realtime?model={model}"
        headers = {"Authorization": f"Bearer {self.settings['HOST_REALTIME_API_KEY']}"}
        t_connect = time.monotonic()
        try:
            self.upstream = await connect(url, additional_headers=headers, max_size=None, open_timeout=15)
        except InvalidStatus as exc:
            body = exc.response.body.decode("utf-8", "replace")[:300] if exc.response.body else ""
            await self.to_browser({"type": "relay.error", "message": f"握手失敗 HTTP {exc.response.status_code} {body}"})
            return
        except Exception as exc:  # noqa: BLE001
            await self.to_browser({"type": "relay.error", "message": f"{type(exc).__name__}: {exc}"})
            return

        await self.send_up({"type": "session.update", "session": self.build_session()})
        await self.to_browser({
            "type": "relay.ready",
            "model": model,
            "log": str(log_path),
            "connect_ms": int((time.monotonic() - t_connect) * 1000),
            "referee": self.settings.get("LLM_MODEL", "") if self.cfg.get("referee_backend", "azure") == "azure"
            else self.cfg.get("referee_qwen_model", ""),
        })

        up = asyncio.create_task(self.pump_upstream())
        down = asyncio.create_task(self.pump_browser())
        done, pending = await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        closed_by = "upstream" if up in done else "browser"
        info = {
            "type": "relay.closed",
            "by": closed_by,
            "seconds": round(time.monotonic() - self.t0, 1),
            "code": self.upstream.close_code,
            "reason": self.upstream.close_reason,
            "counts": self.counts,
        }
        await self.upstream.close()
        await self.to_browser(info)
        print(f"  結束：{info}")
        self.log_fh.close()

    async def pump_upstream(self) -> None:
        try:
            async for raw in self.upstream:
                ev = json.loads(raw)
                kind = ev.get("type", "")
                if kind == "response.created":
                    self.idle.clear()
                elif kind == "response.done":
                    self.idle.set()
                    self.done_count += 1
                    rid = ev.get("response", {}).get("id", "")
                    tasks = self.tool_tasks.pop(rid, None)
                    if tasks:
                        asyncio.create_task(self.finish_tools(rid, tasks))
                elif kind == "response.function_call_arguments.done":
                    rid = ev.get("response_id", "")
                    self.tool_tasks.setdefault(rid, []).append(asyncio.create_task(self.run_tool(ev)))
                elif kind == "input_audio_buffer.speech_started":
                    self.speech_count += 1
                elif kind == "response.audio.delta":
                    self.counts["audio_delta"] += 1
                self.log("up", ev)
                await self.browser.send(raw)
        except ConnectionClosed:
            pass

    async def pump_browser(self) -> None:
        try:
            async for raw in self.browser:
                msg = json.loads(raw)
                kind = msg.get("type", "")
                if kind.startswith("relay."):
                    await self.handle_command(msg)
                    continue
                if kind == "input_audio_buffer.append":
                    self.counts["append"] += 1
                elif kind == "input_audio_buffer.commit":
                    self.speech_count += 1
                self.log("down", msg)
                await self.upstream.send(raw)
        except ConnectionClosed:
            pass

    async def handle_command(self, msg: dict) -> None:
        kind = msg["type"]
        if kind in ("relay.mark", "relay.metrics"):
            self.log("ui", msg)
        elif kind == "relay.set":
            self.log("ui", msg)
            if "tool_delay" in msg:
                self.cfg["tool_delay"] = float(msg["tool_delay"])
        elif kind == "relay.fill_audio":
            asyncio.create_task(self.fill_audio(float(msg.get("seconds", 30)), int(msg.get("count", 10))))
        elif kind == "relay.fill_text":
            asyncio.create_task(self.fill_text(int(msg.get("count", 10))))
        elif kind == "relay.voice_sample":
            self.log("ui", msg)
            asyncio.create_task(self.voice_sample(str(msg.get("voice", "")), str(msg.get("text", "")),
                                                  str(msg.get("sample_id", ""))))

    async def voice_sample(self, voice: str, text: str, sample_id: str) -> None:
        """Audition a voice on its own short connection.

        Voice can only be set before a connection processes audio: a per-response `voice`
        override is ignored and a second session.update is rejected (tested 2026-11-19).
        """
        model = MODELS.get(self.cfg.get("model", "flash"), MODELS["flash"])
        url = f"wss://{self.settings['_HOST']}/api-ws/v1/realtime?model={model}"
        headers = {"Authorization": f"Bearer {self.settings['HOST_REALTIME_API_KEY']}"}
        result = {"type": "relay.sample_done", "sample_id": sample_id, "voice": voice,
                  "voice_reported": "", "transcript": "", "first_audio_ms": None, "error": "", "usage": None}
        try:
            async with connect(url, additional_headers=headers, max_size=None, open_timeout=15) as ws:
                await ws.send(json.dumps({"type": "session.update", "session": {
                    "modalities": ["text", "audio"], "voice": voice, "turn_detection": None,
                    "instructions": self.cfg.get("instructions", ""),
                    "speech_rate": float(self.cfg.get("speech_rate", 1.0)),
                    "enable_speech_emotion": bool(self.cfg.get("emotion", True)),
                }}, ensure_ascii=False))
                await ws.send(json.dumps({"type": "conversation.item.create", "item": {
                    "type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}},
                    ensure_ascii=False))
                sent = time.monotonic()
                await ws.send(json.dumps({"type": "response.create"}))
                async for raw in ws:
                    ev = json.loads(raw)
                    kind = ev.get("type", "")
                    if kind == "response.created":
                        result["voice_reported"] = ev.get("response", {}).get("voice", "")
                    elif kind == "response.audio.delta":
                        if result["first_audio_ms"] is None:
                            result["first_audio_ms"] = int((time.monotonic() - sent) * 1000)
                        await self.to_browser({"type": "relay.sample_audio", "sample_id": sample_id,
                                               "delta": ev.get("delta", "")})
                    elif kind == "response.audio_transcript.done":
                        result["transcript"] = ev.get("transcript", "")
                    elif kind == "error":
                        result["error"] = f"{ev.get('error', {}).get('code')}: {ev.get('error', {}).get('message')}"
                        break
                    elif kind == "response.done":
                        result["usage"] = ev.get("response", {}).get("usage")
                        break
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"{type(exc).__name__}: {exc}"
        await self.to_browser(result)

    async def run_tool(self, ev: dict) -> tuple[str, str]:
        name = ev.get("name", "")
        call_id = ev.get("call_id", "")
        try:
            args = json.loads(ev.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {"_raw": ev.get("arguments")}
        speech_mark = self.speech_count
        delay = float(self.cfg.get("tool_delay", 0))
        await self.to_browser({"type": "relay.tool_started", "call_id": call_id, "name": name,
                               "args": args, "delay": delay})
        started = time.monotonic()
        if name == "lookup_rule":
            await asyncio.sleep(delay)
            result = lookup_rules(str(args.get("topic", "")), str(args.get("question", "")))
        elif name == "ask_referee":
            result = await asyncio.to_thread(
                ask_referee_sync, self.settings, self.cfg,
                str(args.get("question", "")), str(args.get("situation", "")),
            )
        else:
            result = {"error": f"沒有這個工具：{name}"}
        output = json.dumps(result, ensure_ascii=False)
        await self.to_browser({
            "type": "relay.tool_result", "call_id": call_id, "name": name,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "stale": self.speech_count != speech_mark, "output": output[:600],
        })
        return call_id, output

    async def finish_tools(self, rid: str, tasks: list[asyncio.Task]) -> None:
        results = await asyncio.gather(*tasks)
        waited_for_turn = not self.idle.is_set()
        await self.idle.wait()  # a new player turn may have started a response meanwhile
        for call_id, output in results:
            await self.send_up({"type": "conversation.item.create",
                                "item": {"type": "function_call_output", "call_id": call_id, "output": output}})
        await self.send_up({"type": "response.create"})
        await self.to_browser({"type": "relay.tool_output_sent", "response_id": rid,
                               "call_ids": [c for c, _ in results], "waited_for_turn": waited_for_turn})

    async def fill_audio(self, seconds: float, count: int) -> None:
        for i in range(count):
            await self.send_up({"type": "conversation.item.create", "item": {
                "type": "message", "role": "user",
                "content": [{"type": "input_audio", "audio": quiet_pcm(seconds)}],
            }})
            await self.to_browser({"type": "relay.fill_progress", "what": "audio", "done": i + 1,
                                   "count": count, "seconds": seconds})
            await asyncio.sleep(0.2)

    async def fill_text(self, count: int) -> None:
        for i in range(count):
            await self.idle.wait()
            before = self.done_count
            await self.send_up({"type": "conversation.item.create", "item": {
                "type": "message", "role": "user",
                "content": [{"type": "input_text", "text": f"（填充對話第 {i + 1} 句）今天店裡人多嗎？五個字以內回答。"}],
            }})
            await self.send_up({"type": "response.create", "response": {"modalities": ["text"]}})
            for _ in range(300):
                if self.done_count > before:
                    break
                await asyncio.sleep(0.1)
            await self.to_browser({"type": "relay.fill_progress", "what": "text", "done": i + 1, "count": count})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--log-dir", type=Path, help="紀錄資料夾（預設在系統暫存區，不進 repo）")
    args = parser.parse_args()
    settings = load_settings()
    log_dir = args.log_dir or Path(tempfile.gettempdir()) / "host-listen-test"
    log_dir.mkdir(parents=True, exist_ok=True)

    def process_request(connection, request):
        path = request.path.split("?")[0]
        if path == "/ws":
            return None
        if path in ("/", "/index.html"):
            body = (HERE / "index.html").read_bytes()  # re-read so edits show on reload
            return Response(200, "OK", Headers([("Content-Type", "text/html; charset=utf-8"),
                                                ("Content-Length", str(len(body))),
                                                ("Cache-Control", "no-store")]), body)
        return Response(404, "Not Found", Headers([("Content-Length", "0")]), b"")

    async def handler(browser):
        await Relay(browser, settings, log_dir).run()

    async def serve_forever():
        async with serve(handler, "127.0.0.1", args.port, process_request=process_request, max_size=2**22):
            print(f"開 Chrome：http://localhost:{args.port}")
            print(f"阿里雲主機已設定；裁判：{'Azure ' + settings['LLM_MODEL'] if settings.get('LLM_ENDPOINT') else '沒有 Azure 設定'}")
            print(f"紀錄（不含聲音）：{log_dir}\nCtrl+C 結束")
            await asyncio.get_running_loop().create_future()

    try:
        asyncio.run(serve_forever())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
