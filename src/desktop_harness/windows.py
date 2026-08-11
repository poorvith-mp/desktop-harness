"""Window and app discovery via CGWindowList + NSWorkspace."""
from __future__ import annotations

import time
from typing import Any

import Quartz
from AppKit import NSRunningApplication, NSWorkspace
from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode


def _refresh_workspace() -> None:
    """Deliver pending NSWorkspace notifications before reading its caches.

    `runningApplications()` and `frontmostApplication()` are caches that only
    update when the host process pumps a run loop. Neither the CLI nor the warm
    daemon ever does, so both stay frozen at process start: apps launched later
    are invisible (so `activate()` times out on every cold launch) and apps that
    have quit linger indefinitely. A zero timeout drains what is already pending
    without blocking.
    """
    CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.0, True)


def list_apps() -> list[dict[str, Any]]:
    """Running apps with a regular activation policy (skip agents/UI helpers)."""
    _refresh_workspace()
    out = []
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        # 0 = regular, 1 = accessory, 2 = prohibited
        if app.activationPolicy() != 0:
            continue
        out.append({
            "name": app.localizedName() or "",
            "bundle_id": app.bundleIdentifier() or "",
            "pid": int(app.processIdentifier()),
            "active": bool(app.isActive()),
            "hidden": bool(app.isHidden()),
        })
    out.sort(key=lambda a: (not a["active"], a["name"].lower()))
    return out


def list_windows(on_screen_only: bool = True) -> list[dict[str, Any]]:
    """On-screen windows with bounds (global screen points)."""
    opts = Quartz.kCGWindowListOptionOnScreenOnly if on_screen_only else 0
    raw = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []
    out = []
    for w in raw:
        layer = w.get("kCGWindowLayer", 0)
        if layer != 0:
            continue
        b = w.get("kCGWindowBounds") or {}
        width = float(b.get("Width", 0))
        height = float(b.get("Height", 0))
        if width < 50 or height < 50:
            continue
        out.append({
            "id": int(w.get("kCGWindowNumber", 0)),
            "app": w.get("kCGWindowOwnerName") or "",
            "pid": int(w.get("kCGWindowOwnerPID", 0)),
            "title": w.get("kCGWindowName") or "",
            "x": float(b.get("X", 0)),
            "y": float(b.get("Y", 0)),
            "w": width,
            "h": height,
        })
    return out


def frontmost_app() -> dict[str, Any] | None:
    _refresh_workspace()
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if not app:
        return None
    return {
        "name": app.localizedName() or "",
        "bundle_id": app.bundleIdentifier() or "",
        "pid": int(app.processIdentifier()),
        "active": True,
        "hidden": bool(app.isHidden()),
    }


def find_app(name_or_bundle: str | int) -> dict[str, Any] | None:
    """Match by localized name, bundle id, or pid.

    Resolution order:
      1. exact name or exact bundle id
      2. name startswith query
      3. best substring (shortest name wins — avoids "Text" → wrong app)
      4. bundle id via NSRunningApplication
    """
    # pid path
    if isinstance(name_or_bundle, int):
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
            name_or_bundle)
        if not app:
            return None
        return {
            "name": app.localizedName() or "",
            "bundle_id": app.bundleIdentifier() or "",
            "pid": int(app.processIdentifier()),
            "active": bool(app.isActive()),
            "hidden": bool(app.isHidden()),
        }

    q = (name_or_bundle or "").strip().lower()
    if not q:
        return None

    apps = list_apps()
    # 1) exact
    for a in apps:
        if a["name"].lower() == q or a["bundle_id"].lower() == q:
            return a
    # 2) startswith name
    starts = [a for a in apps if a["name"].lower().startswith(q)]
    if len(starts) == 1:
        return starts[0]
    if len(starts) > 1:
        starts.sort(key=lambda a: len(a["name"]))
        return starts[0]
    # 3) substring — prefer shortest name containing q (most specific)
    subs = [a for a in apps if q in a["name"].lower() or q in a["bundle_id"].lower()]
    if subs:
        subs.sort(key=lambda a: (len(a["name"]), a["name"].lower()))
        return subs[0]
    # 4) bundle id launch lookup
    ns_apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
        name_or_bundle)
    if ns_apps:
        app = ns_apps[0]
        return {
            "name": app.localizedName() or "",
            "bundle_id": app.bundleIdentifier() or "",
            "pid": int(app.processIdentifier()),
            "active": bool(app.isActive()),
            "hidden": bool(app.isHidden()),
        }
    return None


def activate(name_or_bundle: str, wait: float | None = None) -> dict[str, Any]:
    """Bring app to front. Launches via `open -a` / NSWorkspace if needed.

    wait: seconds after activate. Default 0.12 if already running, 0.35 if cold launch.
    """
    import subprocess
    from . import safety as _safety

    _safety.check_app_allowed(name_or_bundle)
    app_info = find_app(name_or_bundle)
    cold = app_info is None
    if app_info is None:
        # `open -a` resolves system apps more reliably than launchApplication_
        r = subprocess.run(
            ["open", "-a", name_or_bundle],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            ok = NSWorkspace.sharedWorkspace().launchApplication_(name_or_bundle)
            if not ok:
                err = (r.stderr or r.stdout or "").strip()
                raise RuntimeError(
                    f"app not found / could not launch: {name_or_bundle!r} ({err})")
        # poll until it appears in the running list (tighter than before)
        deadline = time.time() + 4.0
        while time.time() < deadline:
            time.sleep(0.08)
            app_info = find_app(name_or_bundle)
            if app_info:
                break
        if app_info is None:
            raise RuntimeError(f"launched but could not resolve app: {name_or_bundle!r}")
    # already frontmost → skip activate + sleep
    if app_info.get("active") and not cold:
        _safety.audit("activate_skip", {"name": name_or_bundle, "reason": "already_frontmost"})
        return app_info
    apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
        app_info["bundle_id"]) if app_info["bundle_id"] else []
    if apps:
        apps[0].activateWithOptions_(1 << 1)  # ignoring other apps
    else:
        # fallback: activate by PID
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
            app_info["pid"])
        if app:
            app.activateWithOptions_(1 << 1)
    # Confirm activation by polling the real signal (frontmost app switched)
    # instead of blind-sleeping the whole budget first. activateWithOptions_
    # is async and often lands in a few ms; a flat pre-sleep paid the full
    # 120-350ms on every call regardless. Poll immediately, cap the total
    # wait at the old budget so behavior on a slow/contested activation
    # (another app stealing focus) is unchanged.
    budget = (0.35 if cold else 0.12) if wait is None else wait
    deadline = time.time() + max(budget, 1.2)
    poll = 0.02
    while time.time() < deadline:
        cur = find_app(name_or_bundle)
        if cur and cur.get("active"):
            _safety.audit("activate", {"name": name_or_bundle, "cold": cold})
            return cur
        if apps:
            apps[0].activateWithOptions_(1 << 1)
        time.sleep(poll)
    _safety.audit("activate", {"name": name_or_bundle, "cold": cold, "warn": "focus_uncertain"})
    return find_app(name_or_bundle) or app_info


def open_app(name: str) -> dict[str, Any]:
    """Alias for activate — open or focus an app by name."""
    return activate(name)
