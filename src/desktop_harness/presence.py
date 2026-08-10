"""Subtle agent presence: soft-glow pointer + refined hands-off bar.

- Pointer: thin arrow + soft natural glow (not bold)
- Placement: follows CG warp target (no laggy mouseLocation chase)
- System cursor hidden while active (avoids double-cursor offset)
- Banner: quiet bar under notch (visibleFrame), better design

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
_cursor_hidden = False

# Canvas large enough for soft glow; tip near top-left of shape
_CANVAS = 48.0
# Hot-spot of our drawn arrow (tip) inside the canvas (Cocoa, y-up)
_HOT_X = 5.5
_HOT_Y = 42.5


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


def _pump(n: int = 4, seconds: float = 0.01):
    """Minimal runloop spin — keep short so motion stays snappy."""
    try:
        from AppKit import NSDate, NSDefaultRunLoopMode
        app = _ensure_app()
        deadline = time.time() + seconds
        i = 0
        while i < n and time.time() < deadline:
            ev = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                (1 << 64) - 1,
                NSDate.dateWithTimeIntervalSinceNow_(0.0005),
                NSDefaultRunLoopMode,
                True,
            )
            if ev is not None:
                app.sendEvent_(ev)
            i += 1
    except Exception:
        pass


def _hide_system_cursor():
    global _cursor_hidden
    if _cursor_hidden:
        return
    try:
        import Quartz
        # Nested hide count; we match with one show on hide()
        Quartz.CGDisplayHideCursor(Quartz.CGMainDisplayID())
        _cursor_hidden = True
    except Exception:
        pass


def _show_system_cursor():
    global _cursor_hidden
    if not _cursor_hidden:
        return
    try:
        import Quartz
        Quartz.CGDisplayShowCursor(Quartz.CGMainDisplayID())
        _cursor_hidden = False
    except Exception:
        _cursor_hidden = False


def _cg_to_cocoa_origin(cg_x: float, cg_y: float) -> tuple[float, float]:
    """CGEvent point → Cocoa origin for our pointer panel (tip on cg point)."""
    from AppKit import NSScreen
    main = NSScreen.mainScreen()
    if main is None:
        return cg_x - _HOT_X, -cg_y - (_CANVAS - _HOT_Y)
    mf = main.frame()
    # CG: origin top-left of primary, y down
    # Cocoa: origin bottom-left of primary's space, y up
    cocoa_x = float(mf.origin.x) + float(cg_x) - _HOT_X
    cocoa_y = float(mf.origin.y) + float(mf.size.height) - float(cg_y) - _HOT_Y
    return cocoa_x, cocoa_y


def _style_panel(panel, boost: int = 0):
    from AppKit import NSColor, NSStatusWindowLevel, NSFloatingWindowLevel
    try:
        panel.setLevel_(int(NSStatusWindowLevel) + 4 + boost)
    except Exception:
        panel.setLevel_(int(NSFloatingWindowLevel) + 15 + boost)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setIgnoresMouseEvents_(True)
    panel.setHasShadow_(False)
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
    _cls = None

    @classmethod
    def view_class(cls):
        if cls._cls is not None:
            return cls._cls
        from AppKit import NSView

        class AgentPointerView(NSView):
            mode = "normal"  # normal | click

            def isFlipped(self):
                return False

            def drawRect_(self, rect):
                from AppKit import NSBezierPath, NSColor, NSRectFill

                NSColor.clearColor().set()
                NSRectFill(self.bounds())

                # Slim classic arrow (tip top-left-ish)
                tip = (5.5, 42.5)
                pts = [
                    tip,
                    (5.5, 16.0),
                    (11.5, 21.5),
                    (17.5, 8.0),
                    (21.0, 9.5),
                    (14.0, 22.5),
                    (21.5, 22.5),
                ]
                path = NSBezierPath.bezierPath()
                path.moveToPoint_(pts[0])
                for p in pts[1:]:
                    path.lineToPoint_(p)
                path.closePath()

                # Soft natural glow — wide, low alpha (not a hard halo)
                if self.mode == "click":
                    glow_rgb = (0.95, 0.50, 0.28)
                    glow_layers = ((14, 0.05), (9, 0.08), (5, 0.12))
                    fill_a = 0.88
                    edge_a = 0.45
                else:
                    glow_rgb = (0.30, 0.52, 0.95)
                    glow_layers = ((16, 0.04), (10, 0.07), (6, 0.11), (3, 0.16))
                    fill_a = 0.90
                    edge_a = 0.40

                gr, gg, gb = glow_rgb
                for width, alpha in glow_layers:
                    g = path.copy()
                    g.setLineWidth_(float(width))
                    g.setLineJoinStyle_(1)  # round
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        gr, gg, gb, alpha
                    ).set()
                    g.stroke()

                # Soft white fill — not pure neon
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    0.99, 0.99, 1.0, fill_a
                ).set()
                path.fill()

                # Very light edge (not bold outline)
                path.setLineWidth_(0.8)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    gr, gg, gb, edge_a
                ).set()
                path.stroke()

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
    view.mode = "normal"
    panel.setContentView_(view)
    _ring = panel
    return panel


def _place_at_cg(cg_x: float, cg_y: float):
    """Snap pointer panel so tip sits on CG warp target — no lag chase."""
    if _ring is None:
        return
    from AppKit import NSMakeRect
    ox, oy = _cg_to_cocoa_origin(cg_x, cg_y)
    # setFrameOrigin is cheaper than full setFrame when size fixed
    _ring.setFrameOrigin_((ox, oy))
    _ring.orderFrontRegardless()


def _banner_geometry():
    """Below menu bar / notch using visibleFrame."""
    from AppKit import NSScreen
    screen = NSScreen.mainScreen()
    if screen is None:
        return 400.0, 800.0, 260.0, 32.0
    vf = screen.visibleFrame()
    w, h = 248.0, 30.0
    x = vf.origin.x + (vf.size.width - w) / 2.0
    # A bit lower into the content area — never under the notch
    y = vf.origin.y + vf.size.height - h - 8.0
    return x, y, w, h


def _make_banner():
    global _banner
    from AppKit import (
        NSColor, NSMakeRect, NSPanel, NSTextField, NSFont, NSView,
        NSWindowStyleMaskBorderless, NSCenterTextAlignment,
    )
    from Quartz import CGColorCreateGenericRGB

    _ensure_app()
    x, y, w, h = _banner_geometry()
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
        # Soft frosted bar — not a loud slab
        layer.setBackgroundColor_(CGColorCreateGenericRGB(0.12, 0.13, 0.15, 0.72))
        layer.setBorderWidth_(0.6)
        layer.setBorderColor_(CGColorCreateGenericRGB(1, 1, 1, 0.10))
        try:
            layer.setShadowOpacity_(0.25)
            layer.setShadowRadius_(6.0)
            layer.setShadowOffset_((0, -1))
        except Exception:
            pass

    # Leading accent dot via unicode + quieter label
    label = NSTextField.alloc().initWithFrame_(NSMakeRect(14, 6, w - 28, h - 12))
    label.setStringValue_("Agent controlling")
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setAlignment_(NSCenterTextAlignment)
    try:
        label.setTextColor_(
            NSColor.colorWithCalibratedWhite_alpha_(0.92, 0.88)
        )
        label.setFont_(NSFont.systemFontOfSize_weight_(11.5, -0.2))  # light
    except Exception:
        try:
            label.setTextColor_(NSColor.whiteColor())
            label.setFont_(NSFont.systemFontOfSize_(11.5))
        except Exception:
            pass
    view.addSubview_(label)

    # Small blue status pip on the left
    pip = NSView.alloc().initWithFrame_(NSMakeRect(12, (h - 6) / 2, 6, 6))
    pip.setWantsLayer_(True)
    if pip.layer() is not None:
        pip.layer().setCornerRadius_(3.0)
        pip.layer().setBackgroundColor_(
            CGColorCreateGenericRGB(0.35, 0.60, 1.0, 0.95)
        )
    view.addSubview_(pip)

    panel.setContentView_(view)
    panel.setFrameOrigin_((x, y))
    _banner = panel
    return panel


def show(x: float | None = None, y: float | None = None) -> bool:
    global _active
    if not enabled():
        return False
    try:
        import Quartz
        if x is None or y is None:
            ev = Quartz.CGEventCreate(None)
            p = Quartz.CGEventGetLocation(ev)
            x = float(p.x) if x is None else float(x)
            y = float(p.y) if y is None else float(y)
        else:
            x, y = float(x), float(y)
            Quartz.CGWarpMouseCursorPosition(Quartz.CGPointMake(x, y))
            Quartz.CGAssociateMouseAndMouseCursorPosition(True)

        if _ring is None:
            _make_pointer_panel()
        view = _ring.contentView()
        if view is not None:
            view.mode = "normal"
            view.setNeedsDisplay_(True)

        _hide_system_cursor()
        _place_at_cg(x, y)

        ban = _banner or _make_banner()
        bx, by, bw, bh = _banner_geometry()
        from AppKit import NSMakeRect
        ban.setFrame_display_(NSMakeRect(bx, by, bw, bh), True)
        ban.orderFrontRegardless()

        _active = True
        _pump(n=12, seconds=0.04)
        return True
    except Exception as e:
        try:
            print(f"[presence] show failed: {type(e).__name__}: {e}")
        except Exception:
            pass
        _show_system_cursor()
        return False


def move(x: float, y: float) -> None:
    """Called after CG warp with the same CG coords — stay locked, no chase lag."""
    if not enabled():
        return
    if not _active:
        show(x, y)
        return
    try:
        if _ring is None:
            _make_pointer_panel()
        _place_at_cg(float(x), float(y))
        # No heavy pump on every step — keeps glow glued to motion
    except Exception:
        pass


def click_flash(x: float, y: float) -> None:
    if not enabled():
        return
    try:
        if not _active:
            show(x, y)
        view = _ring.contentView() if _ring else None
        if view is not None:
            view.mode = "click"
            view.setNeedsDisplay_(True)
        _place_at_cg(float(x), float(y))
        _pump(n=6, seconds=0.02)
        time.sleep(0.07)
        if view is not None:
            view.mode = "normal"
            view.setNeedsDisplay_(True)
        _place_at_cg(float(x), float(y))
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
    _show_system_cursor()
    _pump(n=4, seconds=0.015)


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


def _make_pointer_panel():
    global _ring
    from AppKit import NSMakeRect, NSPanel, NSWindowStyleMaskBorderless
    _ensure_app()
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, _CANVAS, _CANVAS),
        NSWindowStyleMaskBorderless,
        2,
        False,
    )
    _style_panel(panel)
    View = _PointerView.view_class()
    view = View.alloc().initWithFrame_(NSMakeRect(0, 0, _CANVAS, _CANVAS))
    view.mode = "normal"
    panel.setContentView_(view)
    _ring = panel
    return panel
