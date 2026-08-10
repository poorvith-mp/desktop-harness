# Voice control — Grok Voice Think Fast 2.0 + desktop-harness

**Status:** designed + scaffolded (2026-08-10)  
**Question:** Can we control the Mac by voice with Grok Voice Think Fast 2.0?  
**Answer:** **Yes — via tool calling, not because voice “includes” screen control.**

---

## How it actually works

Grok Voice is a **speech-to-speech** model over WebSocket:

```
  Mic ──► wss://api.x.ai/v1/realtime?model=grok-voice-think-fast-2.0
                │
                │  (hears you, reasons, can speak back)
                │
                ├── function call: open_app("Safari")
                ├── function call: click_text("Bookmarks")
                ├── function call: type_text("…")
                └── …
                │
                ▼
         desktop-harness helpers
         (AX + real mouse + keyboard)
```

Voice **does not** see the screen by itself.  
Capability = **tools you register** + our harness executing them.

That matches prior research: *“capability for agents comes from function/tool calling, not built-in screen control.”*

---

## Auth reality check (important)

| What you have | What Voice API needs |
|---------------|----------------------|
| **Grok Build** login (`~/.grok/auth.json` OIDC) | **Not the same thing** |
| SuperGrok / app subscription | Great for Grok apps; **not** automatic Voice API credits |
| **`XAI_API_KEY`** from [console.x.ai](https://console.x.ai) | **Required** for `wss://api.x.ai/v1/realtime` |

Pricing (order of magnitude): Voice Agent is billed per connection minute (docs historically ~$0.05/min — confirm live pricing).

**Grok Build subscription alone is not enough.** You need an API key with Voice enabled. Store it in the environment or Keychain — **never** in vault/context markdown.

```bash
export XAI_API_KEY="…"   # from console.x.ai — do not commit
```

---

## Best product shapes (ranked)

### 1. Hotkey → local voice daemon (recommended)

- Global shortcut (e.g. **Right ⌥** hold, or **⌘⇧Space**)
- Starts/stops a local process: mic → Realtime WS → tools → harness
- Menubar status: idle / listening / acting
- **Why best:** same muscle memory as Quill; full system control; no browser sandbox

### 2. Thin menubar app (Swift or Python + rumps)

- Click mic → talk → Grok acts on Mac
- Easier for non-CLI users later
- Quill already proved local menubar + Grok APIs for *dictation*; this is *control*

### 3. Grok Build skill only (no separate voice UI)

- You type/speak *in* Grok Build; agent runs `desktop-harness`
- Already works for **text** control
- **Does not** use Think Fast 2.0 S2S unless Grok Build exposes that channel (it doesn’t as a local tool today)

### 4. Browser extension

- **Weak** for OS control (sandbox). Skip for laptop control.

### 5. Phone Action Button → Mac

- Possible later (Continuity / self-hosted relay). Overkill for v1.

**Build order:** scaffold tools + CLI session → hotkey wrapper → menubar polish.

---

## Tool surface (what voice can call)

Keep tools **small and safe** — voice models do better with 8–15 clear tools than 200 raw APIs.

| Tool | Maps to harness |
|------|-----------------|
| `list_apps` | `list_apps()` |
| `open_app` | `open_app(name)` |
| `screen_labels` | `labels(app?)` |
| `click_text` | `click_text(text, app?)` |
| `type_text` | `type_text(text)` |
| `hotkey` | `hotkey(*keys)` |
| `move_mouse` | `move_to(x,y)` |
| `click_xy` | `click(x,y)` |
| `screenshot_app` | `screenshot(app=…)` path only |
| `run_shell` | **optional, high risk** — off by default |

**Consent:** tools that send messages, pay, delete, or change security settings must confirm with the user (voice: “Confirm delete? Say yes.”) or refuse.

---

## Files in this repo

| File | Role |
|------|------|
| `VOICE.md` | this design |
| `src/desktop_harness/voice_tools.py` | tool schemas + local executor |
| `scripts/voice_session.py` | Realtime WS loop (needs `XAI_API_KEY`) |
| `scripts/voice_hotkey_readme.md` | how to bind a global shortcut |

---

## Run (when key is set)

```bash
export XAI_API_KEY="…"
cd ~/Developer/grok/experiments/desktop-harness/grok-20260810
source .venv/bin/activate
pip install websockets sounddevice numpy   # mic + WS
python scripts/voice_session.py            # full duplex
python scripts/voice_session.py --dry-run  # print tool calls, no mouse
```

Without a key, `voice_session.py` exits with a clear message (does not invent access).

---

## Relationship to Quill

| | **Quill** | **Voice + desktop-harness** |
|--|-----------|------------------------------|
| Job | Dictate text into any field | **Control** the Mac by voice |
| Model | STT → insert | S2S + **tools** |
| Output | Keystrokes of words | open apps, click, type, mouse |

Complementary. Don’t merge them.

---

## Longer path

1. ✅ desktop-harness hands/eyes  
2. ✅ voice tool schemas + session script  
3. Wire `XAI_API_KEY` (you, once)  
4. Global hotkey (Karabiner / Raycast / tiny Swift)  
5. Menubar app + “acting” cursor overlay while tools run  
6. Optional: MCP server so *any* agent calls the same tools  

---

## Bottom line

- **Possible:** yes, cleanly, with Think Fast 2.0 **function tools** → harness.  
- **Included free in Grok Build login:** no — needs **API key** + voice billing.  
- **Best UX:** hotkey-launched local voice session, not a browser extension.  
