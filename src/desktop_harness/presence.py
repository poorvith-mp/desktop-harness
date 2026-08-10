"""Subtle agent presence: soft-glow pointer (not a bold circle) + safe banner.

Design goals (user feedback):
  - Cursor-like, elegant, slightly glowing — not a loud solid disc
  - Banner must clear the notch (use visibleFrame, not raw top-center)
  - Still clearly means: agent is driving — hands off

Disable: DH_PRESENCE=0
"""
from __future__ import annotations

import os
import time
from typing import Any

_ring = None  # pointer panel
_banner = None
_app = None
_active = False

# Pointer canvas (includes glow padding)
_CANVAS = 56.0
_HOT_X = 8.0   # tip offset inside canvas (classic arrow tip near top-left)
_HOT_Y = 44.0  # cocoa: tip near top of canvas


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


def _pump(n: int = 10, seconds: float = 0.025):
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
    from AppKit import NSEvent
    loc = NSEvent.mouseLocation()
    return float(loc.x), float(loc.y)


def _style_panel(panel, boost: int = 0):
    from AppKit import NSColor, NSStatusWindowLevel, NSFloatingWindowLevel
    try:
        panel.setLevel_(int(NSStatusWindowLevel) + 4 + boost)
    except Exception:
        panel.setLevel_(int(NSFloatingWindowLevel) + 15 + boost)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setIgnoresMouseEvents_(True)
    panel.setHasShadow_(False)  # we draw our own soft glow
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


class _PointerView:
    """NSView subclass that draws a soft-glow mouse pointer."""

    _cls = None

    @classmethod
    def view_class(cls):
        if cls._cls is not None:
            return cls._cls
        from AppKit import NSView
        import objc

        class AgentPointerView(NSView):
            accent = (0.25, 0.55, 0.98)  # soft blue
            flash = False

            def drawRect_(self, rect):
                from AppKit import (
                    NSBezierPath, NSColor, NSGraphicsContext,
                    NSCompositingOperationSourceOver,
                )
                # Clear
                NSColor.clearColor().set()
                from AppKit import NSRectFill
                NSRectFill(self.bounds())

                # Classic arrow in view coords (origin bottom-left of view)
                # Tip near top-left of the shape, matching system cursor feel
                tip_x, tip_y = 6.0, 50.0
                pts = [
                    (tip_x, tip_y),
                    (tip_x, tip_y - 28),
                    (tip_x + 7, tip_y - 22),
                    (tip_x + 14, tip_y - 36),
                    (tip_x + 18, tip_y - 34),
                    (tip_x + 10, tip_y - 20),
                    (tip_x + 18, tip_y - 20),
                ]

                path = NSBezierPath.bezierPath()
                path.moveToPoint_(pts[0])
                for p in pts[1:]:
                    path.lineToPoint_(p)
                path.closePath()

                ar, ag, ab = self.accent
                if self.flash:
                    ar, ag, ab = 0.98, 0.45, 0.18

                # Soft outer glow (stacked translucent strokes)
                ctx = NSGraphicsContext.currentContext()
                for i, (w, a) in enumerate(((18, 0.06), (12, 0.10), (7, 0.16), (3.5, 0.28))):
                    glow = path.copy()
                    glow.setLineWidth_(w)
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        ar, ag, ab, a
                    ).set()
                    glow.stroke()

                # Fill pointer — mostly white, slight tint
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    0.98, 0.99, 1.0, 0.92
                ).set()
                path.fill()

                # Thin accent edge
                path.setLineWidth_(1.1)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    ar, ag, ab, 0.85
                ).set()
                path.stroke()

                # Tiny inner accent line for depth
                path.setLineWidth_(0.6)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    0.15, 0.15, 0.2, 0.25
                ).set()
                path.stroke()

            def isFlipped(self):
                return False

        cls._cls = AgentPointerView
        return cls._cls


def _make_pointer_panel():
    global _ring
    from AppKit import NSMakeRect, NSPanel, NSWindowStyleMaskBorderless

    _ensure_app()
    size = _CANVAS
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, size, size),
        NSWindowStyleMaskBorderless,
        2,
        False,
    )
    _style_panel(panel)
    View = _PointerView.view_class()
    view = View.alloc().initWithFrame_(NSMakeRect(0, 0, size, size))
    view.accent = (0.25, 0.55, 0.98)
    view.flash = False
    panel.setContentView_(view)
    _ring = panel
    return panel


def _place_pointer():
    """Align pointer tip with the real system cursor hot-spot."""
    if _ring is None:
        return
    from AppKit import NSMakeRect
    mx, my = _mouse_cocoa()
    # System arrow tip ≈ at mouse location; our tip is at (_HOT_X, _HOT_Y) in view
    # View is not flipped: y up, tip near top of canvas
    ox = mx - _HOT_X
    oy = my - _HOT_Y
    _ring.setFrame_display_(NSMakeRect(ox, oy, _CANVAS, _CANVAS), True)
    _ring.orderFrontRegardless()


def _banner_frame():
    """Top of *visible* frame — clears notch + menu bar."""
    from AppKit import NSScreen
    screen = NSScreen.mainScreen()
    if screen is None:
        return 200.0, 200.0, 300.0, 34.0
    # visibleFrame excludes menu bar / notch obstruction area
    vf = screen.visibleFrame()
    w, h = 300.0, 34.0
    # Sit just under the menu bar / notch, still in visible area
    x = vf.origin.x + (vf.size.width - w) / 2.0
    y = vf.origin.y + vf.size.height - h - 10.0
    return x, y, w, h


def _make_banner():
    global _banner
    from AppKit import (
        NSColor, NSMakeRect, NSPanel, NSTextField, NSFont, NSView,
        NSWindowStyleMaskBorderless, NSCenterTextAlignment,
    )
    from Quartz import CGColorCreateGenericRGB

    _ensure_app()
    x, y, w, h = _banner_frame()
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, w, h),
        NSWindowStyleMaskBorderless,
        2,
        False,
    )
    _style_panel(panel, boost=1)

    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    view.setWantsLayer_(True)
    layer = view.layer()
    if layer is not None:
        layer.setCornerRadius_(h / 2.0)
        # Quiet dark glass — not loud blue slab
        layer.setBackgroundColor_(CGColorCreateGenericRGB(0.10, 0.11, 0.13, 0.78))
        layer.setBorderWidth_(0.8)
        layer.setBorderColor_(CGColorCreateGenericRGB(0.35, 0.50, 0.85, 0.45))

    label = NSTextField.alloc().initWithFrame_(NSMakeRect(12, 7, w - 24, h - 14))
    label.setStringValue_("Agent active  ·  hands off")
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setAlignment_(NSCenterTextAlignment)
    try:
        label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(0.95, 0.92))
        label.setFont_(NSFont.systemFontOfSize_weight_(12.0, 0.2))
    except Exception:
        try:
            label.setTextColor_(NSColor.whiteColor())
            label.setFont_(NSFont.systemFontOfSize_(12.0))
        except Exception:
            pass
    view.addSubview_(label)
    panel.setContentView_(view)
    panel.setFrameOrigin_((x, y))
    _banner = panel
    return panel


def show(x: float | None = None, y: float | None = None) -> bool:
    global _active
    if not enabled():
        return False
    try:
        if x is not None and y is not None:
            import Quartz
            Quartz.CGWarpMouseCursorPosition(
                Quartz.CGPointMake(float(x), float(y))
            )
            Quartz.CGAssociateMouseAndMouseCursorPosition(True)
            time.sleep(0.008)

        if _ring is None:
            _make_pointer_panel()
        else:
            view = _ring.contentView()
            if view is not None:
                view.flash = False
                view.accent = (0.25, 0.55, 0.98)
                view.setNeedsDisplay_(True)
        _place_pointer()

        ban = _banner or _make_banner()
        # Recompute position (screen / space may change)
        bx, by, bw, bh = _banner_frame()
        from AppKit import NSMakeRect
        ban.setFrame_display_(NSMakeRect(bx, by, bw, bh), True)
        ban.orderFrontRegardless()

        _active = True
        _pump(n=20, seconds=0.08)
        return True
    except Exception as e:
        try:
            print(f"[presence] show failed: {type(e).__name__}: {e}")
        except Exception:
            pass
        return False


def move(x: float, y: float) -> None:
    if not enabled():
        return
    if not _active:
        show(x, y)
        return
    try:
        if _ring is None:
            _make_pointer_panel()
        _place_pointer()
        if _banner is not None:
            _banner.orderFrontRegardless()
        _pump(n=3, seconds=0.006)
    except Exception:
        pass


def click_flash(x: float, y: float) -> None:
    """Subtle warm pulse on click — not a huge orange disc."""
    if not enabled():
        return
    try:
        show(x, y)
        view = _ring.contentView() if _ring else None
        if view is not None:
            view.flash = True
            view.setNeedsDisplay_(True)
        _place_pointer()
        _pump(n=12, seconds=0.04)
        time.sleep(0.08)
        if view is not None:
            view.flash = False
            view.setNeedsDisplay_(True)
        _place_pointer()
        _pump(n=6, seconds=0.02)
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
    _pump(n=5, seconds=0.02)


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
