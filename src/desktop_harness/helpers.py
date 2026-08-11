"""Agent-facing helpers — pre-imported into every desktop-harness script.

Efficiency order:
  1. shell / APIs (outside this package)
  2. ax_snapshot / find / click_text / set_field  (AX-first)
  3. screenshot + coordinate click               (fallback)
"""
from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path
from typing import Any

from . import ax as _ax
from . import capture as _capture
from . import input as _input
from . import windows as _windows

CORE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CORE_DIR.parent.parent
AGENT_WORKSPACE = Path(
    os.environ.get("DH_AGENT_WORKSPACE", REPO_ROOT / "agent-workspace"))


# --- re-exports ---

list_apps = _windows.list_apps
list_windows = _windows.list_windows
frontmost_app = _windows.frontmost_app
find_app = _windows.find_app
activate = _windows.activate
open_app = _windows.open_app

ax_snapshot = _ax.ax_snapshot
find = _ax.find
focused_element = _ax.focused_element

screenshot = _capture.screenshot

# Mouse — real system pointer (you can watch it move)
mouse_pos = _input.mouse_pos
move_to = _input.move_to
move_by = _input.move_by
wiggle = _input.wiggle
def click(*args, **kwargs):
    from . import safety as _safety
    _safety.check_frontmost_allowed()
    _safety.audit("click", {"args": args[:2]})
    return _input.click(*args, **kwargs)


def right_click(*args, **kwargs):
    from . import safety as _safety
    _safety.check_frontmost_allowed()
    return _input.right_click(*args, **kwargs)


def click_frame(*args, **kwargs):
    from . import safety as _safety
    _safety.check_frontmost_allowed()
    return _input.click_frame(*args, **kwargs)


def drag(*args, **kwargs):
    from . import safety as _safety
    _safety.check_frontmost_allowed()
    return _input.drag(*args, **kwargs)


def scroll(*args, **kwargs):
    from . import safety as _safety
    _safety.check_frontmost_allowed()
    return _input.scroll(*args, **kwargs)


def key(*args, **kwargs):
    from . import safety as _safety
    _safety.check_frontmost_allowed()
    _safety.audit("key", {"key": args[0] if args else None})
    return _input.key(*args, **kwargs)


def hotkey(*args, **kwargs):
    from . import safety as _safety
    _safety.check_frontmost_allowed()
    _safety.audit("hotkey", {"keys": args})
    return _input.hotkey(*args, **kwargs)


def type_text(*args, **kwargs):
    from . import safety as _safety
    _safety.check_frontmost_allowed()
    _safety.audit("type_text", {"n": len(args[0]) if args else 0})
    return _input.type_text(*args, **kwargs)


def enable_agent_cursor(enabled: bool = True):
    """Show / hide agent presence (synced halo + bottom neon bar).

    Design: ONE real system cursor + soft glow halo (never a second arrow).
    Blue while moving; brief red flash on click. DH_PRESENCE=0 to disable.
    """
    try:
        from . import presence
        if not enabled:
            presence.hide()
            _input.set_overlay(None)
            return False
        p = mouse_pos()
        ok = presence.show(p["x"], p["y"])
        if ok:
            # Overlay uses presence.move(x,y) on every warp — same coords as cursor
            _input.set_overlay(presence)
        return ok
    except Exception as e:
        print(f"agent presence unavailable: {e}")
        return False


def hide_agent_presence():
    """Hide ring + banner when a control sequence is finished.

    Call this when you know you're done — it's still the fast, immediate
    path. If a script forgets (crash, early return, the chat turn just
    ending), the warm daemon also self-clears presence after a stretch of
    no harness activity (see daemon.py's idle loop / DH_PRESENCE_IDLE_HIDE)
    so a missed call doesn't leave the overlay on screen indefinitely."""
    try:
        from . import presence
        presence.hide()
    except Exception:
        pass
    _input.set_overlay(None)


def wait(seconds: float = 0.4):
    """Pause — presence-safe: keeps the agent-presence overlay from
    sinking behind other windows during the wait, instead of a raw sleep
    that leaves it unattended. Prefer this over time.sleep() in scripts."""
    try:
        from . import presence
        presence.keep_alive(seconds)
        return
    except Exception:
        pass
    time.sleep(seconds)


def wait_stable(seconds: float = 0.2):
    """Short settle after an action (presence-safe; keep small for speed)."""
    wait(seconds)


def ensure_daemon() -> bool:
    """Return True if warm daemon is available (start is a separate CLI step)."""
    from . import daemon as d
    return d.is_running()


def button_labels(app: str | int | None = None, limit: int = 40) -> list[str]:
    """Labels of visible buttons only (handy for player/toolbars)."""
    nodes = ax_snapshot(app, max_nodes=300, interactive_only=True)
    out, seen = [], set()
    for n in nodes:
        if n.get("role") != "AXButton":
            continue
        lab = (n.get("label") or n.get("title") or "").strip()
        if not lab or lab in seen:
            continue
        seen.add(lab)
        out.append(lab)
        if len(out) >= limit:
            break
    return out


def _media_state_from_nodes(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Shared scoring logic for media_transport()/ensure_media_playing() —
    keeps both reading from one already-fetched node list instead of each
    re-walking the AX tree. Includes an internal "_play_el" (stripped by
    media_transport's public return) so ensure_media_playing can press the
    transport button it just found without a second find()/AXPress walk."""
    labs = []
    has_pause = has_transport_play = has_row_play = False
    play_el = None
    for n in nodes:
        if n.get("role") != "AXButton":
            continue
        lab = (n.get("label") or n.get("title") or "").strip()
        if not lab:
            continue
        labs.append(lab)
        low = lab.lower()
        if low == "pause" or low.startswith("pause "):
            has_pause = True
        elif low == "play":
            has_transport_play = True
            if play_el is None:
                play_el = n.get("_el")
        elif (low.startswith("play ")
              and "playlist" not in low
              and "play all" not in low
              and "playing" not in low):
            # "Play <track>" row buttons — not the main transport
            has_row_play = True
    # State is driven by transport controls only
    if has_pause and not has_transport_play:
        state = "playing"
    elif has_transport_play and not has_pause:
        state = "paused"
    elif has_pause and has_transport_play:
        # both visible rare; trust Pause
        state = "playing"
    else:
        state = "unknown"
    return {
        "state": state,
        "pause": has_pause,
        "play": has_transport_play,  # transport only (API stable)
        "transport_play": has_transport_play,
        "row_play": has_row_play,
        "labels": labs[:30],
        "_play_el": play_el,
    }


def media_transport(app: str | int | None = None) -> dict[str, Any]:
    """Inspect Play/Pause transport without clicking.

    Returns {state: 'playing'|'paused'|'unknown', pause: bool, play: bool,
             transport_play: bool, row_play: bool, labels: [...]}

    Transport Play = exact label "Play" (player bar).
    Row Play = "Play <track name>" list rows (does NOT mean paused).
    Prefer this before any media click. Never spam Space — it toggles.
    """
    nodes = ax_snapshot(app, max_nodes=400, interactive_only=True)
    status = _media_state_from_nodes(nodes)
    status.pop("_play_el", None)
    return status


def ensure_media_playing(app: str | int | None = None) -> dict[str, Any]:
    """If transport shows Pause, do nothing. If Play, press it once. Never Space.

    One AX walk to read state + locate the Play button, one more (via
    wait_stable + media_transport) to confirm the press landed — not the
    3-4 separate full-tree walks a naive read-then-click_text()-then-reread
    sequence costs, since click_text would otherwise re-walk the tree from
    scratch to relocate a button this function already just found.
    """
    from . import safety as _safety
    nodes = ax_snapshot(app, max_nodes=400, interactive_only=True, include_el=True)
    status = _media_state_from_nodes(nodes)
    play_el = status.pop("_play_el", None)
    _safety.audit("ensure_media_playing", status)
    if status["state"] == "playing":
        return {"action": "noop", **status}
    if status["state"] == "paused":
        # Same gate click_text() would apply — direct-press must not
        # bypass the sensitive-app mutation check.
        _safety.check_frontmost_allowed()
        if app:
            _safety.check_app_allowed(str(app))
        pressed = False
        hit: dict[str, Any] = {"label": "Play", "role": "AXButton"}
        if play_el is not None:
            _safety.audit("click_text", {"text": "Play", "app": app, "exact": True, "direct": True})
            pressed = _ax.press_element(play_el)
        if not pressed:
            # Element missing/stale/press failed — fall back to the normal
            # find()+click_text path (it does its own fresh walk).
            hit = click_text("Play", app=app, role="AXButton", exact=True)
        wait_stable(0.3)
        again = media_transport(app)
        return {"action": "pressed_play", "before": status, "after": again, "hit": hit}
    raise RuntimeError(
        f"cannot determine transport state; button sample: {status.get('labels')}"
    )


def click_text(
    text: str,
    app: str | int | None = None,
    *,
    role: str | None = None,
    prefer_ax_press: bool = True,
    exact: bool = False,
) -> dict[str, Any]:
    """Find best match and activate it (AXPress preferred, else click center).

    exact=True: only accept title/label equal to text (case-insensitive).
    Prefer role=\"AXButton\" for toolbar/player controls.
    """
    from . import safety as _safety
    _safety.check_frontmost_allowed()
    if app:
        _safety.check_app_allowed(str(app))
    _safety.audit("click_text", {"text": text, "app": app, "exact": exact})
    hits = _ax.find(text, app=app, role=role, max_results=12)
    if exact:
        q = text.strip().lower()
        hits = [
            h for h in hits
            if (h.get("title") or "").strip().lower() == q
            or (h.get("label") or "").strip().lower() == q
        ]
    if not hits:
        # show what's visible to help the agent
        sample = _ax.public_nodes(
            _ax.ax_snapshot(app, max_nodes=40, interactive_only=True, include_el=True))
        labels = [n.get("label") or n.get("title") or n.get("role") for n in sample[:25]]
        raise RuntimeError(
            f"no AX match for {text!r} (role={role!r}, exact={exact}). visible sample: {labels}")
    hit = hits[0]
    el = hit.get("_el")
    if prefer_ax_press and el is not None:
        if _ax.press_element(el):
            wait_stable()
            return {k: v for k, v in hit.items() if not k.startswith("_")}
    frame = hit.get("frame")
    if not frame:
        raise RuntimeError(f"matched {text!r} but no frame and AXPress failed: {hit}")
    # ensure app frontmost for coordinate click
    if app is not None:
        try:
            if isinstance(app, int):
                # pid → resolve name, then activate
                from AppKit import NSRunningApplication
                ra = NSRunningApplication.runningApplicationWithProcessIdentifier_(app)
                name = (ra.localizedName() if ra else None) or "Finder"
                activate(name)
            else:
                activate(str(app))
        except Exception:
            pass
    click_frame(frame)
    wait_stable()
    return {k: v for k, v in hit.items() if not k.startswith("_")}


def set_field(text: str, value: str, app: str | int | None = None) -> dict[str, Any]:
    """Find a text field by nearby label/title and set its value."""
    hits = _ax.find(text, app=app, max_results=10)
    # prefer text fields
    ordered = sorted(
        hits,
        key=lambda h: (0 if "Text" in (h.get("role") or "") else 1, -h.get("score", 0)),
    )
    if not ordered:
        raise RuntimeError(f"no field matching {text!r}")
    hit = ordered[0]
    el = hit.get("_el")
    if el is not None and _ax.set_value(el, value):
        wait_stable()
        return {k: v for k, v in hit.items() if not k.startswith("_")}
    # fallback: click + type
    if hit.get("frame"):
        click_frame(hit["frame"])
        wait(0.15)
        hotkey("cmd", "a")
        type_text(value)
        wait_stable()
        return {k: v for k, v in hit.items() if not k.startswith("_")}
    raise RuntimeError(f"could not set field {text!r}")


def labels(app: str | int | None = None, limit: int = 40) -> list[str]:
    """Quick list of visible labels for debugging."""
    nodes = ax_snapshot(app, max_nodes=limit * 3, interactive_only=True)
    out = []
    seen = set()
    for n in nodes:
        lab = (n.get("label") or "").strip()
        if not lab or lab in seen:
            continue
        seen.add(lab)
        out.append(f"{n.get('role','')}: {lab}")
        if len(out) >= limit:
            break
    return out


def screen_info(app: str | None = None) -> dict[str, Any]:
    front = frontmost_app()
    wins = list_windows()
    if app:
        wins = [w for w in wins if app.lower() in w["app"].lower()]
    return {
        "frontmost": front,
        "windows": wins[:12],
        "window_count": len(wins),
    }


def verify(note: str = "", app: str | int | None = None) -> dict[str, Any]:
    """Screenshot + AX read to close the loop on an action whose failure
    would otherwise be silent — NOT a routine step after every click.

    click_text/set_field already raise if there's no AX match; that's the
    check for ordinary UI changes. Reach for this specifically for actions
    that can succeed at the AX layer while doing the wrong thing with no
    other way to notice — media transport toggles, anything gated under
    the Consent section, a step you're about to report as finished where
    being wrong matters. Calling it after everything reintroduces the
    vision-loop tax the rest of this module exists to avoid. When you do
    call it, Read the screenshot path it returns before deciding the step
    succeeded — the point is looking, not just calling the function.

    `note` is free text describing what you expected to happen — it goes
    into the audit log next to the actual state, so a later pass (by you
    or another agent) can compare intent vs. outcome without re-deriving
    context.
    """
    result: dict[str, Any] = {"note": note}
    try:
        result["frontmost"] = frontmost_app()
    except Exception as e:
        result["frontmost_error"] = str(e)
    try:
        result["labels"] = labels(app, limit=25)
    except Exception as e:
        result["labels_error"] = str(e)
    try:
        result["screenshot"] = screenshot(app=app if isinstance(app, str) else None)
    except Exception as e:
        result["screenshot_error"] = str(e)
    try:
        from . import safety as _safety
        _safety.audit("verify", {"note": note, "app": app,
                                  "frontmost": result.get("frontmost")})
    except Exception:
        pass
    return result


def _load_agent_helpers():
    p = AGENT_WORKSPACE / "agent_helpers.py"
    if not p.exists():
        return {}
    spec = importlib.util.spec_from_file_location("desktop_harness_agent_helpers", p)
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {k: getattr(mod, k) for k in dir(mod) if not k.startswith("_")}


def namespace() -> dict[str, Any]:
    """Globals injected into scripts."""
    ns = {k: v for k, v in globals().items() if not k.startswith("_")}
    ns.update(_load_agent_helpers())
    return ns
