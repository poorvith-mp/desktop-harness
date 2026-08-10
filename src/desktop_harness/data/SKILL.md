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
2. `labels` / `ax_snapshot` / `click_text` before screenshots  
3. Prefer `AXPress` path (`click_text`) over coordinates  
4. Multi-step work → start/use the warm daemon  
5. Never vision-loop by default  

## Usage

```bash
desktop-harness <<'PY'
print(frontmost_app())
print(labels()[:20])
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
- See: `labels`, `button_labels`, `ax_snapshot`, `find`, `screenshot`, `media_transport`
- Act: `click_text(..., exact=False)`, `set_field`, `type_text`, `hotkey`, `key`
- Media: `ensure_media_playing(app?)` — **look once, act once** (see below)
- Mouse: `mouse_pos`, `move_to`, `wiggle`, `click`, `click_frame`, `drag`, `scroll`
- Presence: auto soft ring + “Agent active — hands off” pill (`DH_PRESENCE=0` to disable);
  `enable_agent_cursor(True/False)`, `hide_agent_presence()` when a sequence ends
- Meta: `wait`, `wait_stable`

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

## Gotchas

- Grant **Accessibility** + **Screen Recording** to the host that runs the CLI (`--doctor`)  
- Coordinate clicks want the target app frontmost  
- Electron apps may need screenshot fallback  
- Cap tree size — don’t dump full AX  

## Docs in repo

`README.md` · `HOW_IT_WORKS.md` · `DESIGN.md`
