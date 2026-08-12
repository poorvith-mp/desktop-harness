"""Window / display capture — pixel fallback when AX is not enough."""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

import Quartz
from AppKit import NSBitmapImageRep, NSImage

from . import windows as winmod

TMP = Path(tempfile.gettempdir()) / "desktop-harness"
TMP.mkdir(exist_ok=True)


def _save_cgimage(image, path: Path) -> Path:
    if image is None:
        raise RuntimeError("capture returned no image")
    # Wrap CGImage in NSBitmapImageRep → PNG
    rep = NSBitmapImageRep.alloc().initWithCGImage_(image)
    data = rep.representationUsingType_properties_(
        4, None)  # NSBitmapImageFileTypePNG = 4
    if data is None:
        raise RuntimeError("failed to encode PNG")
    path = Path(path)
    path.write_bytes(bytes(data))
    return path


def grab_frame(
    app: str | None = None,
    window_id: int | None = None,
) -> dict[str, Any]:
    """Capture a window into RAM — no PNG, no disk.

    This is the fast eye for games and anything that must act on the
    *current* frame. ``screenshot()`` still exists when you need a file
    for a model to read.

    Returns ``{w, h, bpr, data, window_id}`` where ``data`` is RGBA bytes
    (4 bytes/pixel, ``bpr`` may include row padding).
    """
    from . import safety as _safety
    if app:
        _safety.check_app_allowed(app)
    else:
        _safety.check_frontmost_allowed()
    wid = window_id
    if wid is None and app:
        try:
            fr = winmod.window_frame(app)
            wid = fr.get("id")
        except RuntimeError:
            wid = None
        if wid is None:
            raise RuntimeError(f"no on-screen window for app={app!r}")
    image = None
    for attempt in range(3):
        if wid is not None:
            image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectNull,
                Quartz.kCGWindowListOptionIncludingWindow,
                int(wid),
                Quartz.kCGWindowImageBoundsIgnoreFraming
                | Quartz.kCGWindowImageNominalResolution,
            )
        if image is None:
            bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
            image = Quartz.CGWindowListCreateImage(
                bounds,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageNominalResolution,
            )
            wid = None
        if image is not None:
            break
        time.sleep(0.02)
        if app:
            try:
                winmod._invalidate_window_cache()
                fr = winmod.window_frame(app)
                wid = fr.get("id")
            except Exception:
                pass
    if image is None:
        raise RuntimeError("grab_frame returned no image")
    w = int(Quartz.CGImageGetWidth(image))
    h = int(Quartz.CGImageGetHeight(image))
    bpr = int(Quartz.CGImageGetBytesPerRow(image))
    provider = Quartz.CGImageGetDataProvider(image)
    raw = Quartz.CGDataProviderCopyData(provider)
    data = bytes(raw)
    return {
        "w": w,
        "h": h,
        "bpr": bpr,
        "data": data,
        "window_id": int(wid) if wid is not None else None,
    }


def frame_digest(frame: dict[str, Any], samples: int = 24) -> int:
    """Tiny hash of a few pixels — detect a frozen / paused frame cheaply."""
    w = int(frame["w"])
    h = int(frame["h"])
    if w < 2 or h < 2:
        return 0
    d = frame["data"]
    bpr = int(frame["bpr"])
    acc = w * 10007 + h
    n = max(6, int(samples))
    for i in range(n):
        x = 1 + (i * 47) % (w - 2)
        y = 1 + (i * 89) % (h - 2)
        off = y * bpr + x * 4
        acc = (acc * 33 + d[off] + d[off + 1] * 3 + d[off + 2] * 7) & 0xFFFFFFFF
    return acc


def pixel(frame: dict[str, Any], x: int, y: int) -> tuple[int, int, int]:
    """RGBA sample. Clamped. Fast enough for sparse scans."""
    w = int(frame["w"])
    h = int(frame["h"])
    if w <= 0 or h <= 0:
        return (0, 0, 0)
    x = 0 if x < 0 else (w - 1 if x >= w else x)
    y = 0 if y < 0 else (h - 1 if y >= h else y)
    i = y * int(frame["bpr"]) + x * 4
    d = frame["data"]
    return (d[i], d[i + 1], d[i + 2])


def screenshot(
    app: str | None = None,
    window_id: int | None = None,
    path: str | Path | None = None,
) -> str:
    """Capture a window (preferred) or the main display.

    Returns path to PNG. Prefer app/window scope over full desktop.
    """
    from . import safety as _safety
    if app:
        _safety.check_app_allowed(app)
    else:
        # Unscoped (window_id given, or full display) — a targeted app
        # name already got checked above; an untargeted capture can still
        # grab a password manager's visible contents if it's frontmost,
        # same risk class as the click/type gate already covers.
        _safety.check_frontmost_allowed()
    if path is None:
        # Unique per call — concurrent agent steps (or two calls in the
        # same script) used to clobber a single shared capture.png.
        path = TMP / f"capture-{os.getpid()}-{time.time_ns()}.png"
    path = Path(path)
    # Reuse the RAM grab (retries + owner/pid). Then encode PNG once.
    frame = grab_frame(app=app, window_id=window_id)
    wid = frame.get("window_id")
    # Rebuild a CGImage from the already-captured bytes only if we still
    # have the live window; cheaper path: recapture is already done —
    # write via NSBitmapImageRep from a fresh CG grab of the same id.
    image = None
    if wid is not None:
        image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            int(wid),
            Quartz.kCGWindowImageBoundsIgnoreFraming
            | Quartz.kCGWindowImageNominalResolution,
        )
    if image is None:
        bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        image = Quartz.CGWindowListCreateImage(
            bounds,
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
            Quartz.kCGWindowImageNominalResolution,
        )
    _save_cgimage(image, path)
    _safety.audit("screenshot", {"app": app, "window_id": wid, "path": str(path)})
    return str(path)


def window_info(app: str | None = None) -> dict[str, Any] | None:
    if app:
        try:
            return winmod.window_frame(app)
        except RuntimeError:
            return None
    wins = winmod.list_windows()
    return wins[0] if wins else None
