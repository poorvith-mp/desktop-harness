# Observe loop — build, see, fix

**Optional for end users. Recommended for agents building anything visual.**

Normal desktop-harness control (open app, click, type) does **not** need this loop.
Use it when you’re **shipping or polishing UI** (presence, a page, a demo) so the
agent sees the same pixels you do.

```
demo  →  screenshot  →  look at the image  →  fix  →  demo again
```

Do **not** declare “looks good” without reading a capture.  
Do **not** push every micro-tweak — only after a loop pass you’re proud of.

## Steps (agent)

1. **Run the thing** (demo script / harness action).  
2. **Capture** full screen (or window) while it runs:
   ```bash
   mkdir -p /tmp/dh-observe
   screencapture -x /tmp/dh-observe/01.png
   ```
3. **Read the image** with the image tool (`read_file` on the PNG).  
4. **Note what’s wrong** in plain language (position, contrast, lag, wrong chrome…).  
5. **Fix code** for those notes only.  
6. **Demo + capture again** until notes are empty or only polish.  
7. **Then** commit/push if the user wants it public.

## Why

You and the agent should see the **same pixels**.  
Vision on a screenshot is how the agent “sits next to you” without guessing.

## Presence UI specifically

```bash
# Terminal A / background: timed captures
mkdir -p /tmp/dh-observe && rm -f /tmp/dh-observe/*.png
( sleep 1.2; screencapture -x /tmp/dh-observe/hold.png
  sleep 2.0; screencapture -x /tmp/dh-observe/move.png
  sleep 1.5; screencapture -x /tmp/dh-observe/click.png ) &

# Terminal B: demo
DH_NO_DAEMON=1 DH_PRESENCE=1 desktop-harness <<'PY'
enable_agent_cursor(True)
# … moves …
hide_agent_presence()
PY
```

Then open each PNG and critique.

## Checklist for presence

- [ ] Banner clear of notch / menu / tab strip  
- [ ] Banner readable but not loud  
- [ ] Pointer is cursor-like with soft glow (not a bold disc)  
- [ ] No obvious double-cursor lag  
- [ ] Click feedback subtle  
- [ ] Hands-off meaning is obvious  
