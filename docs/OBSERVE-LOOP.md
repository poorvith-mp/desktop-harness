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

For a single action during normal (non-presence) control, you don't need
this whole loop — call `verify()` (see SKILL.md) and read the one
screenshot it returns. This loop is for when you're iterating on *how
something looks or behaves over time*, where one frame can't tell you
whether it's actually working.

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
- [ ] Move = ice ring; click = brief amber then ice  
- [ ] Compact glass island under the menu bar (not on Dock / mini-player)  
- [ ] Hands-off meaning is obvious  
- [ ] Multiple frames reviewed, not one still
- [ ] **A click lands on a different app mid-sequence, and the demo keeps
      going for several more seconds afterward.** Confirm via frames taken
      *after* that click that the halo/banner are still visible. A demo
      that never gives up focus will pass even when this is broken — it
      shipped that way once already (2026-08-11: banner and halo silently
      stopped rendering the instant any other window became key, because
      the accessory app's run loop was never being pumped outside of
      show()/click_flash(); move() — the highest-frequency caller — pumped
      nothing at all).
- [ ] **Several seconds of pure idle** (no move/click calls, just a wait)
      immediately after that same focus-stealing click. Confirm the
      overlay is still there afterward, not just immediately after the
      click. A fix that only covers "during active motion" is not the
      same bug as "while sitting idle," and the second is the more common
      real case (an agent pausing between steps).
- [ ] If a fix here reaches for a background thread to keep something
      updating during idle time: don't. AppKit hard-aborts the whole
      process (SIGABRT, no Python exception, unrecoverable) when window
      methods are called off the main thread — confirmed by trying it.
      Chunk the wait on the calling thread instead (see
      `presence.keep_alive()`).
