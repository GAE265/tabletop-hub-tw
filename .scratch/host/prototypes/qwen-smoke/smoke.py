"""Ticket 06 smoke test: reach Qwen-Audio-3.1-Realtime (Singapore) and save the reply audio.

Throwaway script for the decision ticket, not project code. It sends a short text prompt
(no microphone) and saves the spoken reply as WAV outside the repo.

Settings come from the environment or the worktree's .env (names are proposals, see ticket 06):
  HOST_REALTIME_API_KEY       Model Studio API key (Singapore). Never printed.
  HOST_REALTIME_WORKSPACE_ID  the `ws-xxx` prefix of the API Host, or the whole API Host. Never printed.
  HOST_REALTIME_REGION        optional, default ap-southeast-1

Run from the worktree root:
  uv run --no-project --with 'websockets>=14' python .scratch/host/prototypes/qwen-smoke/smoke.py connect
  uv run --no-project --with 'websockets>=14' python .scratch/host/prototypes/qwen-smoke/smoke.py voices
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import websockets

REPO_ROOT = Path(__file__).resolve().parents[4]

MODELS = {
    "flash": "qwen-audio-3.1-realtime-flash",
    "plus": "qwen-audio-3.1-realtime-plus",
}
DEFAULT_VOICE = "longanqian_v3.1"

# 3.1 TTS Flash voice list, checked 2026-11-19:
# https://www.alibabacloud.com/help/zh/model-studio/qwen-audio-tts-voice-list
# For TTS the first four are Beijing + Singapore and the rest Beijing only.
# Realtime may differ; finding out is the point of `voices`.
VOICES = [
    "longanqian_v3.1",
    "longanhuan_v3.1",
    "longanlingxin_v3.1",
    "longanfengyue_v3.1",
    "xunanchuan_v3.1",
    "yuxiaoyun_v3.1",
    "qiaoxiaojiao_v3.1",
    "xiaxiaochen_v3.1",
    "anmingyuan_v3.1",
    "wenhuaiqing_v3.1",
    "anxiaolan_v3.1",
    "xieshurou_v3.1",
    "baiqinglan_v3.1",
    "xuyuyuan_v3.1",
    "anruorou_v3.1",
    "wenhuaizhi_v3.1",
    "xiaoxingzhi_v3.1",
    "guyunshu_v3.1",
    "huozhuoshi_v3.1",
    "yeqinghe_v3.1",
    "yunhuanhuan_v3.1",
    "xuxiaoqiao_v3.1",
    "baianran_v3.1",
    "xuyanchu_v3.1",
    "yezhiqing_v3.1",
    "andi_v3.1",
    "anyuqing_v3.1",
    "linxiaoling_v3.1",
    "longfeifei_v3.1",
    "longjing_v3.1",
    "longqiang_v3.1",
    "longyan_v3.1",
    "longxiaobai_v3.1",
    "longyue_v3.1",
    "longcheng_v3.1",
    "longlaotie_v3.1",
    "longshao_v3.1",
    "longshu_v3.1",
    "longze_v3.1",
    "longhao_v3.1",
    "longjin_v3.1",
    "longnan_v3.1",
    "longshuo_v3.1",
    "longtian_v3.1",
    "longxiaocheng_v3.1",
    "longke_v3.1",
    "loongbella_v3.1",
    "longanyuanfei_v3.1",
    "longjielidou_v3.1",
    "longanlingxi_v3.1",
    "longhuohuo_v3.1",
    "longyingtao_v3.1",
    "longanya_v3.1",
    "longwan_v3.1",
    "longxing_v3.1",
    "longhua_v3.1",
    "longhan_v3.1",
    "longanzhi_v3.1",
    "longzhe_v3.1",
    "longanyang_v3.1",
    "libai_v3.1",
    "longling_v3.1",
    "longniuniu_v3.1",
    "longshanshan_v3.1",
    "longpaopao_v3.1",
    "loongstella_v3.1",
    "longyuan_v3.1",
    "longmiao_v3.1",
    "longsanshu_v3.1",
    "longanli_v3.1",
    "longanwen_v3.1",
    "longanlang_v3.1",
    "longxiaoxia_v3.1",
    "longanchong_v3.1",
]

INSTRUCTIONS = "你是桌遊店裡的遊戲主持人，說話熱情、簡短，用中文回答。"
CONNECT_PROMPT = "請用一句話歡迎今晚來玩《血與刃的白薔薇》的玩家，二十個字以內。"
VOICE_PROMPT = "請只說這句話：大家好，我是今晚的主持人。"

SAMPLE_RATE = 24000  # output PCM: 24 kHz, 16-bit, mono
EVENT_TIMEOUT = 15.0
RESPONSE_TIMEOUT = 45.0


@dataclass
class Result:
    model: str
    voice: str
    voice_reported: str = ""
    error: str = ""
    audio_bytes: int = 0
    first_audio_ms: int | None = None
    transcript: str = ""
    wav_path: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.audio_bytes > 0

    @property
    def audio_seconds(self) -> float:
        return self.audio_bytes / (SAMPLE_RATE * 2)


def load_settings() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("HOST_REALTIME_API_KEY", "HOST_REALTIME_WORKSPACE_ID", "HOST_REALTIME_REGION"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    missing = [
        k for k in ("HOST_REALTIME_API_KEY", "HOST_REALTIME_WORKSPACE_ID") if not values.get(k)
    ]
    if missing:
        sys.exit(f"缺少設定：{', '.join(missing)}（放在 {env_file} 或環境變數）")
    # Accept the whole API Host as shown in the console (ws-xxx.ap-southeast-1.maas.aliyuncs.com):
    # keep the first label as the workspace ID and take the region from the host.
    host = values["HOST_REALTIME_WORKSPACE_ID"].removeprefix("https://").removeprefix("wss://")
    label, _, rest = host.split("/")[0].partition(".")
    values["HOST_REALTIME_WORKSPACE_ID"] = label
    if rest and not os.environ.get("HOST_REALTIME_REGION"):
        values["HOST_REALTIME_REGION"] = rest.split(".")[0]
    values.setdefault("HOST_REALTIME_REGION", "ap-southeast-1")
    return values


async def run_once(
    settings: dict[str, str], model: str, voice: str, prompt: str, out_dir: Path, tag: str
) -> Result:
    result = Result(model=model, voice=voice)
    # ⚠️ URL, header and event names follow the official WebSocket docs (checked 2026-11-19):
    # https://www.alibabacloud.com/help/en/model-studio/audio-realtime-websocket-access
    url = (
        f"wss://{settings['HOST_REALTIME_WORKSPACE_ID']}."
        f"{settings['HOST_REALTIME_REGION']}.maas.aliyuncs.com/api-ws/v1/realtime?model={model}"
    )
    headers = {"Authorization": f"Bearer {settings['HOST_REALTIME_API_KEY']}"}
    audio = bytearray()
    try:
        async with websockets.connect(url, additional_headers=headers, open_timeout=15) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "session.update",
                        "session": {
                            "modalities": ["text", "audio"],
                            "voice": voice,
                            "instructions": INSTRUCTIONS,
                            "input_audio_format": "pcm",
                            "output_audio_format": "pcm",
                            "turn_detection": None,  # push-to-talk: we trigger the reply ourselves
                        },
                    }
                )
            )
            while True:
                event = json.loads(await asyncio.wait_for(ws.recv(), EVENT_TIMEOUT))
                if event.get("type") == "error":
                    result.error = format_error(event)
                    return result
                if event.get("type") == "session.updated":
                    result.voice_reported = event.get("session", {}).get("voice", "")
                    break

            await ws.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": prompt}],
                        },
                    }
                )
            )
            sent_at = time.monotonic()
            await ws.send(json.dumps({"type": "response.create"}))

            deadline = sent_at + RESPONSE_TIMEOUT
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    result.error = f"{RESPONSE_TIMEOUT:.0f} 秒內沒有收到 response.done"
                    break
                event = json.loads(await asyncio.wait_for(ws.recv(), remaining))
                kind = event.get("type")
                if kind == "response.audio.delta":
                    if result.first_audio_ms is None:
                        result.first_audio_ms = int((time.monotonic() - sent_at) * 1000)
                    audio.extend(base64.b64decode(event.get("delta", "")))
                elif kind == "response.audio_transcript.done":
                    result.transcript = event.get("transcript", "")
                elif kind == "error":
                    result.error = format_error(event)
                    break
                elif kind == "response.done":
                    status = event.get("response", {}).get("status", "")
                    if status and status != "completed":
                        result.error = f"response.done status={status}"
                    break
    except websockets.exceptions.InvalidStatus as exc:
        body = exc.response.body.decode("utf-8", "replace")[:300] if exc.response.body else ""
        result.error = f"握手失敗 HTTP {exc.response.status_code} {body}".strip()
    except TimeoutError:
        result.error = "等待伺服器事件逾時"
    except Exception as exc:  # noqa: BLE001 — throwaway script: report anything else as-is
        result.error = f"{type(exc).__name__}: {exc}"

    result.audio_bytes = len(audio)
    if audio:
        # ✅ got audio back: save it so a human can listen
        path = out_dir / f"{tag}.wav"
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(bytes(audio))
        result.wav_path = str(path)
    return result


def format_error(event: dict) -> str:
    error = event.get("error", {})
    return f"{error.get('code') or error.get('type') or 'error'}: {error.get('message', '')}"


def print_result(r: Result) -> None:
    mark = "OK  " if r.ok else "FAIL"
    first = f"{r.first_audio_ms} ms" if r.first_audio_ms is not None else "-"
    print(
        f"[{mark}] {r.model}  voice={r.voice}  回報voice={r.voice_reported or '-'}  "
        f"音訊={r.audio_seconds:.1f} 秒  文字送出到第一段音訊={first}"
    )
    if r.transcript:
        print(f"       逐字稿：{r.transcript}")
    if r.error:
        print(f"       錯誤：{r.error}")
    if r.wav_path:
        print(f"       聲音檔：{r.wav_path}")


async def cmd_connect(settings: dict[str, str], out_dir: Path, models: list[str]) -> int:
    results = []
    for key in models:
        r = await run_once(
            settings, MODELS[key], DEFAULT_VOICE, CONNECT_PROMPT, out_dir, f"connect-{key}"
        )
        print_result(r)
        results.append(r)
    return 0 if all(r.ok for r in results) else 1


async def cmd_voices(
    settings: dict[str, str], out_dir: Path, model_key: str, voices: list[str]
) -> int:
    rows = []
    for voice in voices:
        r = await run_once(
            settings, MODELS[model_key], voice, VOICE_PROMPT, out_dir, f"voice-{model_key}-{voice}"
        )
        print_result(r)
        rows.append(r)
        await asyncio.sleep(0.5)
    lines = [
        f"# {MODELS[model_key]} 聲線測試（{settings['HOST_REALTIME_REGION']}）",
        "",
        "| voice | 結果 | session.updated 回報的 voice | 音訊秒數 | 錯誤 |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for r in rows:
        lines.append(
            f"| `{r.voice}` | {'OK' if r.ok else 'FAIL'} | {r.voice_reported or '-'} "
            f"| {r.audio_seconds:.1f} | {r.error or ''} |"
        )
    report = out_dir / "voices.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok = [r.voice for r in rows if r.ok]
    print(f"\n叫得動 {len(ok)}／{len(rows)} 個聲線。表格：{report}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, help="聲音檔資料夾（預設在系統暫存區，不進 repo）")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_connect = sub.add_parser("connect", help="Flash 與 Plus 各連一次，存下回覆的聲音")
    p_connect.add_argument("--models", nargs="+", choices=list(MODELS), default=list(MODELS))
    p_voices = sub.add_parser("voices", help="逐一試每個聲線叫不叫得動")
    p_voices.add_argument("--model", choices=list(MODELS), default="flash")
    p_voices.add_argument("--voices", nargs="+", default=VOICES)
    args = parser.parse_args()

    settings = load_settings()
    out_dir = args.out or Path(tempfile.gettempdir()) / "qwen-smoke" / time.strftime(
        "%Y%m%d-%H%M%S"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"區域 {settings['HOST_REALTIME_REGION']}，聲音檔存在 {out_dir}\n")

    if args.cmd == "connect":
        return asyncio.run(cmd_connect(settings, out_dir, args.models))
    return asyncio.run(cmd_voices(settings, out_dir, args.model, args.voices))


if __name__ == "__main__":
    sys.exit(main())
