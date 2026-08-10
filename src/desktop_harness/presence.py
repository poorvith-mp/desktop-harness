"""Subtle visual presence while the agent drives the Mac.

Goals:
  - Clear that something automated is moving the pointer
  - Minimal / quiet (no gaudy animation)
  - Click-through so it never blocks real UI
  - Optional: DH_PRESENCE=0 to disable

Pieces:
  1. Soft ring that follows the pointer
  2. Brief flash on click
  3. Small top pill: "Agent active — hands off"
"""
from __future__ import annotations

import os
import time
from typing import Any

_ring = None
_banner = None
_app = None
_active = False
_RING = 22.0
_FLASH = 34.0


def enabled() -> bool:
    v = os.environ.get("DH_PRESENCE", "1").lower()
    return v not in ("0", "false", "no", "off")


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


def _pump(n: int = 2):
    try:
        from AppKit import NSDate, NSDefaultRunLoopMode
        app = _ensure_app()
        for _ in range(n):
            ev = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                (1 << 64) - 1,
                NSDate.dateWithTimeIntervalSinceNow_(0.0005),
                NSDefaultRunLoopMode,
                True,
            )
            if ev is not None:
                app.sendEvent_(ev)
    except Exception:
        pass


def _screen_to_cocoa(x: float, y: float, size: float) -> tuple[float, float]:
    from AppKit import NSScreen
    screen = NSScreen.mainScreen()
    if screen is None:
        return x - size / 2, y - size / 2
    frame = screen.frame()
    h = frame.size.height
    cocoa_y = h - y - size / 2 + frame.origin.y
    cocoa_x = x - size / 2 + frame.origin.x
    return cocoa_x, cocoa_y


def _make_ring():
    global _ring
    from AppKit import (
        NSColor, NSMakeRect, NSPanel, NSView, NSWindowStyleMaskBorderless,
        NSFloatingWindowLevel,
    )
    from Quartz import CGColorCreateGenericRGB

    _ensure_app()
    size = _RING
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, size, size),
        NSWindowStyleMaskBorderless,
        2,
        False,
    )
    panel.setLevel_(NSFloatingWindowLevel + 2)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setIgnoresMouseEvents_(True)
    panel.setHasShadow_(False)
    # stay on all spaces, transient
    panel.setCollectionBehavior_(1 << 0 | 1 << 3)

    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, size, size))
    view.setWantsLayer_(True)
    layer = view.layer()
    if layer is not None:
        layer.setCornerRadius_(size / 2)
        # soft blue ring — mostly transparent fill, clear edge
        layer.setBackgroundColor_(CGColorCreateGenericRGB(0.25, 0.45, 0.95, 0.28))
        layer.setBorderWidth_(1.5)
        layer.setBorderColor_(CGColorCreateGenericRGB(1, 1, 1, 0.75))
    panel.setContentView_(view)
    _ring = panel
    return panel


def _make_banner():
    global _banner
    from AppKit import (
        NSColor, NSMakeRect, NSPanel, NSTextField, NSFont,
        NSWindowStyleMaskBorderless, NSFloatingWindowLevel,
        NSCenterTextAlignment,
    )
    from Quartz import CGColorCreateGenericRGB

    _ensure_app()
    w, h = 220.0, 28.0
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, w, h),
        NSWindowStyleMaskBorderless,
        2,
        False,
    )
    panel.setLevel_(NSFloatingWindowLevel + 3)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setIgnoresMouseEvents_(True)
    panel.setHasShadow_(True)
    panel.setCollectionBehavior_(1 << 0 | 1 << 3)

    # rounded dark pill via layer
    from AppKit import NSView
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    view.setWantsLayer_(True)
    layer = view.layer()
    if layer is not None:
        layer.setCornerRadius_(h / 2)
        layer.setBackgroundColor_(CGColorCreateGenericRGB(0.08, 0.08, 0.10, 0.82))
        layer.setBorderWidth_(0.5)
        layer.setBorderColor_(CGColorCreateGenericRGB(1, 1, 1, 0.12))

    label = NSTextField.alloc().initWithFrame_(NSMakeRect(8, 4, w - 16, h - 8))
    label.setStringValue_("●  Agent active — hands off")
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setAlignment_(NSCenterTextAlignment)
    try:
        label.setTextColor_(NSColor.whiteColor())
        label.setFont_(NSFont.systemFontOfSize_weight_(11.5, 0.3))
    except Exception:
        pass
    view.addSubview_(label)
    panel.setContentView_(view)

    # place top-center of main screen
    from AppKit import NSScreen
    screen = NSScreen.mainScreen()
    if screen is not None:
        sf = screen.frame()
        # Cocoa: origin bottom-left; top means high y
        x = sf.origin.x + (sf.size.width - w) / 2
        y = sf.origin.y + sf.size.height - h - 14
        panel.setFrameOrigin_((x, y))

    _banner = panel
    return panel


def show(x: float | None = None, y: float | None = None) -> bool:
    """Show presence UI at pointer (or x,y). No-op if DH_PRESENCE=0."""
    global _active
    if not enabled():
        return False
    import Quartz
    if x is None or y is None:
        ev = Quartz.CGEventCreate(None)
        p = Quartz.CGEventGetLocation(ev)
        x = float(p.x) if x is None else x
        y = float(p.y) if y is None else y
    try:
        ring = _ring or _make_ring()
        cx, cy = _screen_to_cocoa(float(x), float(y), _RING)
        ring.setFrameOrigin_((cx, cy))
        ring.setContentSize_((_RING, _RING))
        ring.orderFrontRegardless()

        ban = _banner or _make_banner()
        ban.orderFrontRegardless()
        _active = True
        _pump()
        return True
    except Exception:
        return False


def move(x: float, y: float) -> None:
    if not enabled() or not _active:
        # auto-start on first move if presence wanted
        if enabled():
            show(x, y)
        return
    if _ring is None:
        show(x, y)
        return
    try:
        cx, cy = _screen_to_cocoa(float(x), float(y), _RING)
        _ring.setFrameOrigin_((cx, cy))
        _pump(1)
    except Exception:
        pass


def click_flash(x: float, y: float) -> None:
    """Brief larger ring at click point — one pulse, then back."""
    if not enabled():
        return
    try:
        show(x, y)
        if _ring is None:
            return
        # expand
        cx, cy = _screen_to_cocoa(float(x), float(y), _FLASH)
        _ring.setFrame_display_(
            __import__("AppKit").NSMakeRect(cx, cy, _FLASH, _FLASH), True
        )
        view = _ring.contentView()
        if view and view.layer():
            view.layer().setCornerRadius_(_FLASH / 2)
            from Quartz import CGColorCreateGenericRGB
            view.layer().setBackgroundColor_(
                CGColorCreateGenericRGB(0.25, 0.45, 0.95, 0.40)
            )
        _pump(2)
        time.sleep(0.07)
        # restore
        cx, cy = _screen_to_cocoa(float(x), float(y), _RING)
        _ring.setFrame_display_(
            __import__("AppKit").NSMakeRect(cx, cy, _RING, _RING), True
        )
        if view and view.layer():
            view.layer().setCornerRadius_(_RING / 2)
            from Quartz import CGColorCreateGenericRGB
            view.layer().setBackgroundColor_(
                CGColorCreateGenericRGB(0.25, 0.45, 0.95, 0.28)
            )
        _pump(1)
    except Exception:
        pass


def hide() -> None:
    global _ring, _banner, _active
    try:
        if _ring is not None:
            _ring.orderOut_(None)
            _ring = None
        if _banner is not None:
            _banner.orderOut_(None)
            _banner = None
    except Exception:
        pass
    _active = False
    _pump()


def ensure() -> None:
    """Idempotent: show presence at current mouse if enabled."""
    if not enabled():
        return
    if _active:
        return
    show()


# --- aliases used by older enable_agent_cursor path ---
def show_at(x=None, y=None, color: Any = None):
    return show(x, y)


# module looks like old overlay API
def pulse():
    import Quartz
    ev = Quartz.CGEventCreate(None)
    p = Quartz.CGEventGetLocation(ev)
    click_flash(float(p.x), float(p.y))
