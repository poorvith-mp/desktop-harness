"""Stage browser (optional) + live action monitor (any app).

The monitor is a click-through picture of whatever the agent is driving —
Settings, Notes, Chrome, anything. It is not Chrome-only.

Stage is only for *web* tasks: a dedicated small Chrome window so we do
not hijack the user's everyday tabs or go fullscreen over Grok.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import Quartz
from AppKit import (
    NSBitmapImageRep,
    NSColor,
    NSFont,
    NSImage,
    NSImageView,
    NSMakeRect,
    NSPanel,
    NSScreen,
    NSTextField,
    NSView,
    NSWindowStyleMaskBorderless,
    NSLeftTextAlignment,
    NSFloatingWindowLevel,
)

from . import capture as _capture
from . import presence as _presence
from . import windows as _windows

STAGE_TITLE = "DH Stage"
STAGE_W, STAGE_H = 960.0, 700.0
MONITOR_W, MONITOR_H = 480.0, 300.0
_MIN_REFRESH = 0.18  # ~5 fps cap

_stage: dict[str, Any] | None = None
_monitor: NSPanel | None = None
_image_view: Any = None
_caption: Any = None
_title_field: Any = None
_chrome_bar: Any = None
_follow_app: str | None = None
_follow_wid: int | None = None
_note = ""
_last_refresh = 0.0


def _chrome_available() -> bool:
    return _windows.find_app("Google Chrome") is not None or os.path.isdir(
        "/Applications/Google Chrome.app"
    )


def _visible_frame():
    screen = NSScreen.mainScreen()
    if screen is None:
        return None
    return screen.visibleFrame()


def _place_stage_rect() -> tuple[float, float, float, float]:
    vf = _visible_frame()
    if vf is None:
        return 400.0, 80.0, STAGE_W, STAGE_H
    # Cocoa: origin bottom-left. Park on the right, leave room for Ghostty.
    w = min(STAGE_W, max(640.0, float(vf.size.width) * 0.48))
    h = min(STAGE_H, max(480.0, float(vf.size.height) * 0.72))
    x = float(vf.origin.x) + float(vf.size.width) - w - 16.0
    y = float(vf.origin.y) + (float(vf.size.height) - h) / 2.0
    return x, y, w, h


def _find_stage_window() -> dict[str, Any] | None:
    for w in _windows.list_windows():
        title = (w.get("title") or "")
        app = (w.get("app") or "")
        if STAGE_TITLE.lower() in title.lower() and "chrome" in app.lower():
            return w
        if _stage and w.get("id") == _stage.get("window_id"):
            return w
    return None


def stage_frame() -> dict[str, Any]:
    """Bounds of the Stage Chrome window only — never the user's other tabs."""
    w = _find_stage_window()
    if not w:
        raise RuntimeError("no DH Stage window — call open_stage() first")
    return {
        "id": w["id"],
        "app": w["app"],
        "pid": w.get("pid"),
        "title": w.get("title"),
        "x": float(w["x"]),
        "y": float(w["y"]),
        "w": float(w["w"]),
        "h": float(w["h"]),
    }


def open_stage(url: str | None = None) -> dict[str, Any]:
    """Open or focus a dedicated small Chrome window for web tasks.

    Does not hijack existing Chrome tabs. Does not fullscreen.
    """
    global _stage
    if not _chrome_available():
        raise RuntimeError(
            "Google Chrome is not installed. Stage browser needs Chrome; "
            "do not silently fall back to Safari/fullscreen."
        )
    existing = _find_stage_window()
    target = (url or "https://example.com").strip()
    if existing is None:
        # New window only — never reuse the user's current tab.
        cmd = [
            "open", "-na", "Google Chrome",
            "--args", "--new-window", target,
        ]
        subprocess.run(cmd, check=False, capture_output=True)
        deadline = time.time() + 6.0
        while time.time() < deadline:
            time.sleep(0.2)
            _windows._refresh_workspace()
            # Title may still be the page title; pick newest Chrome window
            chromes = [w for w in _windows.list_windows() if "chrome" in (w.get("app") or "").lower()]
            if chromes:
                # Prefer a window that just appeared (not already tracked)
                existing = max(chromes, key=lambda w: w.get("id") or 0)
                break
        if existing is None:
            raise RuntimeError("Chrome launched but no window appeared for DH Stage")
    _stage = {
        "app": existing["app"],
        "window_id": int(existing["id"]),
        "url": target,
        "title": existing.get("title") or STAGE_TITLE,
    }
    follow(existing["app"], window_id=int(existing["id"]))
    _position_chrome_window(int(existing["id"]))
    show_monitor()
    stage_note(f"stage {target}")
    refresh_monitor(force=True)
    return {**_stage, "frame": {k: existing[k] for k in ("x", "y", "w", "h")}}


def _position_chrome_window(window_id: int) -> None:
    """Best-effort place/size via AppleScript — never fail the open if this misses."""
    x, y, w, h = _place_stage_rect()
    # Chrome AppleScript uses screen coords with origin top-left on some builds;
    # bounds are {left, top, right, bottom} in global pixels (CG).
    vf = _visible_frame()
    if vf is None:
        return
    # Convert Cocoa y (bottom-left) → CG top for Chrome bounds
    screen_h = float(NSScreen.mainScreen().frame().size.height)
    top = screen_h - (y + h)
    left = x
    right = x + w
    bottom = top + h
    script = (
        f'tell application "Google Chrome"\n'
        f'  set index of window 1 to 1\n'
        f'  try\n'
        f'    set bounds of window 1 to {{{int(left)}, {int(top)}, {int(right)}, {int(bottom)}}}\n'
        f'  end try\n'
        f'end tell'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False, capture_output=True, timeout=3,
        )
    except Exception:
        pass


def close_stage() -> dict[str, Any]:
    """Close only the Stage window. Never quit Chrome."""
    global _stage
    info = {"closed": False}
    w = _find_stage_window()
    if w:
        try:
            _windows.activate("Google Chrome", wait=0.2)
            time.sleep(0.1)
            from . import input as _input
            from . import safety as _safety
            _safety.check_frontmost_allowed()
            _input.hotkey("cmd", "w")
            info["closed"] = True
        except Exception as e:
            info["error"] = str(e)
    _stage = None
    hide_monitor()
    return info


def follow(app: str | None = None, window_id: int | None = None) -> dict[str, Any]:
    """Point the live monitor at an app/window (Settings, Notes, Chrome, …)."""
    global _follow_app, _follow_wid
    if window_id is not None:
        _follow_wid = int(window_id)
        for w in _windows.list_windows():
            if w.get("id") == _follow_wid:
                _follow_app = w.get("app")
                break
    elif app:
        _follow_app = str(app)
        try:
            fr = _windows.window_frame(app)
            _follow_wid = int(fr.get("id") or 0) or None
        except Exception:
            _follow_wid = None
    else:
        front = _windows.frontmost_app()
        _follow_app = (front or {}).get("name")
        try:
            fr = _windows.window_frame(_follow_app)
            _follow_wid = int(fr.get("id") or 0) or None
        except Exception:
            _follow_wid = None
    return {"app": _follow_app, "window_id": _follow_wid}


def stage_note(text: str) -> str:
    global _note
    _note = (text or "").strip()[:80]
    _apply_caption()
    return _note


def _apply_caption() -> None:
    if _caption is None:
        return
    who = _follow_app or "desktop"
    line = _note or "watching"
    try:
        _caption.setStringValue_(line)
        if _title_field is not None:
            _title_field.setStringValue_(who)
    except Exception:
        pass


def _monitor_layout() -> tuple[float, float, float, float]:
    vf = _visible_frame()
    bar = 28.0
    if vf is None:
        return 900.0, 700.0, MONITOR_W, MONITOR_H + bar
    # Top-right of visible frame (Cocoa y-up)
    x = float(vf.origin.x) + float(vf.size.width) - MONITOR_W - 16.0
    y = float(vf.origin.y) + float(vf.size.height) - (MONITOR_H + bar) - 16.0
    return x, y, MONITOR_W, MONITOR_H + bar


def show_monitor() -> bool:
    """Click-through live picture of the followed window. Never becomes key."""
    global _monitor, _image_view, _caption, _title_field, _chrome_bar
    _presence._ensure_app()
    if _monitor is not None:
        refresh_monitor(force=True)
        return True
    x, y, pw, ph = _monitor_layout()
    bar = 28.0
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(x, y, pw, ph),
        NSWindowStyleMaskBorderless,
        2,
        False,
    )
    try:
        panel.setLevel_(int(NSFloatingWindowLevel) + 2)
    except Exception:
        panel.setLevel_(80)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setIgnoresMouseEvents_(True)
    panel.setHasShadow_(True)
    try:
        panel.setHidesOnDeactivate_(False)
        panel.setBecomesKeyOnlyIfNeeded_(True)
    except Exception:
        pass
    try:
        # CanJoinAllSpaces | Transient | FullScreenAuxiliary
        panel.setCollectionBehavior_(1 << 0 | 1 << 7 | 1 << 8)
    except Exception:
        pass

    root = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw, ph))
    root.setWantsLayer_(True)

    chrome = NSView.alloc().initWithFrame_(NSMakeRect(0, ph - bar, pw, bar))
    chrome.setWantsLayer_(True)
    if chrome.layer() is not None:
        chrome.layer().setBackgroundColor_(
            Quartz.CGColorCreateGenericRGB(0.07, 0.08, 0.10, 0.92)
        )
    title = NSTextField.alloc().initWithFrame_(NSMakeRect(10, 6, 88, 16))
    title.setBezeled_(False)
    title.setDrawsBackground_(False)
    title.setEditable_(False)
    title.setSelectable_(False)
    title.setStringValue_("Live")
    try:
        title.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(0.95, 0.95))
        title.setFont_(NSFont.systemFontOfSize_weight_(11.0, 0.4))
    except Exception:
        pass
    cap = NSTextField.alloc().initWithFrame_(NSMakeRect(100, 6, pw - 112, 16))
    cap.setBezeled_(False)
    cap.setDrawsBackground_(False)
    cap.setEditable_(False)
    cap.setSelectable_(False)
    cap.setAlignment_(NSLeftTextAlignment)
    try:
        cap.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(0.75, 0.95))
        cap.setFont_(NSFont.systemFontOfSize_(11.0))
    except Exception:
        pass
    chrome.addSubview_(title)
    chrome.addSubview_(cap)

    img = NSImageView.alloc().initWithFrame_(NSMakeRect(0, 0, MONITOR_W, MONITOR_H))
    try:
        # AxesIndependently (1) stretches. Use proportionally-down so
        # Notes/Settings text stays readable, letterboxed if needed.
        img.setImageScaling_(3)  # NSImageScaleProportionallyUpOrDown — keep aspect
    except Exception:
        pass
    try:
        img.setImageAlignment_(5)  # NSImageAlignCenter
    except Exception:
        pass

    root.addSubview_(img)
    root.addSubview_(chrome)
    panel.setContentView_(root)
    panel.orderFrontRegardless()
    _monitor = panel
    _image_view = img
    _caption = cap
    _title_field = title
    _chrome_bar = chrome
    _apply_caption()
    _presence._pump(n=4, seconds=0.02)
    refresh_monitor(force=True)
    return True


def hide_monitor() -> None:
    global _monitor, _image_view, _caption, _title_field, _chrome_bar
    try:
        if _monitor is not None:
            _monitor.setIgnoresMouseEvents_(True)
            _monitor.orderOut_(None)
            try:
                _monitor.setFrame_display_(NSMakeRect(-4000, -4000, 10, 10), False)
            except Exception:
                pass
            _monitor.setReleasedWhenClosed_(True)
            _monitor.close()
    except Exception:
        pass
    try:
        from AppKit import NSApp
        app = NSApp()
        if app is not None:
            for win in list(app.windows() or []):
                try:
                    if win is _presence._halo or win is _presence._banner:
                        continue
                    win.orderOut_(None)
                    try:
                        win.setFrame_display_(NSMakeRect(-4000, -4000, 10, 10), False)
                    except Exception:
                        pass
                    win.close()
                except Exception:
                    pass
    except Exception:
        pass
    _presence._pump(n=6, seconds=0.03)
    _monitor = None
    _image_view = None
    _caption = None
    _title_field = None
    _chrome_bar = None


def monitor_active() -> bool:
    return _monitor is not None


def _fit_monitor_to_image(nsimg) -> None:
    """Resize the panel so the capture keeps its aspect ratio (no stretch)."""
    global _image_view
    if _monitor is None or nsimg is None:
        return
    try:
        sz = nsimg.size()
        iw, ih = float(sz.width), float(sz.height)
    except Exception:
        return
    if iw < 8 or ih < 8:
        return
    bar = 28.0
    max_w, max_h = 520.0, 340.0
    scale = min(max_w / iw, max_h / ih, 1.0)
    vw, vh = max(240.0, iw * scale), max(160.0, ih * scale)
    x, y, _, _ = _monitor_layout()
    # keep top-right anchored
    vf = _visible_frame()
    if vf is not None:
        x = float(vf.origin.x) + float(vf.size.width) - vw - 16.0
        y = float(vf.origin.y) + float(vf.size.height) - (vh + bar) - 16.0
    try:
        _monitor.setFrame_display_(NSMakeRect(x, y, vw, vh + bar), False)
        if _image_view is not None:
            _image_view.setFrame_(NSMakeRect(0, 0, vw, vh))
        if _chrome_bar is not None:
            _chrome_bar.setFrame_(NSMakeRect(0, vh, vw, bar))
        if _title_field is not None:
            _title_field.setFrame_(NSMakeRect(10, 6, 88, 16))
        if _caption is not None:
            _caption.setFrame_(NSMakeRect(100, 6, max(80.0, vw - 112), 16))
    except Exception:
        pass


def _nsimage_from_window(window_id: int):
    image = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        int(window_id),
        Quartz.kCGWindowImageBoundsIgnoreFraming
        | Quartz.kCGWindowImageNominalResolution,
    )
    if image is None:
        return None
    rep = NSBitmapImageRep.alloc().initWithCGImage_(image)
    nsimg = NSImage.alloc().initWithSize_(rep.size())
    nsimg.addRepresentation_(rep)
    return nsimg


def refresh_monitor(*, force: bool = False) -> bool:
    """Redraw the monitor from the followed window. Main thread only."""
    global _last_refresh
    if _monitor is None or _image_view is None:
        return False
    now = time.monotonic()
    if not force and (now - _last_refresh) < _MIN_REFRESH:
        return False
    wid = _follow_wid
    if wid is None and _follow_app:
        try:
            fr = _windows.window_frame(_follow_app)
            wid = int(fr.get("id") or 0) or None
        except Exception:
            wid = None
    if not wid:
        _apply_caption()
        return False
    nsimg = _nsimage_from_window(wid)
    if nsimg is None:
        return False
    try:
        _fit_monitor_to_image(nsimg)
        _image_view.setImage_(nsimg)
        _monitor.orderFrontRegardless()
        _apply_caption()
        _presence._pump(n=2, seconds=0.004)
    except Exception:
        return False
    _last_refresh = now
    return True


def tick() -> None:
    """Called from presence.keep_alive / after actions."""
    if _monitor is not None:
        refresh_monitor(force=False)
