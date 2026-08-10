# Launch voice control with a hotkey

Once `XAI_API_KEY` is set and `voice_session.py` works with `--text`, bind a global shortcut.

## Option A — Raycast / Alfred / Keyboard Maestro

Command:

```bash
export XAI_API_KEY="$(security find-generic-password -s xai-api-key -w 2>/dev/null)"
cd "$HOME/Developer/grok/experiments/desktop-harness/grok-20260810"
source .venv/bin/activate
python scripts/voice_session.py
```

Suggested hotkey: **⌃⌥Space** (Control-Option-Space) — easy, free of Grok/Quill conflicts.

## Option B — Store key in Keychain (recommended)

```bash
security add-generic-password -a "$USER" -s xai-api-key -w 'YOUR_KEY_HERE' -U
```

Never put the key in NOW.md or context vault files.

## Option C — Tiny menubar (later)

Python `rumps` or Swift menu bar: Start / Stop session, show “Listening… / Acting…”.

Quill already occupies a corner dictation UX; this control agent should be a separate icon (e.g. “DH Voice”).
