"""Agent presence — one real cursor + synced glow (no second arrow).

Design rules (from observe loop):
  - NEVER draw a second pointer shape (dual-cursor lag is unusable)
  - System cursor stays; we only draw a soft HALO locked to the warp target
  - Move = cool blue glow; click = brief red flash, then blue again
  - Bottom neon bar fully above Dock (window level + margin + pad math)

DH_PRESENCE=0 disables everything.
"""
from __future__ import annotations

import os
import time

_halo = None
_banner = None
_app = None
_active = False
_last_cg: tuple[float, float] | None = None
_mode = "blue"  # blue | red

# IMPORTANT — main thread only. AppKit asserts on non-main-thread window
# calls and hard-aborts the whole process (SIGABRT, unrecoverable, no
# Python exception to catch) — verified by trying a background "keepalive"
# thread here and watching it crash desktop-harness every single run. Do
# not reach for threading to solve idle-persistence; use keep_alive()
# below to pump in small increments from whatever thread is already
# calling into presence (which must be the main thread).

# Halo canvas — circle centered on cursor tip
_SIZE = 40.0
_FLASH = 48.0


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


def _style_panel(panel, boost: int = 0):
    from AppKit import NSColor, NSPopUpMenuWindowLevel
    try:
        # Above Dock / most chrome
        panel.setLevel_(int(NSPopUpMenuWindowLevel) + 8 + boost)
    except Exception:
        panel.setLevel_(100 + boost)
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


def _cg_to_center_origin(cg_x: float, cg_y: float, size: float) -> tuple[float, float]:
    """Center a size×size panel on the CGEvent hot-spot (cursor tip)."""
    from AppKit import NSScreen
    main = NSScreen.mainScreen()
    if main is None:
        return cg_x - size / 2, -cg_y - size / 2
    mf = main.frame()
    # CG: top-left of primary, y down → Cocoa: bottom-left, y up
    cocoa_cx = float(mf.origin.x) + float(cg_x)
    cocoa_cy = float(mf.origin.y) + float(mf.size.height) - float(cg_y)
    return cocoa_cx - size / 2.0, cocoa_cy - size / 2.0


class _HaloView:
    """Soft disc under the real system cursor — not a second arrow."""
    _cls = None

    @classmethod
    def view_class(cls):
        if cls._cls is not None:
            return cls._cls
        from AppKit import NSView

        class HaloView(NSView):
            mode = "blue"

            def isFlipped(self):
                return False

            def drawRect_(self, rect):
                from AppKit import NSBezierPath, NSColor, NSRectFill

                NSColor.clearColor().set()
                NSRectFill(self.bounds())

                b = self.bounds()
                cx = b.size.width / 2.0
                cy = b.size.height / 2.0
                # Leave a clear hole in the center so the real cursor tip stays sharp
                outer_r = min(b.size.width, b.size.height) / 2.0 - 1.0
                inner_r = 5.0

                if self.mode == "red":
                    # Click: soft warm red ring
                    rings = (
                        (outer_r, 0.98, 0.30, 0.25, 0.22),
                        (outer_r * 0.72, 0.98, 0.35, 0.28, 0.16),
                        (outer_r * 0.48, 1.0, 0.45, 0.35, 0.10),
                    )
                else:
                    # Move/idle: soft blue ring
                    rings = (
                        (outer_r, 0.30, 0.55, 1.0, 0.20),
                        (outer_r * 0.72, 0.35, 0.60, 1.0, 0.14),
                        (outer_r * 0.48, 0.45, 0.70, 1.0, 0.09),
                    )

                for r, rr, gg, bb, aa in rings:
                    path = NSBezierPath.bezierPath()
                    path.appendBezierPathWithOvalInRect_(
                        ((cx - r, cy - r), (2 * r, 2 * r))
                    )
                    # punch hole
                    hole = NSBezierPath.bezierPath()
                    hole.appendBezierPathWithOvalInRect_(
                        ((cx - inner_r, cy - inner_r), (2 * inner_r, 2 * inner_r))
                    )
                    path.appendBezierPath_(hole)
                    try:
                        path.setWindingRule_(1)  # even-odd
                    except Exception:
                        pass
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        rr, gg, bb, aa
                    ).set()
                    path.fill()

                # Thin bright rim (subtle neon edge)
                rim = NSBezierPath.bezierPath()
                rim.appendBezierPathWithOvalInRect_(
                    ((cx - outer_r + 0.5, cy - outer_r + 0.5),
                     (2 * (outer_r - 0.5), 2 * (outer_r - 0.5)))
                )
                rim.setLineWidth_(1.2)
                if self.mode == "red":
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        1.0, 0.40, 0.30, 0.55
                    ).set()
                else:
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        0.45, 0.75, 1.0, 0.45
                    ).set()
                rim.stroke()

        cls._cls = HaloView
        return cls._cls


def _make_halo(size: float | None = None):
    global _halo
    from AppKit import NSMakeRect, NSPanel, NSWindowStyleMaskBorderless
    size = size or _SIZE
    _ensure_app()
    if _halo is None:
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, size, size),
            NSWindowStyleMaskBorderless,
            2,
            False,
        )
        _style_panel(panel)
        _halo = panel
    View = _HaloView.view_class()
    view = View.alloc().initWithFrame_(NSMakeRect(0, 0, size, size))
    view.mode = _mode
    _halo.setContentView_(view)
    from AppKit import NSMakeRect as R
    # keep size
    o = _halo.frame().origin
    _halo.setFrame_display_(R(o.x, o.y, size, size), False)
    return _halo


def _place_halo(cg_x: float, cg_y: float, size: float | None = None):
    global _last_cg
    size = size or _SIZE
    if _halo is None:
        _make_halo(size)
    ox, oy = _cg_to_center_origin(cg_x, cg_y, size)
    from AppKit import NSMakeRect
    _halo.setFrame_display_(NSMakeRect(ox, oy, size, size), False)
    _halo.orderFrontRegardless()
    if _banner is not None:
        _banner.orderFrontRegardless()
    _last_cg = (cg_x, cg_y)
    # Window-server frame/order commands only flush when the accessory
    # app's run loop actually spins. This app never calls NSApp.run(), so
    # without a pump here the overlay silently stops updating the instant
    # focus moves to another app (e.g. any click that lands elsewhere) —
    # every high-frequency caller (move/drag) funnels through this
    # function, so pumping here covers all of them from one place.
    # Idle gaps between calls are covered by keep_alive(), not here.
    _pump(n=2, seconds=0.004)


def _make_banner():
    global _banner
    from AppKit import (
        NSColor, NSMakeRect, NSPanel, NSTextField, NSFont, NSView,
        NSWindowStyleMaskBorderless, NSCenterTextAlignment,
    )
    from Quartz import CGColorCreateGenericRGB

    _ensure_app()
    px, py, pw, ph, w, h, pad = _banner_layout()
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, pw, ph),
        NSWindowStyleMaskBorderless,
        2,
        False,
    )
    _style_panel(panel, boost=2)

    root = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, pw, ph))
    root.setWantsLayer_(True)
    if root.layer() is not None:
        root.layer().setBackgroundColor_(CGColorCreateGenericRGB(0, 0, 0, 0))

    # Neon wash under pill
    halo = NSView.alloc().initWithFrame_(
        NSMakeRect(pad - 5, pad - 5, w + 10, h + 10)
    )
    halo.setWantsLayer_(True)
    if halo.layer() is not None:
        halo.layer().setCornerRadius_((h + 10) / 2.0)
        halo.layer().setBackgroundColor_(
            CGColorCreateGenericRGB(0.18, 0.48, 1.0, 0.18)
        )
        try:
            halo.layer().setShadowOpacity_(1.0)
            halo.layer().setShadowRadius_(18.0)
            halo.layer().setShadowOffset_((0, 0))
            halo.layer().setShadowColor_(
                CGColorCreateGenericRGB(0.30, 0.60, 1.0, 1.0)
            )
        except Exception:
            pass
    root.addSubview_(halo)

    pill = NSView.alloc().initWithFrame_(NSMakeRect(pad, pad, w, h))
    pill.setWantsLayer_(True)
    if pill.layer() is not None:
        pill.layer().setCornerRadius_(h / 2.0)
        pill.layer().setBackgroundColor_(
            CGColorCreateGenericRGB(0.05, 0.06, 0.09, 0.92)
        )
        pill.layer().setBorderWidth_(1.6)
        pill.layer().setBorderColor_(
            CGColorCreateGenericRGB(0.40, 0.75, 1.0, 0.98)
        )
        try:
            pill.layer().setShadowOpacity_(1.0)
            pill.layer().setShadowRadius_(14.0)
            pill.layer().setShadowOffset_((0, 0))
            pill.layer().setShadowColor_(
                CGColorCreateGenericRGB(0.35, 0.70, 1.0, 1.0)
            )
        except Exception:
            pass

    pip = NSView.alloc().initWithFrame_(NSMakeRect(16, (h - 7) / 2.0, 7, 7))
    pip.setWantsLayer_(True)
    if pip.layer() is not None:
        pip.layer().setCornerRadius_(3.5)
        pip.layer().setBackgroundColor_(
            CGColorCreateGenericRGB(0.50, 0.80, 1.0, 1.0)
        )
        try:
            pip.layer().setShadowOpacity_(1.0)
            pip.layer().setShadowRadius_(6.0)
            pip.layer().setShadowOffset_((0, 0))
            pip.layer().setShadowColor_(
                CGColorCreateGenericRGB(0.4, 0.75, 1.0, 1.0)
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
    panel.setFrame_display_(NSMakeRect(px, py, pw, ph), True)
    _banner = panel
    return panel


def _banner_layout():
    from AppKit import NSScreen
    screen = NSScreen.mainScreen()
    pad = 20.0
    w, h = 252.0, 38.0
    if screen is None:
        return 400.0, 90.0, w + 2 * pad, h + 2 * pad, w, h, pad
    vf = screen.visibleFrame()
    margin = pad + 64.0  # fully clear of Dock
    pill_x = vf.origin.x + (vf.size.width - w) / 2.0
    pill_y = vf.origin.y + margin
    return (
        pill_x - pad,
        pill_y - pad,
        w + 2 * pad,
        h + 2 * pad,
        w, h, pad,
    )


def keep_alive(seconds: float) -> None:
    """Hold presence visible through an idle wait — call this instead of
    time.sleep() while an action script pauses with presence active.

    Chunks the wait and re-asserts ordering + pumps between chunks, all on
    the calling (main) thread. A background thread sounds like the right
    tool for "keep something alive while I sleep," and an earlier version
    of this file did exactly that — it crashed the whole process every
    time (AppKit hard-aborts on window calls from a non-main thread; no
    Python exception, nothing to catch). This is the safe version: same
    effect, zero threads.
    """
    if not _active:
        time.sleep(max(0.0, seconds))
        return
    remaining = max(0.0, seconds)
    step = 0.12
    while remaining > 0:
        chunk = min(step, remaining)
        time.sleep(chunk)
        remaining -= chunk
        try:
            if _halo is not None:
                _halo.orderFrontRegardless()
            if _banner is not None:
                _banner.orderFrontRegardless()
            _pump(n=1, seconds=0.003)
        except Exception:
            pass


def show(x: float | None = None, y: float | None = None) -> bool:
    global _active, _mode
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

        # ONE cursor: keep system pointer; halo only
        _mode = "blue"
        _make_halo(_SIZE)
        _set_halo_mode("blue")

        global _banner
        if _banner is not None:
            try:
                _banner.orderOut_(None)
            except Exception:
                pass
            _banner = None
        ban = _make_banner()
        ban.orderFrontRegardless()

        _active = True
        _place_halo(x, y, _SIZE)
        _pump(n=10, seconds=0.03)
        return True
    except Exception as e:
        try:
            print(f"[presence] show failed: {type(e).__name__}: {e}")
        except Exception:
            pass
        return False


def _set_halo_mode(mode: str):
    global _mode
    _mode = mode
    if _halo is None:
        return
    view = _halo.contentView()
    if view is not None and hasattr(view, "mode"):
        view.mode = "red" if mode == "red" else "blue"
        view.setNeedsDisplay_(True)


def move(x: float, y: float) -> None:
    """Warp already done by input.py; place halo on the SAME cg coords — no lag chase."""
    if not enabled():
        return
    if not _active:
        show(x, y)
        return
    try:
        if _halo is None:
            _make_halo(_SIZE)
        if _mode != "blue":
            _set_halo_mode("blue")
        # Same coordinates as CGWarp in the same call stack → synced
        _place_halo(float(x), float(y), _SIZE)
    except Exception:
        pass


def click_flash(x: float, y: float) -> None:
    """Subtle red flash on click, then back to blue — same center, no second cursor."""
    if not enabled():
        return
    try:
        if not _active:
            show(x, y)
        _set_halo_mode("red")
        _place_halo(float(x), float(y), _FLASH)
        _pump(n=4, seconds=0.015)
        time.sleep(0.07)
        _set_halo_mode("blue")
        _place_halo(float(x), float(y), _SIZE)
    except Exception:
        pass


def hide() -> None:
    global _halo, _banner, _active, _last_cg
    _active = False
    try:
        if _halo is not None:
            _halo.orderOut_(None)
            _halo = None
        if _banner is not None:
            _banner.orderOut_(None)
            _banner = None
    except Exception:
        pass
    _last_cg = None
    _pump(n=3, seconds=0.01)


def ensure() -> None:
    if not enabled():
        return
    if _active:
        return
    show()


def active() -> bool:
    """True if the halo/banner are currently shown.

    Lets a caller outside this module (the daemon's idle loop) check state
    without reaching into the private `_active` global directly.
    """
    return _active


def pulse():
    import Quartz
    ev = Quartz.CGEventCreate(None)
    p = Quartz.CGEventGetLocation(ev)
    click_flash(float(p.x), float(p.y))


# --- wire input.py overlay API ---
def set_overlay(_):
    pass
