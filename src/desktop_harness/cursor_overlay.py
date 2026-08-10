"""Optional floating agent-cursor ring for visual transparency.

Shows a bright circle where the agent is pointing. Clicks pass through.
Requires AppKit main-thread affinity; works in short CLI processes.
"""
from __future__ import annotations

import math
from typing import Any

_panel = None
_app = None
_SIZE = 28.0


def _ensure_app():
    global _app
    if _app is not None:
        return _app
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    _app = NSApplication.sharedApplication()
    try:
        _app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass
    return _app


def _make_panel():
    global _panel
    from AppKit import (
        NSColor, NSMakeRect, NSPanel, NSView, NSWindowStyleMaskBorderless,
        NSFloatingWindowLevel, NSColorSpace,
    )
    from Quartz import CGColorCreateGenericRGB

    _ensure_app()
    size = _SIZE
    style = NSWindowStyleMaskBorderless
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, size, size),
        style,
        2,  # NSBackingStoreBuffered
        False,
    )
    panel.setLevel_(NSFloatingWindowLevel + 1)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setIgnoresMouseEvents_(True)
    panel.setCollectionBehavior_(1 << 0 | 1 << 3)  # can join all spaces + stationary-ish
    panel.setHasShadow_(True)

    # Simple filled circle via content view background — draw with layer
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, size, size))
    view.setWantsLayer_(True)
    layer = view.layer()
    if layer is not None:
        layer.setCornerRadius_(size / 2)
        # #3b82f6 @ ~0.85 alpha
        layer.setBackgroundColor_(CGColorCreateGenericRGB(0.231, 0.510, 0.965, 0.85))
        layer.setBorderWidth_(2.0)
        layer.setBorderColor_(CGColorCreateGenericRGB(1, 1, 1, 0.9))
    panel.setContentView_(view)
    panel.orderFrontRegardless()
    _panel = panel
    return panel


def _screen_to_cocoa(x: float, y: float) -> tuple[float, float]:
    """CG global (top-left origin) → Cocoa bottom-left origin for main layout."""
    from AppKit import NSScreen
    # Quartz mouse uses top-left of main display region in global coords.
    # NSWindow frame origin is bottom-left of screen.
    screen = NSScreen.mainScreen()
    if screen is None:
        return x - _SIZE / 2, y - _SIZE / 2
    frame = screen.frame()
    # For multi-monitor this is imperfect; good enough for main display demos.
    h = frame.size.height
    # CGEvent y increases downward from top of primary; Cocoa y increases upward
    cocoa_y = h - y - _SIZE / 2
    cocoa_x = x - _SIZE / 2
    # offset by screen origin for multi-monitor primary at (0,0) usually fine
    cocoa_x += frame.origin.x
    cocoa_y += frame.origin.y
    return cocoa_x, cocoa_y


def show(x: float | None = None, y: float | None = None, color: Any = None) -> None:
    """Show the agent cursor at (x,y) or current mouse position."""
    import Quartz
    if x is None or y is None:
        ev = Quartz.CGEventCreate(None)
        p = Quartz.CGEventGetLocation(ev)
        x = float(p.x) if x is None else x
        y = float(p.y) if y is None else y
    panel = _panel or _make_panel()
    cx, cy = _screen_to_cocoa(float(x), float(y))
    panel.setFrameOrigin_((cx, cy))
    panel.orderFrontRegardless()
    _pump()


def move(x: float, y: float) -> None:
    if _panel is None:
        show(x, y)
        return
    cx, cy = _screen_to_cocoa(float(x), float(y))
    _panel.setFrameOrigin_((cx, cy))
    _pump()


def hide() -> None:
    global _panel
    if _panel is not None:
        _panel.orderOut_(None)
        _panel = None
    _pump()


def pulse() -> None:
    """Brief size flash — best-effort."""
    if _panel is None:
        return
    try:
        view = _panel.contentView()
        layer = view.layer() if view else None
        if layer is not None:
            layer.setOpacity_(1.0)
    except Exception:
        pass
    _pump()


def _pump():
    """Process a few AppKit events so the window paints in CLI scripts."""
    try:
        from AppKit import NSApp, NSDate, NSDefaultRunLoopMode
        app = _ensure_app()
        # spin briefly
        for _ in range(3):
            ev = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                2**64 - 1,  # NSEventMaskAny roughly
                NSDate.dateWithTimeIntervalSinceNow_(0.001),
                NSDefaultRunLoopMode,
                True,
            )
            if ev is not None:
                app.sendEvent_(ev)
    except Exception:
        pass
