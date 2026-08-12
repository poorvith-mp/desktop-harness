# desktop-harness

**Agent hands for your Mac.**  
Built for **[Grok Build](https://grok.com)** — a first-class Mac control surface when the GUI is the task.

Also works with **any agent that can run a shell command** (Claude Code, Codex CLI, scripts, etc.). Grok Build is the home base; other tools are welcome.

```text
You → Grok Build (or another agent) → desktop-harness → your Mac
```

| | |
|--|--|
| **Name** | `desktop-harness` |
| **Primary** | **Grok Build** (skill + CLI) |
| **Also works with** | Claude Code, Codex CLI, plain shell, other coding agents |
| **What it is** | Local **CLI + agent skill** (not an MCP server) |
| **How it sees** | **Accessibility tree first**, screenshots only as fallback |
| **How it acts** | Real system mouse + keyboard (`CGEvent`) + AX press |
| **Platform** | macOS (Sequoia+ recommended) |
| **Status** | v0.5.1 |
| **Built with** | [Grok Build](https://grok.com) |

---

## Is this an MCP tool?

**No.** Not right now.

| Shape | Role |
|-------|------|
| **CLI** `desktop-harness` | What actually runs |
| **Skill** (`SKILL.md`) | Teaches Grok Build *when/how* to call the CLI |
| **Optional daemon** | Keeps Python/pyobjc warm so multi-step tasks stay fast |
| **MCP** | Not required; could wrap the same API later |

Agents already have shell. A thin CLI is the lowest-friction path for Grok Build today.

**Agent view (v0.5):** `show_monitor()` pops a small live picture of whatever the
agent is driving (Notes, Settings, Chrome…). Stay in Grok Build and still see
the work. Web tasks use `open_stage(url)` — a dedicated small Chrome window,
not your everyday tabs and not a fullscreen takeover.

---

## Why it’s fast (the efficient path)

Many computer-use setups do:

> screenshot → vision model → guess pixels → click → repeat  

That’s capable but **slow and expensive**.

**desktop-harness** uses what macOS already gives every app:

1. **Shell first** when the task isn’t really GUI  
2. **Accessibility (AX) tree** — buttons, labels, fields as structured text (~ms)  
3. **AXPress / set value** before synthetic clicks  
4. **Window screenshot** only when AX is empty (custom canvas, games)  
5. **Warm daemon** so step 2…N don’t re-import pyobjc every time  

Full capability without a vision loop on every click.

---

## Install

```bash
git clone https://github.com/xfreeze2/desktop-harness.git
cd desktop-harness
chmod +x install.sh && ./install.sh
# puts desktop-harness on ~/.local/bin and registers Grok skill if ~/.grok exists
```

Manual path: see [install.md](./install.md).

### Updating (no auto-update)

This tool is a **local CLI** — it has no background app that pings the store.
Agents only run it when a task needs Mac control. To update:

```bash
cd /path/to/desktop-harness
git pull
./install.sh          # refresh venv + PATH shim + Grok skill
desktop-harness check-update   # optional: compare to GitHub main
desktop-harness --version
```

There is **no silent auto-update** (by design — you control when code that can move your mouse changes).

### Permissions (once)

System Settings → Privacy & Security:

1. **Accessibility** — on for Terminal / Ghostty / your agent host  
2. **Screen Recording** — on (for screenshots); restart the host app after  

```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
desktop-harness --doctor
```

### Agent skill (Grok Build)

```bash
mkdir -p ~/.grok/skills/desktop-harness
desktop-harness skill > ~/.grok/skills/desktop-harness/SKILL.md
```

Other agents: call the same CLI from shell; point them at `SKILL.md` if they support skills.

---

## Quick use

```bash
# Release checks (non-destructive)
desktop-harness selftest

# Visible smoke test (watch the mouse + TextEdit)
desktop-harness demo

# What am I looking at?
desktop-harness <<'PY'
print(frontmost_app())
print(labels()[:15])
PY

# Open an app and click by name
desktop-harness <<'PY'
open_app("TextEdit")
click_text("Format")   # when that menu exists
PY

# Real mouse
desktop-harness <<'PY'
print(mouse_pos())
move_to(400, 300)
click(400, 300)
PY
```

### Warm daemon (recommended for multi-step agent runs)

```bash
desktop-harness daemon start --bg   # warm process in background
desktop-harness daemon status
# subsequent desktop-harness calls auto-use the daemon when it’s up
desktop-harness daemon stop
```

Env knobs:

| Variable | Effect |
|----------|--------|
| `DH_NO_DAEMON=1` | Always in-process |
| `DH_MOUSE_INSTANT=1` | Warp mouse with no animation |
| `DH_PRESENCE=1` (default) | Ice ring + bottom **Hands off — agent** island while controlling |
| `DH_PRESENCE=0` | Disable presence UI |
| `DH_SAFE=1` (default) | Agent policy defaults |
| `DH_ALLOW_SENSITIVE=1` | Allow sensitive app names / overrides |

**Presence (default on):** **one** system cursor + ice halo while moving; brief **amber** halo on click; large bottom **Hands off — agent** island (above the Dock). No second fake arrow. Off: `DH_PRESENCE=0`.

**Observe loop (optional):** for agents *building* visual things — demo → **many** screenshots → look → fix. Not needed for normal control. See `docs/OBSERVE-LOOP.md` / `scripts/observe-demo.sh`.

---

## Safety

This drives a **real** computer.

- Default blocks for password-manager-like apps (open + mutations while frontmost)  
- Audit log: `~/.desktop-harness/audit.jsonl`  
- Warm daemon: owner-only socket + token (see [SECURITY.md](./SECURITY.md))  
- **Agents must ask** before send/post/pay/delete/security changes (see skill)  
- **Voice scaffold** (`scripts/voice_session.py`) is gated separately: mutations need `--live`; without it only read-only tools run (see [SECURITY.md](./SECURITY.md))

You can always grab the mouse; physical input wins.

---

## How it works (one diagram)

```
┌──────────────────────────────────────────┐
│  Grok Build (primary) / other agents     │
│     desktop-harness <<'PY' …             │
└──────────────────┬───────────────────────┘
                   │  (optional warm daemon)
         ┌─────────▼─────────┐
         │    helpers.py     │
         └─────────┬─────────┘
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
 ax.py         capture.py      input.py
 AX tree       window PNG      real mouse
 (primary)     (fallback)      + keyboard
```

Plain English: [HOW_IT_WORKS.md](./HOW_IT_WORKS.md)  
Architecture notes: [DESIGN.md](./DESIGN.md)

---

## API surface (helpers)

| Helper | Purpose |
|--------|---------|
| `list_apps` / `list_windows` / `frontmost_app` | Discovery |
| `open_app` / `activate` | Launch / focus |
| `ax_snapshot` / `labels` / `find` | See UI structure |
| `click_text` / `set_field` | Act by name (`exact=True` for Play/Pause) |
| `media_transport` / `ensure_media_playing` | Read player state; play once without toggling |
| `mouse_pos` / `move_to` / `wiggle` / `click` / `drag` / `scroll` | Real pointer |
| `type_text` / `hotkey` / `key` | Keyboard |
| `screenshot` | Window/display capture |
| `enable_agent_cursor` | Optional blue ring |

---

## What it’s not

- Not a replacement for shell/git/API work  
- Not a sandboxed VM — it drives **your** real Mac (use with care)  
- Not locked to one agent brand — **built for Grok Build**, usable from any shell agent  

---

## Roadmap

- [x] AX-first control + CLI + skill  
- [x] Real system mouse  
- [x] Warm daemon + faster defaults  
- [x] Safety gates + audit log  
- [x] `selftest` + `install.sh` + media-safe helpers  
- [ ] Background control without stealing focus  
- [ ] Optional MCP wrapper  
- [ ] One-click `.app` permission onboarding  

---

## License

MIT — see [LICENSE](./LICENSE).
