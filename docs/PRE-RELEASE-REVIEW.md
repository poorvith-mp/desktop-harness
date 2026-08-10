# Pre-release code review — desktop-harness

**Scope:** all Python under `src/desktop_harness/` (plus packaging/docs as release surface)  
**Path:** `experiments/desktop-harness/grok-20260810/`  
**Date:** 2026-08-10  
**Reviewer:** Grok Build (code-review pass)  
**Claim under test:** “Agent hands for your Mac” — AX-first CLI + skill, safe enough and documented enough for public use

No source was modified in this pass except this report.

---

## Critical (must fix before release)

### 1. Safety gates are mostly advisory — sensitive apps can still be driven

**Where:** `safety.py` (`check_app_allowed`, `check_helper_allowed`), `windows.py` (`activate` only), `helpers.py` / `input.py` / `ax.py`

**Problem:**
- `check_app_allowed()` runs only in `activate` / `open_app`. It does **not** run on `click_text`, `click`, `type_text`, `hotkey`, `set_field`, `ax_snapshot`, or `find`.
- If 1Password / Bitwarden / Keychain Access is already frontmost (or the agent uses coordinate clicks / AX on the focused app), the harness will control it freely.
- `check_helper_allowed()` is **never called** anywhere in the package. `_HIGH_RISK_HELPERS` (`run_shell`, `shell`, `osascript_raw`) are not real helpers — so `DH_SAFE=1` blocks nothing concrete.
- README / SECURITY.md claim “blocks password-manager-like apps” and “safe mode blocks high-risk helpers” — stronger than the implementation.

**Suggested fix:**
- On every mutating action (`click_text`, `click`, `type_text`, `hotkey`, `set_field`, `press_element` path), call `check_app_allowed(frontmost_app()["name"])` (and/or target app name).
- Either wire `check_helper_allowed` into a real gate, or remove the dead API and rewrite docs to: “safe mode is policy for agents; runtime only blocks `open_app` on sensitive name substrings.”
- Expand sensitive list (LastPass, KeePass, Dashlane, NordPass, `com.apple.keychainaccess`, etc.) and match **bundle_id** as well as display name.
- Audit **all** mutations to `~/.desktop-harness/audit.jsonl`, not only `click_text` / `activate` / `ensure_media_playing`.

---

### 2. Warm daemon: unauthenticated local RCE with Accessibility rights

**Where:** `daemon.py` — `serve()`, `client_request()`, `exec_via_daemon()`

**Problem:**
- Protocol is raw Unix-socket JSON: `{"op":"exec","code":"..."}` → `exec(compile(...), ns, ns)` with full helper namespace (mouse, keyboard, AX, screenshots).
- No auth token, no peer-credential check (`SO_PEERCRED` / `getpeereid`), no allowlist of callers.
- Socket lives under `~/Library/Caches/desktop-harness/daemon.sock`. Same-UID processes can connect; on multi-user or shared machines this is full desktop control for anything that can open the socket.
- Stale socket / race: second `daemon start` unlinks the path and binds again; no single-instance lock on the PID file beyond best-effort.

**Suggested fix (minimum for public “daemon recommended”):**
- Require a secret file (e.g. `~/.desktop-harness/daemon.token`, mode `0600`) written at start; clients send it on every request; refuse otherwise.
- Prefer `socket` mode `0o600` after bind (explicit `os.chmod`).
- On start: if PID file exists and process is alive, refuse to start; if dead, clean socket + pid.
- Document in SECURITY.md: “daemon = persistent privileged exec endpoint; treat like leaving Accessibility open to local code.”

---

### 3. Version / packaging inconsistency will confuse installers

**Where:**
- `src/desktop_harness/__init__.py` → `__version__ = "0.1.0"`
- `pyproject.toml` → `version = "0.3.0"`
- README → “v0.3 — usable, public”
- `DESIGN.md` / `HOW_IT_WORKS.md` still describe v0.1–v0.2 roadmaps that contradict shipped v0.3 (daemon vs MCP vs background control)

**Problem:** Public clone will report three different versions; roadmap docs claim features that are not the current product bar.

**Suggested fix:**
- Single source of truth: `__version__ = "0.3.0"` matching `pyproject.toml`.
- Update DESIGN / HOW_IT_WORKS “Longer path” tables so v0.3 = warm daemon + safety docs (not “MCP” or “background control” as done).

---

### 4. `desktop-harness skill` breaks outside a source checkout

**Where:** `run.py` — `cmd == "skill"`

```python
root = Path(__file__).resolve().parent.parent.parent
sys.stdout.write((root / "SKILL.md").read_text())
```

**Problem:**
- Editable install: `…/src/desktop_harness/run.py` → repo root — works.
- Wheel / `pip install` into site-packages: parent chain is **not** the repo; `SKILL.md` is not packaged (`pyproject.toml` only lists `packages = ["src/desktop_harness"]`). Command raises `FileNotFoundError`.
- Same class of bug: `helpers.REPO_ROOT = CORE_DIR.parent.parent` for `agent-workspace` — wrong under site-packages.

**Suggested fix:**
- Ship `SKILL.md` as package data (`package-data` / hatch force-include) and read via `importlib.resources`.
- Or embed a minimal skill string constant in `run.py` / `admin.py`.
- Default `DH_AGENT_WORKSPACE` to `~/.desktop-harness/agent-workspace`, not a relative guess of repo root.

---

### 5. Public docs still hard-code this machine’s private paths

**Where:**
- `install.md` — `~/Developer/grok/experiments/desktop-harness/grok-20260810` and absolute shim to that venv
- `scripts/voice_hotkey_readme.md` — same tree
- `VOICE.md` — example `cd` to private experiment path

**Problem:** Looks unprofessional and fails for every external user. README clone path is fine; `install.md` is not.

**Suggested fix:** Rewrite install to GitHub clone + `pip install -e .` + `$(pwd)/.venv/bin/desktop-harness` only. Move or clearly mark voice scripts as **experimental / optional** so the core product path stays clean.

---

## High (should fix)

### 6. `click_text` + integer `app` (pid) can crash on coordinate fallback

**Where:** `helpers.click_text` (~lines 209–212)

```python
activate(str(app) if not isinstance(app, int) else (
    find_app(app) or {}).get("name", "Finder"))
```

**Problem:** `find_app` expects a `str` and calls `.strip().lower()`. Passing a **pid (`int`)** raises `AttributeError`. PID is a valid `app` type for `ax_snapshot` / `find`.

**Suggested fix:** Resolve pid → name via `list_apps()` / `NSRunningApplication`, or skip activate when `app` is already the AX target pid and use that process’s name only when needed.

---

### 7. `find_app` substring match is first-hit, not best-hit

**Where:** `windows.find_app`

```python
if q in a["name"].lower():
    return a
```

**Problem:** Query `"Text"` can return the first regular app whose name contains “text”, not TextEdit; `"Mail"` / short prefixes are similarly fragile. Apps are sorted by active then name — still wrong.

**Suggested fix:** Prefer exact name → exact bundle_id → name startswith → substring; score and pick best. Never substring-match queries shorter than ~3–4 chars without exact/prefix.

---

### 8. `media_transport` “Play” detection is incomplete (dead branch)

**Where:** `helpers.media_transport`

```python
if low == "play" or (low.startswith("play ") and ...):
    if low == "play":
        has_play = True
```

**Problem:** Outer condition allows `"Play <track>"` but inner only sets `has_play` for exact `"play"`. State machine may report `unknown` when only row-level Play exists, or mis-handle UIs where transport is labeled differently. Postmortem helpers are only half-wired.

**Suggested fix:** Either set `has_play` for the filtered `startswith("play ")` case as a separate flag (`transport_play` vs `row_play`), or drop the outer or and document exact-only.

---

### 9. Double (or triple) AX walks on common paths

**Where:** `ax.find`, `helpers.click_text`, `ensure_media_playing`

**Problem:**
- `find()` always walks interactive tree; if no strong hit, walks full tree again (`max_nodes=450`).
- `click_text` on miss walks **again** for a sample (`ax_snapshot` max 40).
- `ensure_media_playing`: `media_transport` + `click_text` (1–2 walks) + `media_transport` again → **3–4 full AX walks** for one “press Play”.

**Suggested fix:**
- Cache last snapshot per `(pid, interactive_only, max_nodes)` for ~100–200 ms inside the daemon process.
- `click_text` should reuse nodes from `find` for the error sample.
- `ensure_media_playing` should pass nodes or do one walk with both detect + act.

---

### 10. Every CLI call pays a daemon ping even when not using daemon

**Where:** `run._want_daemon` → `daemon.is_running` → `client_request` ping, timeout **0.4s**

**Problem:** If the socket file exists but the daemon is dead/hung, each invocation waits up to 400 ms before falling through. If daemon is healthy, still a connect/ping round-trip before every script.

**Suggested fix:** Shorter timeout (50–100 ms); delete stale sock on failed connect; optional PID liveness check before connect.

---

### 11. Arbitrary `exec` is the product — document blast radius, don’t oversell “safe mode”

**Where:** `run._exec_local`, `daemon.serve` exec path, skill guidance

**Problem:** Agents can `import subprocess`, write files, or call raw Quartz without going through helpers. That is intentional for flexibility, but combined with marketing language about safe mode it is a trust bug.

**Suggested fix:** SECURITY.md one-pager: “Any code in the script runs with the host’s privileges. DH_* gates only wrap a few helpers. Use a dedicated agent profile / non-admin user for unattended runs.”

---

### 12. Capability gaps vs “agent hands for Mac” (product honesty)

These are not necessarily ship-blockers if docs set expectations, but they undercut the claim if left unstated:

| Gap | Impact | Suggested MVP add or doc |
|-----|--------|---------------------------|
| No `menu_click("File", "Save")` / menu-bar path | Agents flail on standard menus | Thin AX menu walk helper |
| No `wait_for(text/role, timeout=)` | Fixed `wait()` races | Poll `find` with timeout |
| No clipboard get/set | Common agent need | `pbcopy`/`pbpaste` or NSPasteboard |
| No window focus by title / raise specific window | Multi-window apps fail | `activate` + AX window match |
| No scroll-into-view for off-screen AX nodes | Clicks miss | AX scroll ancestor or wheel loop |
| Keyboard map incomplete for hotkeys (`.`, `/`, F-keys, etc.) | `hotkey("cmd", ".")` fails | Expand `_KEYCODES` or unicode key path |
| Overlay / Cocoa coords wrong on multi-monitor | Agent cursor lies | Document “main display only” or fix transform |
| Background control without stealing focus | HOW_IT_WORKS lists as v0.3 — **not shipped** | Align roadmap; don’t claim it |
| Electron / canvas | Documented weakness | Keep as known limit |
| Voice path half-integrated | Voice scripts need `websockets` + API key; not core CLI | Mark optional in README; don’t block core install |

---

## Medium / polish

### 13. Fixed sleeps still dominate multi-step latency

**Where:** `input.click` settle 0.04 + 0.02; `wait_stable` default 0.2; `activate` 0.12/0.35; `helpers.click_text` always `wait_stable()` after press; demo sleeps 0.35–0.4

**Suggestion:** Prefer AX “enabled / value changed” over fixed sleeps where possible; keep short HID settles; make `wait_stable` default 0.05–0.1 for daemon path.

### 14. `ax._ax_point` uses magic type ints `1` / `2`

Prefer `kAXValueCGPointType` / `kAXValueCGSizeType` constants for pyobjc portability.

### 15. `ax.walk` interactive filter logic is hard to reason about

Nearly all nodes end up `keep=True` after the nested branches; tree may still be noisier than intended. Add a unit-style fixture walk or simplify to: keep interactive roles + labeled leaves + always-descend containers.

### 16. `namespace()` / agent_helpers load once in daemon

Edits to `agent-workspace/agent_helpers.py` require daemon restart. Document or add `op: "reload"`.

### 17. `screenshot` default path is a single shared file

`TMP / "capture.png"` — concurrent agent steps clobber each other. Use unique names (`capture-{pid}-{ts}.png`) or require explicit path.

### 18. Audit log has no rotation / redaction

Long-running agents will grow `audit.jsonl` forever; values typed into `set_field` are not audited today (good for secrets) but click targets might still be sensitive. Document path + retention.

### 19. Sensitive substring `"wallet"` / `"bank"` is broad

May block Apple Wallet intentionally, but also false-positive app names. Prefer bundle IDs.

### 20. `type_text` delay 8 ms/char

Fine for short strings; long pastes should use clipboard paste (`cmd+v`) helper for speed.

### 21. Doctor AX check treats `len(nodes) >= 0` as success

Always true. Prefer `len(nodes) > 0` or trusted-only when empty is OK.

### 22. Voice / experimental surface

- `voice_tools.py` is solid enough as a schema layer but sits next to core with no CLI entry.
- `scripts/voice_session.py` dry-run still **executes** `list_apps` / `mouse_pos` / labels with `dry_run=False` for demos — surprising.

### 23. MIT LICENSE present — good

No secrets/API keys in source. `XAI_API_KEY` only via env in voice scripts — good.

### 24. Dead / unused imports

`run.py` imports `subprocess`, `time` unused; `cursor_overlay` imports `math` unused — clean before tag.

---

## What works well

1. **Clear product shape** — CLI + skill, not MCP-first. Matches how coding agents actually invoke tools today.
2. **AX-first architecture** — `ax.py` + `helpers.click_text` preferring `AXPress` over pixels is the right efficiency story; scoring improvements after the media postmortem are thoughtful.
3. **Real HID mouse** — `CGWarpMouseCursorPosition` + `CGEventPost` is honest “you can watch the cursor” control; defaults shortened for agent speed (`duration=0.08` move, `0.06` click).
4. **Warm daemon design** — Correct diagnosis (cold Python/pyobjc spawn); NDJSON protocol is simple; auto-route when daemon is up with in-process fallback is pragmatic.
5. **Doctor** — Practical permission check (AX + real capture size) better than most open-source automation tools.
6. **Media helpers + skill rules** — `media_transport` / `ensure_media_playing` + SKILL.md “one action / never spam Space” address a real production failure mode.
7. **Activate skip when already frontmost** — Good latency win in `windows.activate`.
9. **MIT + SECURITY.md + README safety section** — Baseline public hygiene is present (needs honesty upgrades above, not a greenfield rewrite).
10. **Editable install story in README** — Clone → venv → pyobjc → `pip install -e .` is reproducible for power users.

---

## Recommended release checklist

### Code / safety (before `git push` public)

- [ ] Align `__version__` with `pyproject.toml` (0.3.0)
- [ ] Gate **mutations** on frontmost/target sensitive apps; fix or remove dead `check_helper_allowed`
- [ ] Daemon: token auth + `chmod 0o600` socket + single-instance PID check; document in SECURITY.md
- [ ] Fix `click_text` pid/`find_app(int)` crash
- [ ] Harden `find_app` matching (exact > prefix > substring)
- [ ] Fix `media_transport` Play branch logic
- [ ] Package `SKILL.md` (or embed) so `desktop-harness skill` works from a wheel
- [ ] Default agent workspace under `~/.desktop-harness/`
- [ ] Optional but high value: snapshot cache in-process; unique screenshot paths

### Docs / packaging

- [ ] Rewrite `install.md` without `~/Developer/grok/experiments/...`
- [ ] Align DESIGN.md / HOW_IT_WORKS.md version tables with shipped reality (daemon = v0.3; MCP/background = future)
- [ ] README: explicit **limitations** (Electron, multi-monitor overlay, no background focus steal, no menu helper yet)
- [ ] SECURITY.md: arbitrary `exec` blast radius; daemon risk; what `DH_SAFE` actually does
- [ ] Mark voice (`VOICE.md`, `scripts/`, `voice_tools.py`) as **optional experimental** so core product review stays tight
- [ ] Confirm LICENSE year/name; no personal absolute paths in default docs

### Smoke tests (run on a clean Mac if possible)

- [ ] `pip install -e .` in fresh venv → `desktop-harness --doctor`
- [ ] `desktop-harness demo` (TextEdit + visible mouse)
- [ ] `desktop-harness skill | head` works
- [ ] `desktop-harness daemon start` → second terminal `labels()` &lt; ~150 ms
- [ ] `open_app("1Password")` refused without `DH_ALLOW_SENSITIVE=1`
- [ ] With 1Password already frontmost: `click_text` / `type_text` also refused after gate fix
- [ ] `ensure_media_playing` on a known player: noop when Pause visible
- [ ] Unauthenticated connect to daemon socket fails after token fix

### Public git hygiene

- [ ] `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, local audit logs, `.DS_Store`
- [ ] No `.env`, no API keys, no machine-local shims
- [ ] Tag `v0.3.0` only after checklist; keep experiment folder name out of user-facing install if possible

### Product messaging (honest bar)

Ship as: **“AX-first Mac control CLI for coding agents — fast path + optional warm daemon. Not background multi-agent cursors yet.”**  
That claim is supportable. “Fully safe agent hands” is not, until gates and daemon auth land.

---

## Severity summary (quick)

| # | Issue | Severity |
|---|--------|----------|
| 1 | Sensitive-app / safe-mode gates incomplete | Critical |
| 2 | Daemon unauthenticated exec | Critical |
| 3 | Version string / roadmap contradiction | Critical (release hygiene) |
| 4 | `skill` command / package data | Critical (install UX) |
| 5 | Private paths in public install docs | Critical (release hygiene) |
| 6–12 | pid crash, find_app, media, AX cost, ping, exec honesty, capability gaps | High |
| 13–24 | Sleeps, polish, voice, doctor, keycodes | Medium |

---

*End of report. Source tree left unchanged except this file.*
