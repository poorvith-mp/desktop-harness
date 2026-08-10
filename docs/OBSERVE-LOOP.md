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

**Dense capture (required for motion bugs):** one screenshot is not enough.
Take many frames while moving so lag/desync shows up:

```bash
./scripts/observe-demo.sh /tmp/dh-observe
# then read several frames: hold, mid-move, click
```

## Checklist for presence

- [ ] **One** cursor only — soft halo around system pointer, never a second arrow  
- [ ] Halo locked to warp target (no “dragging a second cursor”)  
- [ ] Move = soft blue; click = brief red then blue  
- [ ] Banner fully on-screen (not half in Dock), neon edge readable  
- [ ] Hands-off meaning is obvious  
- [ ] Multiple frames reviewed, not one still
