"""Ticket 11 checks: how smart_turn_v2 treats spoken commands. PROTOTYPE, throwaway.

No human voice and no speaker: phrases are synthesized with macOS `say` (zh_TW voice Meijia),
converted to 16 kHz mono PCM and fed straight into the WebSocket in 100 ms chunks, with
near-silent noise before and after (as if the table microphone were always open).

  probe  does smart_turn_v2 accept turn_detection.silence_duration_ms (what session.updated reports)
  a      a command spoken while the host is talking, for several silence_duration_ms values,
         plus a normal rule question with and without a 1.2 s pause in the middle
  b      a command spoken while the host is silent: counted as a turn? right tool called?
  c      table chatter that happens to contain a command word: any tool called by mistake?
  d      plain chatter while the host is talking: does the server cancel the host's reply?
  e      plain chatter and real questions while the host is silent: does the host speak?
  --quiet-tool (before the subcommand) adds a not_for_me tool the model should call instead of
         answering chatter; results go to a quiet subfolder

Run from the worktree root:
  uv run --no-project --with 'websockets>=14' python .scratch/host/prototypes/listen-test/command_checks.py probe
  ... command_checks.py a
  ... command_checks.py b --silence 800 --reps 3
  ... command_checks.py c --silence 800
  ... command_checks.py --threshold 0.8 c      (results go to a thr-0.8 subfolder)
Synthesized audio, event logs (no audio) and results go to the system temp folder, never into the repo.
"Host is talking" here means the server is still sending audio; the server generates faster than
playback, so each row also reports how much unplayed audio a real client would still hold.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import random
import re
import struct
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as S  # noqa: E402
from websockets.asyncio.client import connect  # noqa: E402
from websockets.exceptions import ConnectionClosed  # noqa: E402

SETTINGS = S.load_settings()
HEADERS = {"Authorization": f"Bearer {SETTINGS['HOST_REALTIME_API_KEY']}"}
OUT = Path(tempfile.gettempdir()) / "host-listen-test" / "auto" / "cmd"
TTS = OUT / "tts"
THRESHOLD = 0.5  # turn_detection.threshold; --threshold overrides it
QUIET = False  # --quiet-tool: give the model a "not for me" tool to call instead of answering chatter
TTS.mkdir(parents=True, exist_ok=True)
URL = f"wss://{SETTINGS['_HOST']}/api-ws/v1/realtime?model={S.MODELS['flash']}"
CHUNK = 3200  # 100 ms of 16 kHz 16-bit mono

INSTR = (
    "你是桌遊店的 AI 主持人，今晚主持《血與刃的白薔薇》（5 到 10 人的陣營推理遊戲）。"
    "說話：熱情、有戲劇感，用台灣常用的說法。平常回答一到三句；玩家要你講長一點時就照做。"
    "規則問題：先說一句很短的等待語（例如「我翻一下規則」），再呼叫 lookup_rule；"
    "只根據查到的內容回答，查不到就說規則摘要沒寫，不要自己編。"
    "語音指令：玩家說「下一步」就呼叫 next_phase；說「上一步」就呼叫 previous_phase；"
    "說「等一下」或「暫停」就呼叫 pause_hosting；說「繼續」就呼叫 resume_hosting；"
    "說「結束了」，或說某一方贏了（例如「白薔薇贏了」「血刃贏了」），就呼叫 end_hosting，有說哪一方就帶 winner。"
    "只有玩家是在對你下指令時才呼叫；玩家之間聊天剛好講到這些字（例如「等一下再出牌」）不要呼叫。"
    "呼叫之後只回一句很短的話。"
)
QUIET_INSTR = (
    "桌上的玩家會彼此聊天。聽到的話如果不是在問你規則、也不是對你下指令，"
    "就只呼叫 not_for_me，不要說任何話，不要接話，也不要評論。"
)
STATE_RUNNING = "目前狀況：7 人局，第 2 回合，階段 2（決定出牌），主持進行中。"
STATE_PAUSED = "目前狀況：7 人局，第 2 回合，階段 2（決定出牌），主持暫停中。"
LONG_PROMPT = (
    "請用至少三百個字，慢慢地、完整地講一段《血與刃的白薔薇》的背景故事，自己編就好。"
    "不要查規則，不要呼叫任何工具，中間不要停下來問問題。"
)


def _tool(name: str, desc: str, props: dict | None = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": []}}}


TOOLS = [
    S.TOOL_LOOKUP,
    _tool("next_phase", "玩家說「下一步」：進到下一個階段。"),
    _tool("previous_phase", "玩家說「上一步」：退回上一個階段。"),
    _tool("pause_hosting", "玩家說「等一下」或「暫停」：主持暫停。"),
    _tool("resume_hosting", "玩家說「繼續」：從暫停恢復主持。"),
    _tool("end_hosting", "玩家說「結束了」或說某一方贏了：結束這場主持。", {
        "winner": {"type": "string", "enum": ["白薔薇", "血刃"], "description": "玩家說哪一方贏；沒說就不帶"}}),
]
QUIET_TOOL = _tool("not_for_me", "玩家不是在對主持人說話（玩家之間聊天、附和聲、自言自語）時呼叫。呼叫後不要說任何話。")
COMMAND_TOOLS = {"next_phase", "previous_phase", "pause_hosting", "resume_hosting", "end_hosting"}
EXPECT = {
    "下一步": ("next_phase", None), "上一步": ("previous_phase", None),
    "暫停": ("pause_hosting", None), "等一下": ("pause_hosting", None),
    "繼續": ("resume_hosting", None), "結束了": ("end_hosting", ""),
    "白薔薇贏了": ("end_hosting", "白薔薇"), "血刃贏了": ("end_hosting", "血刃"),
}
CHATTER = ["等一下再出牌啦", "你下一步要出什麼", "我覺得快結束了", "上一步他明明沒出牌", "白薔薇贏了嗎",
           "暫停一下，我去上廁所"]
BACKCHANNEL = ["嗯嗯", "哈哈哈，好啦好啦", "我覺得三號一定是血刃"]  # d: chatter while the host is talking
QUESTION = "我們七個人玩，血刃陣營總共有幾個人？"
PLAIN_CHATTER = ["我覺得三號一定是血刃", "哈哈哈，好啦好啦", "欸你剛剛為什麼不出牌", "我去拿個飲料"]
REAL_QUESTIONS = [QUESTION, "金幣可以交給自己嗎", "主持人，現在是第幾回合"]
QUESTION_PARTS = ("我們七個人玩，", "血刃陣營總共有幾個人？")


def noise(n_bytes: int) -> bytes:
    n = n_bytes // 2
    return struct.pack(f"<{n}h", *(random.randint(-40, 40) for _ in range(n)))


def tts(text: str) -> bytes:
    """Synthesize with macOS say, return trimmed 16 kHz mono 16-bit PCM."""
    path = TTS / (re.sub(r"\W", "", text)[:24] + ".wav")
    if not path.exists():
        subprocess.run(["say", "-v", "Meijia", "-o", str(path), "--file-format=WAVE",
                        "--data-format=LEI16@16000", text], check=True)
    with wave.open(str(path), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2), "unexpected wav format"
        pcm = w.readframes(w.getnframes())
    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    loud = [i for i, v in enumerate(samples) if abs(v) > 300]
    if not loud:
        return pcm
    lo, hi = max(0, loud[0] - 800), min(len(samples), loud[-1] + 800)  # keep 50 ms each side
    return pcm[lo * 2:hi * 2]


def utterance(spec: dict) -> bytes:
    if spec.get("parts"):
        a, b = (tts(p) for p in spec["parts"])
        return a + noise(int(16000 * 2 * spec.get("gap_s", 1.2))) + b
    return tts(spec["say"])


def turn_detection(silence: int | None) -> dict:
    td = {"type": "smart_turn_v2", "threshold": THRESHOLD}
    if silence is not None:
        td["silence_duration_ms"] = silence
    return td


class Trial:
    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.t0 = time.monotonic()
        self.queue = b""
        self.utt_start: int | None = None
        self.utt_end: int | None = None
        self.td_reported = None
        self.segs: dict[str, dict] = {}
        self.trs: dict[str, dict] = {}
        self.resps: dict[str, dict] = {}
        self.pending: dict[str, list] = {}
        self.errors: list[str] = []
        self.in_progress: set[str] = set()
        self.last_event_ms = 0
        self.log = (OUT / f"{spec['label']}.jsonl").open("w", encoding="utf-8")

    def ms(self) -> int:
        return int((time.monotonic() - self.t0) * 1000)

    async def feeder(self, ws) -> None:
        next_t = time.monotonic()
        while True:
            if self.queue:
                chunk, self.queue = self.queue[:CHUNK], self.queue[CHUNK:]
                if self.utt_start is None:
                    self.utt_start = self.ms()
                if not self.queue:
                    chunk += noise(CHUNK - len(chunk))
                    self.utt_end = self.ms()
            else:
                chunk = noise(CHUNK)
            await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": base64.b64encode(chunk).decode()}))
            next_t += 0.1
            await asyncio.sleep(max(0.0, next_t - time.monotonic()))

    async def receiver(self, ws) -> None:
        async for raw in ws:
            ev = json.loads(raw)
            kind, ms = ev.get("type", ""), self.ms()
            rid = ev.get("response_id") or (ev.get("response") or {}).get("id") or ""
            if kind == "response.audio.delta":
                r = self.resps.setdefault(rid, {"calls": []})
                r.setdefault("first_audio_ms", ms)
                r["last_audio_ms"] = ms
                r["audio_s"] = r.get("audio_s", 0.0) + len(ev.get("delta", "")) * 3 / 4 / 48000
                r.setdefault("audio_marks", []).append((ms, round(r["audio_s"], 2)))
                continue
            self.log.write(json.dumps({"ms": ms, **ev}, ensure_ascii=False) + "\n")
            self.last_event_ms = ms
            iid = ev.get("item_id", "")
            if kind == "session.updated":
                self.td_reported = (ev.get("session") or {}).get("turn_detection")
            elif kind == "input_audio_buffer.speech_started":
                self.segs[iid] = {"started_ms": ms}
            elif kind == "input_audio_buffer.speech_stopped":
                self.segs.setdefault(iid, {}).update(stopped_ms=ms, reason=ev.get("reason") or "valid")
            elif kind.endswith("audio_transcription.delta"):
                t = self.trs.setdefault(iid, {"kind": "ambient" if "ambient" in kind else "input", "partial": ""})
                # `text` is the confirmed prefix, `stash` the tentative tail (seen 2026-11-20).
                t.setdefault("first_delta_ms", ms)
                t["partial"] = str(ev.get("text") or "") + str(ev.get("stash") or "")
                t.setdefault("deltas", []).append((ms, t["partial"]))
            elif kind.endswith("audio_transcription.completed"):
                t = self.trs.setdefault(iid, {"kind": "ambient" if "ambient" in kind else "input", "partial": ""})
                t.update(completed_ms=ms, text=ev.get("transcript") or "",
                         kind="ambient" if "ambient" in kind else "input")
            elif kind == "response.created":
                self.resps.setdefault(rid, {"calls": []})["created_ms"] = ms
                self.in_progress.add(rid)
            elif kind == "response.audio_transcript.done":
                self.resps.setdefault(rid, {"calls": []})["said"] = (ev.get("transcript") or "").strip()
            elif kind == "response.function_call_arguments.done":
                try:
                    args = json.loads(ev.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": ev.get("arguments")}
                name = ev.get("name", "")
                self.resps.setdefault(rid, {"calls": []})["calls"].append({"name": name, "args": args, "ms": ms})
                out = (S.lookup_rules(str(args.get("topic", "")), str(args.get("question", "")))
                       if name == "lookup_rule" else {"ok": True})
                self.pending.setdefault(rid, []).append((ev.get("call_id"), json.dumps(out, ensure_ascii=False), name))
            elif kind == "response.done":
                resp = ev.get("response") or {}
                self.resps.setdefault(rid, {"calls": []}).update(
                    done_ms=ms, status=resp.get("status"), status_details=resp.get("status_details"))
                self.in_progress.discard(rid)
                for call_id, output, name in self.pending.pop(rid, []):
                    await ws.send(json.dumps({"type": "conversation.item.create", "item": {
                        "type": "function_call_output", "call_id": call_id, "output": output}}, ensure_ascii=False))
                    if name != "not_for_me":  # staying silent is the whole point of that tool
                        await ws.send(json.dumps({"type": "response.create"}))
            elif kind == "error":
                self.errors.append(json.dumps(ev.get("error"), ensure_ascii=False))

    async def until(self, cond, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if cond():
                return True
            await asyncio.sleep(0.05)
        return cond()

    def my_segs(self) -> list[dict]:
        if self.utt_start is None:
            return []
        return [s for s in self.segs.values() if s.get("started_ms", 0) >= self.utt_start - 300]

    async def run(self) -> dict:
        spec = self.spec
        session = {
            "modalities": ["text", "audio"], "voice": "xunanchuan_v3.1",
            "instructions": INSTR + (QUIET_INSTR if QUIET else "") + spec.get("state", STATE_RUNNING),
            "input_audio_format": "pcm", "output_audio_format": "pcm",
            "input_audio_transcription": {"language": "zh"}, "enable_speech_emotion": True,
            "max_history_turns": 20, "tools": TOOLS + ([QUIET_TOOL] if QUIET else []), "turn_detection": turn_detection(spec.get("silence")),
        }
        long_rid = None
        try:
            async with connect(URL, additional_headers=HEADERS, max_size=None, open_timeout=15) as ws:
                self.t0 = time.monotonic()
                await ws.send(json.dumps({"type": "session.update", "session": session}, ensure_ascii=False))
                recv = asyncio.create_task(self.receiver(ws))
                await self.until(lambda: self.td_reported is not None or self.errors, 10)
                feed = asyncio.create_task(self.feeder(ws))
                await asyncio.sleep(1.0)
                if spec.get("host_talking"):
                    await ws.send(json.dumps({"type": "conversation.item.create", "item": {
                        "type": "message", "role": "user",
                        "content": [{"type": "input_text", "text": LONG_PROMPT}]}}, ensure_ascii=False))
                    await ws.send(json.dumps({"type": "response.create"}))
                    await self.until(lambda: any("first_audio_ms" in r for r in self.resps.values()), 20)
                    long_rid = next((k for k, r in self.resps.items() if "first_audio_ms" in r), None)
                    await asyncio.sleep(1.0)
                if spec.get("say") or spec.get("parts"):
                    self.queue = utterance(spec)
                    await self.until(lambda: self.utt_end is not None, 30)
                    # Wait for every detected segment to be judged and transcribed.
                    await self.until(lambda: bool(self.my_segs()) and all(
                        "stopped_ms" in s for s in self.my_segs()) and all(
                        "completed_ms" in self.trs.get(i, {}) for i, s in self.segs.items()
                        if s in self.my_segs()), 12)
                    await asyncio.sleep(1.5)
                    others = lambda: not [r for r in self.in_progress if r != long_rid] and not self.pending  # noqa: E731
                    await self.until(others, 15)
                    await asyncio.sleep(1.0)
                    await self.until(others, 15)
                    if long_rid:
                        await self.until(lambda: long_rid not in self.in_progress, 4)
                feed.cancel()
                recv.cancel()
        except (ConnectionClosed, OSError, TimeoutError) as exc:
            self.errors.append(f"{type(exc).__name__}: {exc}")
        self.log.close()
        return self.summary(long_rid)

    def summary(self, long_rid: str | None) -> dict:
        spec, end = self.spec, self.utt_end
        segs = sorted(self.my_segs(), key=lambda s: s["started_ms"])
        ids = [i for i, s in self.segs.items() if s in segs]
        trs = [self.trs.get(i, {}) for i in sorted(ids, key=lambda i: self.segs[i]["started_ms"])]
        calls = [c for k, r in self.resps.items() if k != long_rid for c in r["calls"]]
        replies = [r for k, r in self.resps.items() if k != long_rid and "created_ms" in r]
        rel = lambda v: None if v is None or end is None else v - end  # noqa: E731
        row = {
            "label": spec["label"], "group": spec["group"], "say": spec.get("say") or "｜".join(spec.get("parts", [])),
            "silence_sent": spec.get("silence"), "td_reported": self.td_reported,
            "segments": len(segs),
            "end_to_stopped_ms": [rel(s.get("stopped_ms")) for s in segs],
            "end_to_started_ms": [rel(s.get("started_ms")) for s in segs],
            "reason": [s.get("reason", "沒有 speech_stopped") for s in segs],
            "tr_kind": [t.get("kind") for t in trs],
            "text": [t.get("text") for t in trs],
            "end_to_text_ms": [rel(t.get("completed_ms")) for t in trs],
            "end_to_first_delta_ms": [rel(t.get("first_delta_ms")) for t in trs],
            "deltas": [[(rel(m), txt) for m, txt in t.get("deltas", [])][:8] for t in trs],
            "end_to_partial_match_ms": [rel(next((m for m, txt in t.get("deltas", [])
                                                  if norm(spec.get("say")) and norm(spec.get("say")) in norm(txt)), None))
                                        for t in trs],
            "calls": [{"name": c["name"], "args": c["args"], "end_to_call_ms": rel(c["ms"])} for c in calls],
            "replies": [{"end_to_created_ms": rel(r.get("created_ms")), "status": r.get("status"),
                         "end_to_first_audio_ms": rel(r.get("first_audio_ms")), "said": r.get("said")} for r in replies],
            "errors": self.errors,
        }
        if long_rid:
            r = self.resps[long_rid]
            first = r.get("first_audio_ms") or 0

            def unplayed(at: int | None) -> float | None:
                """Seconds of audio a real client would still have to play at time `at`."""
                if at is None:
                    return None
                got = max((s for m, s in r.get("audio_marks", []) if m <= at), default=0.0)
                return round(got - (at - first) / 1000, 1)

            stopped = segs[0].get("stopped_ms") if segs else None
            row["long"] = {
                "status": r.get("status") or "還在產生", "status_details": r.get("status_details"),
                "end_to_done_ms": rel(r.get("done_ms")), "audio_total_s": round(r.get("audio_s", 0.0), 1),
                "server_sending_at_utt_start": (r.get("done_ms") or 10**9) > (self.utt_start or 0),
                "server_sending_at_stopped": None if stopped is None else (r.get("done_ms") or 10**9) > stopped,
                "unplayed_s_at_utt_end": unplayed(end), "unplayed_s_at_stopped": unplayed(stopped),
                "end_to_last_audio_ms": rel(r.get("last_audio_ms")),
            }
        return row


# The transcription comes back in Simplified Chinese with punctuation; fold both before comparing.
S2T = str.maketrans("暂结赢继续蔷们个阵营总几觉么没厕吗对这说会为", "暫結贏繼續薔們個陣營總幾覺麼沒廁嗎對這說會為")


def norm(text: str | None) -> str:
    return re.sub(r"[\W_]", "", text or "").translate(S2T)


def show(row: dict) -> None:
    long = row.get("long")
    bits = [
        f"[{row['label']}] 「{row['say']}」",
        f"段數 {row['segments']}",
        f"說完→判定 {row['end_to_stopped_ms']} ms",
        f"reason {row['reason']}",
        f"辨識 {row['text']}（{row['tr_kind']}）說完→完整文字 {row['end_to_text_ms']} ms，"
        f"說完→片段文字已含整句 {row['end_to_partial_match_ms']} ms",
        "工具 " + ("、".join(f"{c['name']}{c['args'] or ''}@{c['end_to_call_ms']}ms" for c in row["calls"]) or "沒有"),
    ]
    if row["replies"]:
        bits.append("回話 " + " / ".join(f"{r['said']}（{r['status']}，首音 {r['end_to_first_audio_ms']} ms）"
                                        for r in row["replies"]))
    if long:
        bits.append(f"長回答 {long['status']} {long['status_details'] or ''}，說完時伺服器還在送={long['server_sending_at_stopped']}，"
                    f"判定時還沒播完的聲音 {long['unplayed_s_at_stopped']} 秒")
    if row["errors"]:
        bits.append("錯誤 " + "；".join(row["errors"]))
    print("｜".join(bits), flush=True)


async def run_all(specs: list[dict], name: str, parallel: int = 3) -> list[dict]:
    for spec in specs:  # synthesize up front, outside the timed part
        if spec.get("say") or spec.get("parts"):
            utterance(spec)
    sem = asyncio.Semaphore(parallel)

    async def one(spec: dict) -> dict:
        async with sem:
            row = await Trial(spec).run()
            show(row)
            return row

    rows = await asyncio.gather(*(one(s) for s in specs))
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"共 {sum(1 for s in specs if s.get('say') or s.get('parts'))} 句；結果：{path}", flush=True)
    return rows


def tag(silence: int | None) -> str:
    return "base" if silence is None else str(silence)


def specs_a(values: list[int | None]) -> list[dict]:
    specs = []
    for v in values:
        for i in range(3):
            specs.append({"group": "A", "label": f"a-{tag(v)}-wait{i + 1}", "say": "等一下", "silence": v,
                          "host_talking": True})
        for word, key in (("暫停", "pause"), ("下一步", "next")):
            specs.append({"group": "A", "label": f"a-{tag(v)}-{key}", "say": word, "silence": v, "host_talking": True})
        specs.append({"group": "A-q", "label": f"a-{tag(v)}-question", "say": QUESTION, "silence": v})
        specs.append({"group": "A-q", "label": f"a-{tag(v)}-question-gap", "parts": QUESTION_PARTS, "gap_s": 1.2,
                      "silence": v})
    return specs


def specs_b(silence: int | None, reps: int) -> list[dict]:
    return [{"group": "B", "label": f"b-{tag(silence)}-{i + 1}-{n}", "say": phrase, "silence": silence,
             "state": STATE_PAUSED if phrase == "繼續" else STATE_RUNNING}
            for n, phrase in enumerate(EXPECT) for i in range(reps)]


def specs_c(silence: int | None, reps: int) -> list[dict]:
    return [{"group": "C", "label": f"c-{tag(silence)}-{i + 1}-{n}", "say": phrase, "silence": silence}
            for n, phrase in enumerate(CHATTER) for i in range(reps)]


def specs_e(reps: int) -> list[dict]:
    return [{"group": "E", "label": f"e-{i + 1}-{n}", "say": phrase, "silence": None}
            for n, phrase in enumerate(PLAIN_CHATTER + REAL_QUESTIONS) for i in range(reps)]


def table_talk(rows: list[dict], phrases: list[str]) -> None:
    print("句子｜算一句｜主持人出聲｜not_for_me｜查規則｜指令工具")
    for phrase in phrases:
        mine = [r for r in rows if r["say"] == phrase]
        n = len(mine)
        valid = sum(1 for r in mine if r["reason"] and r["reason"][0] == "valid")
        spoke = sum(1 for r in mine if any(x.get("said") for x in r["replies"]))
        count = lambda names: sum(1 for r in mine if any(c["name"] in names for c in r["calls"]))  # noqa: E731
        print(f"{phrase}｜{valid}/{n}｜{spoke}/{n}｜{count({'not_for_me'})}/{n}｜{count({'lookup_rule'})}/{n}｜{count(COMMAND_TOOLS)}/{n}")


def table_b(rows: list[dict]) -> None:
    print("句子｜算一句｜辨識正確｜呼叫對的工具｜說完到工具呼叫 ms")
    for phrase, (tool, winner) in EXPECT.items():
        mine = [r for r in rows if r["say"] == phrase]
        valid = sum(1 for r in mine if r["reason"] and r["reason"][0] == "valid")
        exact = sum(1 for r in mine if r["text"] and norm(r["text"][0]) == norm(phrase))
        good = [c["end_to_call_ms"] for r in mine for c in r["calls"][:1]
                if c["name"] == tool and (winner is None or (c["args"].get("winner") or "") == winner)]
        span = f"{min(good)}–{max(good)}" if good else "—"
        print(f"{phrase}｜{valid}/{len(mine)}｜{exact}/{len(mine)}｜{len(good)}/{len(mine)}｜{span}")


def table_c(rows: list[dict]) -> None:
    for phrase in CHATTER:
        mine = [r for r in rows if r["say"] == phrase]
        wrong = [c["name"] for r in mine for c in r["calls"] if c["name"] in COMMAND_TOOLS]
        valid = sum(1 for r in mine if r["reason"] and r["reason"][0] == "valid")
        print(f"{phrase}｜算一句 {valid}/{len(mine)}｜誤呼叫 {len(wrong)} 次 {wrong or ''}")


def parse_silence(value: str) -> int | None:
    return None if value in ("base", "none") else int(value)


def main() -> int:
    global THRESHOLD, OUT, QUIET
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--quiet-tool", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe")
    p_a = sub.add_parser("a")
    p_a.add_argument("--values", nargs="+", default=["base", "500", "800", "1500"])
    sub.add_parser("d")
    sub.add_parser("e").add_argument("--reps", type=int, default=2)
    for name in ("b", "c"):
        p = sub.add_parser(name)
        p.add_argument("--silence", default="base")
        p.add_argument("--reps", type=int, default=3 if name == "b" else 2)
    args = parser.parse_args()
    THRESHOLD = args.threshold
    if THRESHOLD != 0.5:  # keep the 0.5 baseline results untouched
        OUT = OUT / f"thr-{THRESHOLD}"
        OUT.mkdir(parents=True, exist_ok=True)
    QUIET = args.quiet_tool
    if QUIET:
        OUT = OUT / "quiet"
        OUT.mkdir(parents=True, exist_ok=True)
    if args.cmd == "probe":
        specs = [{"group": "probe", "label": f"probe-{tag(v)}", "silence": v} for v in (None, 500, 800, 1500)]
        for row in asyncio.run(run_all(specs, "probe", parallel=4)):
            print(f"送出 silence_duration_ms={row['silence_sent']} → session.updated 回報 {row['td_reported']}｜錯誤 {row['errors']}")
    elif args.cmd == "a":
        asyncio.run(run_all(specs_a([parse_silence(v) for v in args.values]), "a-" + "-".join(args.values)))
    elif args.cmd == "d":
        specs = [{"group": "D", "label": f"d-base-{n}", "say": phrase, "silence": None, "host_talking": True}
                 for n, phrase in enumerate(BACKCHANNEL)]
        table_talk(asyncio.run(run_all(specs, "d-base")), BACKCHANNEL)
    elif args.cmd == "e":
        table_talk(asyncio.run(run_all(specs_e(args.reps), "e")), PLAIN_CHATTER + REAL_QUESTIONS)
    elif args.cmd == "b":
        silence = parse_silence(args.silence)
        table_b(asyncio.run(run_all(specs_b(silence, args.reps), f"b-{tag(silence)}")))
    else:
        silence = parse_silence(args.silence)
        rows = asyncio.run(run_all(specs_c(silence, args.reps), f"c-{tag(silence)}"))
        table_c(rows)
        table_talk(rows, CHATTER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
