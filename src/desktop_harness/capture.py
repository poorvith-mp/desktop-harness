"""Window / display capture — pixel fallback when AX is not enough."""
from __future__ import annotations

import tempfile
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


def screenshot(
    app: str | None = None,
    window_id: int | None = None,
    path: str | Path | None = None,
) -> str:
    """Capture a window (preferred) or the main display.

    Returns path to PNG. Prefer app/window scope over full desktop.
    """
    path = Path(path or TMP / "capture.png")
    wid = window_id
    if wid is None and app:
        for w in winmod.list_windows():
            if app.lower() in w["app"].lower() or app.lower() in (w["title"] or "").lower():
                wid = w["id"]
                break
        if wid is None:
            raise RuntimeError(f"no on-screen window for app={app!r}")
    if wid is not None:
        image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            wid,
            Quartz.kCGWindowImageBoundsIgnoreFraming
            | Quartz.kCGWindowImageNominalResolution,
        )
    else:
        # main display
        bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        image = Quartz.CGWindowListCreateImage(
            bounds,
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
            Quartz.kCGWindowImageNominalResolution,
        )
    _save_cgimage(image, path)
    return str(path)


def window_info(app: str | None = None) -> dict[str, Any] | None:
    if app:
        for w in winmod.list_windows():
            if app.lower() in w["app"].lower():
                return w
        return None
    wins = winmod.list_windows()
    return wins[0] if wins else None
