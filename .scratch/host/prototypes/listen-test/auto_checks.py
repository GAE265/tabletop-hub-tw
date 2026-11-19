"""Ticket 07 checks that need no human voice. PROTOTYPE, throwaway.

  idle      how long a connection survives with nobody talking (3 variants in parallel)
  memory    does the host still remember a planted fact after 300+ s of history audio / 20+ turns
  delegate  same rule questions: model answers alone vs hands off to the referee (text model)

Run from the worktree root:
  uv run --no-project --with 'websockets>=14' python .scratch/host/prototypes/listen-test/auto_checks.py idle
Audio for `delegate` is saved to the system temp folder so a human can listen; never into the repo.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
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
OUT = Path(tempfile.gettempdir()) / "host-listen-test" / "auto"
OUT.mkdir(parents=True, exist_ok=True)

BASE_INSTR = (
    "你是桌遊店的 AI 主持人，今晚主持《血與刃的白薔薇》（5 到 10 人的陣營推理遊戲）。"
    "說話：熱情、有戲劇感；每次一到三句話，用台灣常用的說法。"
    "規則問題：先說一句很短的等待語（例如「我翻一下規則」），再呼叫 lookup_rule；"
    "只根據查到的內容回答，查不到就說規則摘要沒寫，不要自己編。"
)
DELEGATE_INSTR = (
    "需要多步推理的規則題（牽涉人數、順序推算、多個效果、勝負判定），先說等待語，再呼叫 ask_referee，"
    "把問題和玩家說過的局面完整交給裁判；拿到答案後用你的口吻唸出來，不要改結論。"
)
QUESTIONS = [
    ("我們七個人玩，血刃陣營總共有幾個人？", "3 人"),
    ("七個人玩，座位 3 放了水晶，數字是 6。這個回合誰先決定出牌、誰最後？", "座位 4 先，座位 3 最後"),
    ("這個回合翻出雙刃、信者、白薔薇各一張，結果怎樣？", "血刃陣營立刻獲勝"),
    ("獻祭區已經有三張花苞，可是白薔薇還沒打出來，白薔薇陣營贏了嗎？", "還沒贏，遊戲繼續"),
    ("死亡區已經有一張信者，這個回合翻出暗刃、司教、幽魂，會怎樣？", "司教進死亡區，死亡區 2 張，血刃獲勝"),
    ("白水晶可以拿來跟別人換金幣嗎？", "規則摘要沒寫"),
]


def url(model_key: str) -> str:
    return f"wss://{SETTINGS['_HOST']}/api-ws/v1/realtime?model={S.MODELS[model_key]}"


async def wait_for(ws, *kinds: str, timeout: float = 60) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        ev = json.loads(await asyncio.wait_for(ws.recv(), max(0.1, deadline - time.monotonic())))
        if ev.get("type") in kinds or ev.get("type") == "error":
            return ev


# ------------------------------------------------------------------ idle
async def idle_one(name: str, ping: bool, stream_silence: bool, cap_s: int) -> str:
    t0 = time.monotonic()
    ws = await connect(url("flash"), additional_headers=HEADERS, max_size=None,
                       ping_interval=20 if ping else None)
    await ws.send(json.dumps({"type": "session.update", "session": {
        "voice": "xunanchuan_v3.1", "turn_detection": {"type": "smart_turn_v2"}}}))
    events: dict[str, int] = {}

    async def feeder():
        chunk = base64.b64encode(bytes(640)).decode()  # 20 ms of digital silence
        while True:
            await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": chunk}))
            await asyncio.sleep(0.02)

    feed = asyncio.create_task(feeder()) if stream_silence else None
    try:
        async with asyncio.timeout(cap_s):
            async for raw in ws:
                kind = json.loads(raw).get("type", "")
                events[kind] = events.get(kind, 0) + 1
        result = f"斷線 code={ws.close_code} reason={ws.close_reason!r}"
    except TimeoutError:
        result = f"撐到上限 {cap_s} 秒還沒斷"
    except ConnectionClosed as exc:
        result = f"斷線 {exc}"
    finally:
        if feed:
            feed.cancel()
        await ws.close()
    line = f"[{name}] {time.monotonic() - t0:.0f} 秒：{result}；收到事件 {events}"
    print(line, flush=True)
    return line


async def cmd_idle(cap_s: int) -> None:
    print(f"開始 {time.strftime('%H:%M:%S')}，上限 {cap_s} 秒", flush=True)
    await asyncio.gather(
        idle_one("A 不送聲音、有 ping", ping=True, stream_silence=False, cap_s=cap_s),
        idle_one("B 不送聲音、沒有 ping", ping=False, stream_silence=False, cap_s=cap_s),
        idle_one("C 一直送靜音、有 ping", ping=True, stream_silence=True, cap_s=cap_s),
    )


# ------------------------------------------------------------------ memory
async def ask_text(ws, text: str) -> tuple[str, dict]:
    await ws.send(json.dumps({"type": "conversation.item.create", "item": {
        "type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}},
        ensure_ascii=False))
    await ws.send(json.dumps({"type": "response.create", "response": {"modalities": ["text"]}}))
    answer = ""
    while True:
        ev = json.loads(await asyncio.wait_for(ws.recv(), 60))
        if ev.get("type") in ("response.text.done", "response.audio_transcript.done"):
            answer = ev.get("text") or ev.get("transcript") or ""
        elif ev.get("type") == "error":
            return f"ERROR {ev.get('error')}", {}
        elif ev.get("type") == "response.done":
            return answer, ev.get("response", {}).get("usage") or {}


async def memory_run(label: str, max_turns: int, audio_items: int, text_turns: int) -> None:
    async with connect(url("flash"), additional_headers=HEADERS, max_size=None) as ws:
        await ws.send(json.dumps({"type": "session.update", "session": {
            "modalities": ["text", "audio"], "turn_detection": None, "max_history_turns": max_turns,
            "instructions": "你是桌遊主持人，回答簡短。"}}))
        await wait_for(ws, "session.updated")
        plant, _ = await ask_text(ws, "請記住：今晚的暗號是「藍色鳳梨」，三號座位的玩家叫阿哲。只回答「記住了」。")
        # One big input_audio item gets the connection closed (1009 message too big; the server said
        # 1 MiB once and 256 KiB once), so stream 20 s per item through the buffer and commit it.
        for _ in range(audio_items):
            pcm = base64.b64decode(S.quiet_pcm(20))
            for i in range(0, len(pcm), 3200):  # 100 ms per append
                await ws.send(json.dumps({"type": "input_audio_buffer.append",
                                          "audio": base64.b64encode(pcm[i:i + 3200]).decode()}))
                await asyncio.sleep(0.002)
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            ev = await wait_for(ws, "input_audio_buffer.committed")
            if ev.get("type") == "error":
                print(f"  塞音訊失敗：{ev.get('error')}", flush=True)
                break
        for i in range(text_turns):
            await ask_text(ws, f"（閒聊第 {i + 1} 句）今天店裡人多嗎？五個字以內。")
        answer, usage = await ask_text(ws, "剛剛請你記住的暗號是什麼？三號座位的玩家叫什麼？")
        ok = "鳳梨" in answer and "阿哲" in answer
        print(f"[{label}] {'記得' if ok else '不記得'}｜植入回覆：{plant}｜最後回答：{answer}｜最後一輪 usage：{usage}",
              flush=True)


async def cmd_memory() -> None:
    await memory_run("保留 50 輪、塞 340 秒安靜語音（17 段 × 20 秒）", 50, 17, 0)
    await memory_run("保留 50 輪、塞 600 秒安靜語音（30 段 × 20 秒）", 50, 30, 0)
    await memory_run("預設 20 輪、塞 22 輪文字對話", 20, 0, 22)
    await memory_run("保留 50 輪、塞 22 輪文字對話", 50, 0, 22)


# ------------------------------------------------------------------ delegate
async def delegate_one(model_key: str, delegate: bool, idx: int) -> dict:
    question, expected = QUESTIONS[idx]
    cfg = {"referee_backend": "azure"}
    tools = [S.TOOL_LOOKUP] + ([S.TOOL_REFEREE] if delegate else [])
    row = {"model": model_key, "delegate": delegate, "q": idx + 1, "expected": expected,
           "first_audio_ms": None, "answer_audio_ms": None, "tools": [], "spoken": []}
    audio = bytearray()
    async with connect(url(model_key), additional_headers=HEADERS, max_size=None) as ws:
        await ws.send(json.dumps({"type": "session.update", "session": {
            "modalities": ["text", "audio"], "voice": "xunanchuan_v3.1", "turn_detection": None,
            "instructions": BASE_INSTR + (DELEGATE_INSTR if delegate else ""), "tools": tools}},
            ensure_ascii=False))
        await wait_for(ws, "session.updated")
        await ws.send(json.dumps({"type": "conversation.item.create", "item": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": question}]}},
            ensure_ascii=False))
        sent = time.monotonic()
        await ws.send(json.dumps({"type": "response.create"}))
        answering = False
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), 90))
            kind = ev.get("type", "")
            ms = int((time.monotonic() - sent) * 1000)
            if kind == "response.audio.delta":
                audio.extend(base64.b64decode(ev.get("delta", "")))
                if answering and row["answer_audio_ms"] is None:
                    row["answer_audio_ms"] = ms
                elif not answering and row["first_audio_ms"] is None:
                    row["first_audio_ms"] = ms
            elif kind == "response.audio_transcript.done":
                row["spoken"].append(ev.get("transcript", "").strip())
            elif kind == "response.function_call_arguments.done":
                args = json.loads(ev.get("arguments") or "{}")
                t = time.monotonic()
                if ev.get("name") == "ask_referee":
                    out = await asyncio.to_thread(S.ask_referee_sync, SETTINGS, cfg,
                                                  str(args.get("question", "")), str(args.get("situation", "")))
                else:
                    out = S.lookup_rules(str(args.get("topic", "")), str(args.get("question", "")))
                row["tools"].append({"name": ev.get("name"), "args": args,
                                     "tool_ms": int((time.monotonic() - t) * 1000)})
                row.setdefault("_pending", []).append((ev.get("call_id"), json.dumps(out, ensure_ascii=False)))
            elif kind == "response.done":
                pending = row.pop("_pending", [])
                if not pending:
                    break
                for call_id, output in pending:
                    await ws.send(json.dumps({"type": "conversation.item.create", "item": {
                        "type": "function_call_output", "call_id": call_id, "output": output}}, ensure_ascii=False))
                await ws.send(json.dumps({"type": "response.create"}))
                answering = True
            elif kind == "error":
                row["spoken"].append(f"ERROR {ev.get('error')}")
                break
    path = OUT / f"q{idx + 1}-{model_key}-{'delegate' if delegate else 'self'}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(bytes(audio))
    row["wav"] = str(path)
    return row


async def cmd_delegate(models: list[str]) -> None:
    rows = []
    for model_key in models:
        for delegate in (False, True):
            for idx in range(len(QUESTIONS)):
                row = await delegate_one(model_key, delegate, idx)
                rows.append(row)
                tools = "、".join(f"{t['name']}({t['tool_ms']}ms)" for t in row["tools"]) or "沒用工具"
                print(f"[{model_key} {'轉交' if delegate else '自己'} Q{row['q']}] 首音 {row['first_audio_ms']} ms，"
                      f"答案首音 {row['answer_audio_ms']} ms，{tools}｜說：{' / '.join(row['spoken'])}｜應答：{row['expected']}",
                      flush=True)
    (OUT / "delegate.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"聲音檔與結果：{OUT}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_idle = sub.add_parser("idle")
    p_idle.add_argument("--cap", type=int, default=5400)
    sub.add_parser("memory")
    p_del = sub.add_parser("delegate")
    p_del.add_argument("--models", nargs="+", default=["flash", "plus"], choices=list(S.MODELS))
    args = parser.parse_args()
    if args.cmd == "idle":
        asyncio.run(cmd_idle(args.cap))
    elif args.cmd == "memory":
        asyncio.run(cmd_memory())
    else:
        asyncio.run(cmd_delegate(args.models))
    return 0


if __name__ == "__main__":
    sys.exit(main())
