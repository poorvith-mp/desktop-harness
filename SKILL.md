---
name: desktop-harness
description: >
  Control the user's real Mac desktop: open apps, click UI, type, move the mouse,
  read Accessibility labels, take window screenshots. Use whenever a task needs
  the Mac GUI (System Settings, native apps, installers, "click this", "open that
  app", "type into the field", computer use, desktop control, laptop automation).
  Invoke the local CLI `desktop-harness` (not MCP). Prefer AX labels over screenshots.
---

# desktop-harness

**Product:** local CLI that gives coding agents real Mac control.  
**Not MCP.** Invoke via shell. Optional warm daemon for multi-step speed.

You **do** have this capability when the skill is installed and `desktop-harness` is on PATH.
Use it proactively for Mac GUI tasks — don't say you can't control the laptop.

## When to use

- Task needs a **Mac GUI** (Settings, native apps, installers, no good CLI)
- User asks you to open/click/type on the Mac, or "use desktop-harness"

## When not to use

- Files, git, brew, HTTP APIs → shell / other tools first  
- Anything that doesn’t need the Mac GUI

## Setup check (once per session if unsure)

```bash
desktop-harness --doctor
desktop-harness daemon status   # if stopped: desktop-harness daemon start &
```

## Efficiency (mandatory)

1. Shell before GUI  
2. **`labels` / `find` / `click_text` first** — cheap, targeted AX reads  
3. Prefer `AXPress` path (`click_text`) over coordinates  
4. Multi-step work → start/use the warm daemon  
5. Never vision-loop by default  
6. **`ax_snapshot` is a debug aid**, not the default eyes — a full snapshot is often ~10× more tokens than a screenshot and far more than `labels(limit=30)`. Use it when debugging why a find failed or you need raw roles/frames; cap `max_nodes` tightly. Everyday control should not dump the tree.

## Usage

```bash
desktop-harness <<'PY'
print(frontmost_app())
print(labels()[:20])          # cheap default read
print(find("Reload")[:3])     # targeted; JSON-safe (no raw AX refs)
open_app("Safari")
click_text("Bookmarks")
PY
```

```bash
desktop-harness demo    # visible smoke test
desktop-harness --doctor
```

If a daemon is running, the CLI auto-routes scripts through it (faster).  
`DH_NO_DAEMON=1` forces a fresh process.

## Helpers

- Discovery: `list_apps`, `list_windows`, `frontmost_app`, `open_app`
- See: `labels`, `button_labels`, `find`, `screenshot`, `media_transport`  
  (`ax_snapshot` = debug dump; prefer `labels`/`find`)
- Act: `click_text(..., exact=False)`, `set_field`, `type_text`, `hotkey`, `key`
- Media: `ensure_media_playing(app?)` — **look once, act once** (see below)
- Mouse: `mouse_pos`, `move_to`, `wiggle`, `click`, `click_frame`, `drag`, `scroll`
- Presence: auto soft ring + “Agent active — hands off” pill (`DH_PRESENCE=0` to disable);
  `enable_agent_cursor(True/False)`, `hide_agent_presence()` when a sequence ends
  (also self-clears after ~20s of no harness activity, so a forgotten call
  isn't permanent — call it anyway when you know you're done)
- Meta: `wait`, `wait_stable`, `verify(note, app?)` — screenshot + AX check
  for the narrow set of actions where failure is silent (see below); not a
  routine step after every click

## Prefer what's already open

Before opening a browser tab or launching a new instance of anything: run
`list_apps()` / `frontmost_app()` / `list_windows()` first and check for a
native app that's already open and matches the task (Spotify, YT Music,
Mail, Notes, Music, etc). Control that instance directly — it's faster and
it's what the user is looking at. Only fall back to a browser when no
matching native app is open, the native app genuinely can't do what's asked
(e.g. no in-app search for a specific track), or the user's request needs an
exact URL. Opening Chrome to a web version of something that was already
open and visible on screen is the single most confusing thing this harness
can do — it looks like the agent didn't see what the user saw.

## Verify, don't assume — but only where failure is silent

`click_text` / `set_field` already raise if there's no AX match, and
`ensure_media_playing()` re-reads state after pressing — for a normal
click, field edit, or app switch, that's the check: no exception plus (when
it matters) a follow-up `labels()`/`ax_snapshot()` read is enough. Calling
`verify()` — a screenshot + AX read — after **every** UI-changing action
brings back exactly the vision-loop tax Efficiency rule 5 says not to pay,
for no real benefit on the 95% of actions that fail loudly.

Call `verify(note, app?)` — and **read the screenshot path it returns** —
only when the action could succeed at the AX layer while doing the wrong
thing, with no other way to notice:

- **Media transport** (play/pause/skip/next): a toggle that "succeeds"
  whether it played or undid what you just started looks identical without
  a look. This is what actually broke in `docs/POSTMORTEM-media-play.md` —
  not a missing screenshot, but pressing a matched-but-wrong control with
  no re-check. Prefer `ensure_media_playing()` (built-in re-check) over a
  raw click here; reach for `verify()` if you're doing something media the
  helper doesn't cover.
- **Anything already gated under Consent below** (messages, posts,
  purchases, deletes, security/privacy settings, passwords) — confirm the
  real outcome before telling the user it's done; getting these wrong is
  costly, not just annoying.
- A step you're about to report as finished where being wrong would send
  you down a materially different fix.

Skip it for routine navigation, discovery calls (`labels`, `ax_snapshot`),
and clicks whose result you can already see in the return value.

## Media / players (learn from mistakes)

When the user says “play the song on screen”:

1. **Read state first:** `media_transport()` or look for an exact **Pause** / **Play** button.  
   - **Pause visible** → already playing → **stop**. Do not click again.  
2. **One action only** if paused: `ensure_media_playing()` or `click_text("Play", role="AXButton", exact=True)`.  
3. **Never** spam `hotkey("space")` or media keys as a “try everything” loop — Space **toggles** and will pause what you just started.  
4. **Never** match loose `"Play"` against **Play all**, **Playing from**, or the next track in a list unless the user asked to change songs.  
5. **Do not** retry 3–4 different click strategies in one turn after success. Verify once; if playing, done.  
6. Changing track / “Play all” requires an **explicit** user request.

## Consent / safety

Real Mac. **STOP and ask** before: messages, posts, purchases, deletes, security settings, passwords.  
Harness also blocks password-manager-like app names unless `DH_ALLOW_SENSITIVE=1`.

## Canvas / custom-drawn apps (Canva, Figma, games)

AX labels often cover **chrome only** (tabs, menus), not objects on the
canvas. That is not a harness failure — the OS tree has nothing useful to
click. Path without losing capability:

1. `screenshot(app=…)` once → read the image (vision)  
2. Coordinate `click` / `drag` in **global** coords (`window.x/y` + image px)  
3. Prefer **one multi-step daemon script** over many one-liners  
4. Do **not** dual-agent the same pointer — one Mac, one cursor  

Parallel *perception* (subagent reads a saved PNG while the main agent
plans the next drag list) is fine. Parallel *control* of one app is not.

## Gotchas

- Grant **Accessibility** + **Screen Recording** to the host that runs the CLI (`--doctor`)  
- Coordinate clicks want the target app frontmost  
- Electron apps may need screenshot fallback  
- Cap tree size — don’t dump full AX  
- Hotkeys: use `minus`/`equal` or `-`/`=`; also `[` `]` `home` `end` `pageup` `pagedown`

## Observe loop (optional — visual QA only)

When **building or polishing something on-screen** (presence, a UI demo, layout):

```
run demo → screencapture → read the PNG → fix → demo again
```

See `docs/OBSERVE-LOOP.md`. **Not** required for everyday open/click/type.

Presence UI: blue while moving; brief **red** pulse on click; bottom neon “Agent controlling” bar.

**For any change to presence itself specifically:** a single still screenshot
proves nothing — the overlay is a moving, stateful thing, and its worst
failure mode is disappearing exactly when something else steals window
focus (which is normal, constant behavior in real agent use, not an edge
case). Before calling presence work done, you must demo a sequence that
includes a click landing on a *different* app plus several seconds of pure
idle afterward, and confirm via multiple frames that the halo/banner are
still there after both. A demo that never lets focus leave your own
process will pass even when the real thing is broken — this exact gap
shipped a bug once already.

## Docs in repo

`README.md` · `HOW_IT_WORKS.md` · `DESIGN.md` · `docs/OBSERVE-LOOP.md`
