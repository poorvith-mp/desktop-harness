"""Visible agent presence: bright ring on the REAL pointer + top banner.

Placement uses NSEvent.mouseLocation() after warps so the ring sticks to
the system cursor (no fragile CG↔Cocoa math).

Disable: DH_PRESENCE=0
"""
from __future__ import annotations

import os
import time
from typing import Any

_ring = None
_banner = None
_app = None
_active = False

_RING = 44.0
_FLASH = 72.0


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
    try:
        _app.finishLaunching()
    except Exception:
        pass
    return _app


def _pump(n: int = 12, seconds: float = 0.03):
    try:
        from AppKit import NSDate, NSDefaultRunLoopMode
        app = _ensure_app()
        deadline = time.time() + seconds
        i = 0
        while i < n or time.time() < deadline:
            ev = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                (1 << 64) - 1,
                NSDate.dateWithTimeIntervalSinceNow_(0.002),
                NSDefaultRunLoopMode,
                True,
            )
            if ev is not None:
                app.sendEvent_(ev)
            i += 1
    except Exception:
        pass


def _mouse_cocoa() -> tuple[float, float]:
    """Current pointer in Cocoa global coords (origin bottom-left)."""
    from AppKit import NSEvent
    loc = NSEvent.mouseLocation()
    return float(loc.x), float(loc.y)


def _style_panel(panel, boost: int = 0):
    from AppKit import NSColor, NSStatusWindowLevel, NSFloatingWindowLevel
    try:
        panel.setLevel_(int(NSStatusWindowLevel) + 5 + boost)
    except Exception:
        panel.setLevel_(int(NSFloatingWindowLevel) + 20 + boost)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setIgnoresMouseEvents_(True)
    panel.setHasShadow_(True)
    try:
        panel.setHidesOnDeactivate_(False)
    except Exception:
        pass
    try:
        panel.setCollectionBehavior_(1 << 0 | 1 << 7 | 1 << 3)
    except Exception:
        pass
    try:
        panel.setAlphaValue_(1.0)
    except Exception:
        pass


def _paint_ring(size: float, rgba=(0.10, 0.50, 1.0, 0.70), border=3.5):
    """Recreate ring view with given size/color (simple + reliable)."""
    global _ring
    from AppKit import NSMakeRect, NSPanel, NSView, NSWindowStyleMaskBorderless
    from Quartz import CGColorCreateGenericRGB

    _ensure_app()
    # keep same panel if possible
    if _ring is None:
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, size, size),
            NSWindowStyleMaskBorderless,
            2,
            False,
        )
        _style_panel(panel)
        _ring = panel
    else:
        panel = _ring

    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, size, size))
    view.setWantsLayer_(True)
    layer = view.layer()
    if layer is not None:
        layer.setCornerRadius_(size / 2.0)
        r, g, b, a = rgba
        layer.setBackgroundColor_(CGColorCreateGenericRGB(r, g, b, a))
        layer.setBorderWidth_(border)
        layer.setBorderColor_(CGColorCreateGenericRGB(1, 1, 1, 1.0))
        try:
            layer.setShadowOpacity_(0.5)
            layer.setShadowRadius_(10.0)
        except Exception:
            pass
    panel.setContentView_(view)
    return panel


def _place_ring_on_mouse(size: float | None = None):
    size = size or _RING
    mx, my = _mouse_cocoa()
    from AppKit import NSMakeRect
    panel = _ring or _paint_ring(size)
    # center ring on pointer
    panel.setFrame_display_(
        NSMakeRect(mx - size / 2.0, my - size / 2.0, size, size), True
    )
    panel.orderFrontRegardless()
    return mx, my


def _make_banner():
    global _banner
    from AppKit import (
        NSColor, NSMakeRect, NSPanel, NSTextField, NSFont, NSView,
        NSWindowStyleMaskBorderless, NSCenterTextAlignment, NSScreen,
    )
    from Quartz import CGColorCreateGenericRGB

    _ensure_app()
    w, h = 320.0, 40.0
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, w, h),
        NSWindowStyleMaskBorderless,
        2,
        False,
    )
    _style_panel(panel, boost=2)

    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    view.setWantsLayer_(True)
    layer = view.layer()
    if layer is not None:
        layer.setCornerRadius_(h / 2.0)
        layer.setBackgroundColor_(CGColorCreateGenericRGB(0.02, 0.02, 0.05, 0.94))
        layer.setBorderWidth_(2.0)
        layer.setBorderColor_(CGColorCreateGenericRGB(0.2, 0.55, 1.0, 1.0))

    label = NSTextField.alloc().initWithFrame_(NSMakeRect(12, 8, w - 24, h - 16))
    label.setStringValue_("●  AGENT ACTIVE  ·  don't touch the mouse")
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setAlignment_(NSCenterTextAlignment)
    try:
        label.setTextColor_(NSColor.whiteColor())
        label.setFont_(NSFont.boldSystemFontOfSize_(13.0))
    except Exception:
        pass
    view.addSubview_(label)
    panel.setContentView_(view)

    screen = NSScreen.mainScreen()
    if screen is not None:
        sf = screen.frame()
        x = sf.origin.x + (sf.size.width - w) / 2.0
        y = sf.origin.y + sf.size.height - h - 20.0
        panel.setFrameOrigin_((x, y))

    _banner = panel
    return panel


def show(x: float | None = None, y: float | None = None) -> bool:
    """Show banner + ring. x,y optional (CG); ring snaps to real mouse after."""
    global _active
    if not enabled():
        return False
    try:
        # If CG coords given, warp first so mouseLocation matches intent
        if x is not None and y is not None:
            import Quartz
            Quartz.CGWarpMouseCursorPosition(
                Quartz.CGPointMake(float(x), float(y))
            )
            Quartz.CGAssociateMouseAndMouseCursorPosition(True)
            time.sleep(0.01)

        _paint_ring(_RING)
        _place_ring_on_mouse(_RING)

        ban = _banner or _make_banner()
        ban.orderFrontRegardless()

        _active = True
        _pump(n=25, seconds=0.1)
        return True
    except Exception as e:
        try:
            print(f"[presence] show failed: {type(e).__name__}: {e}")
        except Exception:
            pass
        return False


def move(x: float, y: float) -> None:
    """x,y are CGEvent coords (same as CGWarp). Snap ring to real mouse."""
    if not enabled():
        return
    if not _active:
        show(x, y)
        return
    try:
        # Caller already warped; just stick ring to Cocoa mouse
        if _ring is None:
            _paint_ring(_RING)
        _place_ring_on_mouse(_RING)
        if _banner is not None:
            _banner.orderFrontRegardless()
        _pump(n=4, seconds=0.008)
    except Exception:
        pass


def click_flash(x: float, y: float) -> None:
    if not enabled():
        return
    try:
        show(x, y)
        # Orange flash — hard to miss
        _paint_ring(
            _FLASH,
            rgba=(1.0, 0.35, 0.10, 0.75),
            border=4.0,
        )
        _place_ring_on_mouse(_FLASH)
        _pump(n=15, seconds=0.06)
        time.sleep(0.10)
        # Back to blue
        _paint_ring(_RING)
        _place_ring_on_mouse(_RING)
        _pump(n=8, seconds=0.03)
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
    _pump(n=6, seconds=0.02)


def ensure() -> None:
    if not enabled():
        return
    if _active:
        return
    show()


def pulse():
    import Quartz
    ev = Quartz.CGEventCreate(None)
    p = Quartz.CGEventGetLocation(ev)
    click_flash(float(p.x), float(p.y))
