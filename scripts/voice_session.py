#!/usr/bin/env python3
"""Grok Voice Think Fast 2.0 session → desktop-harness tools.

Requires:
  export XAI_API_KEY=...   # from https://console.x.ai  (NOT Grok Build login)

Usage:
  python scripts/voice_session.py --dry-run     # tools only, no mic/network if no key
  python scripts/voice_session.py               # full duplex (needs key + mic)
  python scripts/voice_session.py --text "Open TextEdit and type hello"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# project import
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MODEL = os.environ.get("GROK_VOICE_MODEL", "grok-voice-think-fast-2.0")
WS_URL = f"wss://api.x.ai/v1/realtime?model={MODEL}"


def main():
    ap = argparse.ArgumentParser(description="Voice → desktop-harness")
    ap.add_argument("--dry-run", action="store_true", help="Execute no real GUI; print tool calls")
    ap.add_argument("--text", type=str, default=None, help="One-shot text turn (no mic)")
    ap.add_argument("--list-tools", action="store_true")
    args = ap.parse_args()

    from desktop_harness.voice_tools import (
        SESSION_INSTRUCTIONS,
        TOOL_DEFINITIONS,
        execute,
    )

    if args.list_tools:
        for t in TOOL_DEFINITIONS:
            print(f"- {t['name']}: {t['description'][:80]}")
        return

    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key and not args.dry_run:
        print(
            "Missing XAI_API_KEY.\n\n"
            "Grok Build login is NOT enough for Voice API.\n"
            "1. Create a key at https://console.x.ai\n"
            "2. export XAI_API_KEY='…'\n"
            "3. Re-run this script\n\n"
            "Tip: try --dry-run to inspect tools without a key:\n"
            "  python scripts/voice_session.py --dry-run --text 'demo'\n",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.dry_run and not key:
        # local demo of tool executor only
        print("dry-run local tools (no network)")
        demos = [
            ("list_apps", {}),
            ("mouse_pos", {}),
            ("screen_labels", {"limit": 10}),
        ]
        for name, args_ in demos:
            out = execute(name, args_, dry_run=False)  # list_apps is read-only ok
            print(f"\n>> {name} {args_}\n{out[:500]}")
        print("\nTo run live voice: export XAI_API_KEY=… && python scripts/voice_session.py")
        return

    try:
        import websockets
    except ImportError:
        print("pip install websockets", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run_session(key, text=args.text, dry_run=args.dry_run))


async def run_session(api_key: str, *, text: str | None, dry_run: bool):
    import websockets
    from desktop_harness.voice_tools import (
        SESSION_INSTRUCTIONS,
        TOOL_DEFINITIONS,
        execute,
    )

    headers = {"Authorization": f"Bearer {api_key}"}
    print(f"connecting {WS_URL} …")
    async with websockets.connect(
        WS_URL,
        additional_headers=headers,
        max_size=8 * 1024 * 1024,
    ) as ws:
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "voice": "eve",
                "instructions": SESSION_INSTRUCTIONS,
                "tools": TOOL_DEFINITIONS,
                "turn_detection": {"type": "server_vad"} if not text else None,
            },
        }))
        print("session configured (tools registered).")

        if text:
            await ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }))
            await ws.send(json.dumps({"type": "response.create"}))
            print(f"sent text turn: {text!r}")
        else:
            print(
                "Mic streaming not wired in this scaffold yet.\n"
                "Use --text \"Open Safari\" for a tool-using turn,\n"
                "or next step: add sounddevice PCM → input_audio_buffer.append.\n"
            )
            # Still listen for a few events so config errors show up
            pass

        pending_calls = []
        async for raw in ws:
            if isinstance(raw, bytes):
                continue
            event = json.loads(raw)
            et = event.get("type", "")
            if et in ("error", "session.updated", "response.done",
                      "response.function_call_arguments.done",
                      "response.output_audio_transcript.delta",
                      "response.output_text.delta",
                      "conversation.item.input_audio_transcription.completed"):
                if et == "error":
                    print("ERROR:", event)
                elif et == "session.updated":
                    print("session.updated ok")
                elif et.endswith("transcript.delta") or et.endswith("text.delta"):
                    delta = event.get("delta") or event.get("text") or ""
                    if delta:
                        print(delta, end="", flush=True)
                elif et == "response.function_call_arguments.done":
                    name = event.get("name")
                    call_id = event.get("call_id")
                    arguments = event.get("arguments") or "{}"
                    print(f"\n[tool] {name}({arguments})")
                    result = execute(name, arguments, dry_run=dry_run)
                    print(f"[tool result] {result[:300]}")
                    await ws.send(json.dumps({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": result,
                        },
                    }))
                    pending_calls.append(call_id)
                elif et == "response.done":
                    if pending_calls:
                        # after all outputs, continue (simplified: one create)
                        await ws.send(json.dumps({"type": "response.create"}))
                        pending_calls.clear()
                    if text:
                        print("\n(text turn complete)")
                        break
            # ignore noisy audio deltas in text mode


if __name__ == "__main__":
    main()
