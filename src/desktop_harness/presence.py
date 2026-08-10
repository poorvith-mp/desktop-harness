"""Agent presence — observe-improve loop design (v soft).

What screenshots showed was wrong:
  - Banner sat in app chrome / near notch → looked like a tab, not a status chip
  - Custom cursor too weak / system cursor still visible → double offset lag
  - Glow felt harsh or laggy when chasing mouseLocation

Fixes:
  - Banner: bottom-center of visibleFrame (always clear of notch + menu)
  - Hide system cursor via NSCursor.hide() while active
  - Place overlay on CG warp target (no chase lag)
  - Soft arrow + gentle blue glow only

DH_PRESENCE=0 to disable.
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

_CANVAS = 52.0
# Tip of drawn arrow inside the canvas (Cocoa y-up)
_HOT_X = 6.0
_HOT_Y = 44.0


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


def _pump(n: int = 3, seconds: float = 0.008):
    try:
        from AppKit import NSDate, NSDefaultRunLoopMode
        app = _ensure_app()
        deadline = time.time() + seconds
        i = 0
        while i < n and time.time() < deadline:
            ev = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                (1 << 64) - 1,
                NSDate.dateWithTimeIntervalSinceNow_(0.0004),
                NSDefaultRunLoopMode,
                True,
            )
            if ev is not None:
                app.sendEvent_(ev)
            i += 1
    except Exception:
        pass


def _hide_system_cursor():
    """Hide the *global* system cursor (NSCursor.hide only affects our process)."""
    global _cursor_hidden
    try:
        import Quartz
        # CGDisplayHideCursor is reference-counted; hide until not visible
        for _ in range(4):
            try:
                if hasattr(Quartz, "CGCursorIsVisible") and not Quartz.CGCursorIsVisible():
                    break
            except Exception:
                pass
            Quartz.CGDisplayHideCursor(Quartz.CGMainDisplayID())
        _cursor_hidden = True
    except Exception:
        try:
            from AppKit import NSCursor
            NSCursor.hide()
            _cursor_hidden = True
        except Exception:
            pass


def _show_system_cursor():
    global _cursor_hidden
    if not _cursor_hidden:
        return
    try:
        import Quartz
        # Match hide count (we may have called hide multiple times)
        for _ in range(6):
            try:
                if hasattr(Quartz, "CGCursorIsVisible") and Quartz.CGCursorIsVisible():
                    break
            except Exception:
                pass
            Quartz.CGDisplayShowCursor(Quartz.CGMainDisplayID())
    except Exception:
        try:
            from AppKit import NSCursor
            NSCursor.unhide()
        except Exception:
            pass
    _cursor_hidden = False


def _cg_to_panel_origin(cg_x: float, cg_y: float) -> tuple[float, float]:
    """CG warp point → Cocoa origin so drawn tip sits on the hot-spot."""
    from AppKit import NSScreen
    main = NSScreen.mainScreen()
    if main is None:
        return cg_x - _HOT_X, -cg_y
    mf = main.frame()
    cocoa_x = float(mf.origin.x) + float(cg_x) - _HOT_X
    cocoa_y = float(mf.origin.y) + float(mf.size.height) - float(cg_y) - _HOT_Y
    return cocoa_x, cocoa_y


def _style_panel(panel, boost: int = 0):
    from AppKit import NSColor, NSStatusWindowLevel, NSFloatingWindowLevel, NSPopUpMenuWindowLevel
    # Must sit above the Dock (status level alone is not enough on many Macs)
    try:
        panel.setLevel_(int(NSPopUpMenuWindowLevel) + 5 + boost)
    except Exception:
        try:
            panel.setLevel_(int(NSStatusWindowLevel) + 30 + boost)
        except Exception:
            panel.setLevel_(int(NSFloatingWindowLevel) + 50 + boost)
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


class _PointerView:
    _cls = None

    @classmethod
    def view_class(cls):
        if cls._cls is not None:
            return cls._cls
        from AppKit import NSView

        class AgentPointerView(NSView):
            mode = "normal"

            def isFlipped(self):
                return False

            def drawRect_(self, rect):
                from AppKit import NSBezierPath, NSColor, NSRectFill

                NSColor.clearColor().set()
                NSRectFill(self.bounds())

                # Slim system-like arrow
                pts = [
                    (6.0, 44.0),   # tip
                    (6.0, 18.0),
                    (12.0, 23.5),
                    (17.5, 10.0),
                    (20.5, 11.5),
                    (14.0, 24.5),
                    (21.0, 24.5),
                ]
                path = NSBezierPath.bezierPath()
                path.moveToPoint_(pts[0])
                for p in pts[1:]:
                    path.lineToPoint_(p)
                path.closePath()

                # Always cool blue — never red/orange (that read as errors)
                if self.mode == "click":
                    # Brief warm/red pulse on click (then back to blue)
                    gr, gg, gb = 0.98, 0.32, 0.28
                    layers = ((14, 0.07), (8, 0.12), (4, 0.18))
                else:
                    # Moving / idle: soft blue
                    gr, gg, gb = 0.30, 0.55, 0.98
                    layers = ((16, 0.04), (10, 0.07), (6, 0.11), (3, 0.15))

                for width, alpha in layers:
                    g = path.copy()
                    g.setLineWidth_(float(width))
                    try:
                        g.setLineJoinStyle_(1)
                        g.setLineCapStyle_(1)
                    except Exception:
                        pass
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        gr, gg, gb, alpha
                    ).set()
                    g.stroke()

                # Soft white body
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    1.0, 1.0, 1.0, 0.96
                ).set()
                path.fill()

                # Whisper of cool edge — not bold
                path.setLineWidth_(0.6)
                NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    gr, gg, gb, 0.28
                ).set()
                path.stroke()

        cls._cls = AgentPointerView
        return cls._cls


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


def _place_at_cg(cg_x: float, cg_y: float):
    if _ring is None:
        return
    ox, oy = _cg_to_panel_origin(cg_x, cg_y)
    _ring.setFrameOrigin_((ox, oy))
    _ring.orderFrontRegardless()


def _banner_layout():
    """Full panel rect in Cocoa coords — pill + neon pad fully inside visibleFrame.

    Past bug: origin was (pill_x - pad, pill_y - pad) with pill_y near dock,
    so half the glow sat under the Dock / off-screen.
    """
    from AppKit import NSScreen
    screen = NSScreen.mainScreen()
    pad = 18.0
    w, h = 248.0, 36.0
    if screen is None:
        return 400.0, 60.0, w, h, pad
    vf = screen.visibleFrame()
    # Sit clearly above the Dock / bottom chrome (half-buried was the #1 bug)
    margin = pad + 52.0
    pill_x = vf.origin.x + (vf.size.width - w) / 2.0
    pill_y = vf.origin.y + margin
    panel_x = pill_x - pad
    panel_y = pill_y - pad
    panel_w = w + pad * 2
    panel_h = h + pad * 2
    return panel_x, panel_y, panel_w, panel_h, w, h, pad


def _make_banner():
    """Bottom status chip: dark glass + strong neon cyan border glow (fully on-screen)."""
    global _banner
    from AppKit import (
        NSColor, NSMakeRect, NSPanel, NSTextField, NSFont, NSView,
        NSWindowStyleMaskBorderless, NSCenterTextAlignment,
    )
    from Quartz import CGColorCreateGenericRGB

    _ensure_app()
    panel_x, panel_y, panel_w, panel_h, w, h, pad = _banner_layout()
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, panel_w, panel_h),
        NSWindowStyleMaskBorderless,
        2,
        False,
    )
    _style_panel(panel, boost=1)

    root = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, panel_w, panel_h))
    root.setWantsLayer_(True)
    if root.layer() is not None:
        root.layer().setBackgroundColor_(CGColorCreateGenericRGB(0, 0, 0, 0))

    # Outer neon wash
    halo = NSView.alloc().initWithFrame_(
        NSMakeRect(pad - 6, pad - 6, w + 12, h + 12)
    )
    halo.setWantsLayer_(True)
    if halo.layer() is not None:
        halo.layer().setCornerRadius_((h + 12) / 2.0)
        halo.layer().setBackgroundColor_(
            CGColorCreateGenericRGB(0.20, 0.50, 1.0, 0.16)
        )
        try:
            halo.layer().setShadowOpacity_(1.0)
            halo.layer().setShadowRadius_(20.0)
            halo.layer().setShadowOffset_((0, 0))
            halo.layer().setShadowColor_(
                CGColorCreateGenericRGB(0.30, 0.60, 1.0, 1.0)
            )
        except Exception:
            pass
    root.addSubview_(halo)

    # Main pill
    pill = NSView.alloc().initWithFrame_(NSMakeRect(pad, pad, w, h))
    pill.setWantsLayer_(True)
    layer = pill.layer()
    if layer is not None:
        layer.setCornerRadius_(h / 2.0)
        layer.setBackgroundColor_(CGColorCreateGenericRGB(0.05, 0.06, 0.09, 0.90))
        layer.setBorderWidth_(1.5)
        layer.setBorderColor_(CGColorCreateGenericRGB(0.40, 0.75, 1.0, 0.95))
        try:
            layer.setShadowOpacity_(1.0)
            layer.setShadowRadius_(12.0)
            layer.setShadowOffset_((0, 0))
            layer.setShadowColor_(
                CGColorCreateGenericRGB(0.35, 0.70, 1.0, 1.0)
            )
        except Exception:
            pass

    pip = NSView.alloc().initWithFrame_(NSMakeRect(16, (h - 6) / 2.0, 6, 6))
    pip.setWantsLayer_(True)
    if pip.layer() is not None:
        pip.layer().setCornerRadius_(3.0)
        pip.layer().setBackgroundColor_(
            CGColorCreateGenericRGB(0.50, 0.80, 1.0, 1.0)
        )
        try:
            pip.layer().setShadowOpacity_(1.0)
            pip.layer().setShadowRadius_(6.0)
            pip.layer().setShadowOffset_((0, 0))
            pip.layer().setShadowColor_(
                CGColorCreateGenericRGB(0.45, 0.75, 1.0, 1.0)
            )
        except Exception:
            pass
    pill.addSubview_(pip)

    label = NSTextField.alloc().initWithFrame_(NSMakeRect(30, 8, w - 46, h - 16))
    label.setStringValue_("Agent controlling")
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setAlignment_(NSCenterTextAlignment)
    try:
        label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(0.97, 0.95))
        label.setFont_(NSFont.systemFontOfSize_weight_(12.5, 0.25))
    except Exception:
        try:
            label.setTextColor_(NSColor.whiteColor())
            label.setFont_(NSFont.systemFontOfSize_(12.5))
        except Exception:
            pass
    pill.addSubview_(label)
    root.addSubview_(pill)

    panel.setContentView_(root)
    panel.setFrameOrigin_((panel_x, panel_y))
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

        # Always rebuild banner layout (screen / dock can change)
        if _banner is not None:
            try:
                _banner.orderOut_(None)
            except Exception:
                pass
            globals()["_banner"] = None
        ban = _make_banner()
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
    if not enabled():
        return
    if not _active:
        show(x, y)
        return
    try:
        if _ring is None:
            _make_pointer_panel()
        _hide_system_cursor()
        _place_at_cg(float(x), float(y))
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
        _pump(n=4, seconds=0.015)
        time.sleep(0.06)
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
    _pump(n=3, seconds=0.01)


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


def _place_at_cg(cg_x: float, cg_y: float):
    if _ring is None:
        return
    ox, oy = _cg_to_panel_origin(cg_x, cg_y)
    _ring.setFrameOrigin_((ox, oy))
    _ring.orderFrontRegardless()


def _banner_geometry():
    from AppKit import NSScreen
    screen = NSScreen.mainScreen()
    if screen is None:
        return 500.0, 40.0, 220.0, 36.0
    vf = screen.visibleFrame()
    w, h = 220.0, 36.0
    x = vf.origin.x + (vf.size.width - w) / 2.0
    y = vf.origin.y + 28.0
    return x, y, w, h
