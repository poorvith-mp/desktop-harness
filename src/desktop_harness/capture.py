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

    This is the fast eye when the next frame is the action.
    ``screenshot()`` still exists when you need a file for a model to read.

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
    ox = oy = 0.0
    if wid is not None:
        try:
            for win in winmod.list_windows(on_screen_only=False):
                if int(win.get("id") or 0) == int(wid):
                    ox = float(win.get("x") or 0)
                    oy = float(win.get("y") or 0)
                    break
        except Exception:
            pass
    return {
        "w": w,
        "h": h,
        "bpr": bpr,
        "data": data,
        "window_id": int(wid) if wid is not None else None,
        "x": ox,
        "y": oy,
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
    """RGB sample. Clamped. Fast enough for sparse scans."""
    w = int(frame["w"])
    h = int(frame["h"])
    if w <= 0 or h <= 0:
        return (0, 0, 0)
    x = 0 if x < 0 else (w - 1 if x >= w else x)
    y = 0 if y < 0 else (h - 1 if y >= h else y)
    i = y * int(frame["bpr"]) + x * 4
    d = frame["data"]
    return (d[i], d[i + 1], d[i + 2])


def color_near(
    rgb: tuple[int, int, int] | list[int],
    target: tuple[int, int, int] | list[int],
    tol: int = 28,
) -> bool:
    """True if each channel is within ``tol`` of ``target``. App-agnostic."""
    return (
        abs(int(rgb[0]) - int(target[0])) <= tol
        and abs(int(rgb[1]) - int(target[1])) <= tol
        and abs(int(rgb[2]) - int(target[2])) <= tol
    )


def _box(frame: dict[str, Any], region) -> tuple[int, int, int, int]:
    """Normalize ``(x, y, w, h)`` to integer x0,y0,x1,y1.

    Values in ``0..1`` on all four slots are fractions of the frame.
    One convention — same as ``window_frame`` — not two.
    """
    w = int(frame["w"])
    h = int(frame["h"])
    if not region:
        return 0, 0, w, h
    x, y, rw, rh = (float(region[0]), float(region[1]),
                     float(region[2]), float(region[3]))
    if 0 <= x <= 1 and 0 <= y <= 1 and 0 < rw <= 1 and 0 < rh <= 1:
        x, y, rw, rh = x * w, y * h, rw * w, rh * h
    x0 = max(0, min(w, int(x)))
    y0 = max(0, min(h, int(y)))
    x1 = max(x0 + 1, min(w, int(x + rw)))
    y1 = max(y0 + 1, min(h, int(y + rh)))
    return x0, y0, x1, y1


def find_color(
    frame: dict[str, Any],
    rgb: tuple[int, int, int] | list[int],
    *,
    tol: int = 28,
    region=None,
    step: int = 3,
    limit: int = 80,
) -> dict[str, Any] | None:
    """Centroid of pixels near ``rgb``. None if nothing matches.

    Works on any window: a button, a playhead, a sprite, a highlight.
    ``region`` limits the search (px or 0–1 fractions).
    """
    x0, y0, x1, y1 = _box(frame, region)
    step = max(1, int(step))
    data = frame["data"]
    bpr = int(frame["bpr"])
    tr, tg, tb = int(rgb[0]), int(rgb[1]), int(rgb[2])
    xs: list[int] = []
    ys: list[int] = []
    for y in range(y0, y1, step):
        row = y * bpr
        for x in range(x0, x1, step):
            i = row + x * 4
            if (abs(data[i] - tr) <= tol
                    and abs(data[i + 1] - tg) <= tol
                    and abs(data[i + 2] - tb) <= tol):
                xs.append(x)
                ys.append(y)
                if len(xs) >= limit:
                    break
        if len(xs) >= limit:
            break
    if not xs:
        return None
    xs.sort()
    ys.sort()
    n = len(xs)
    return {
        "x": xs[n // 2],
        "y": ys[n // 2],
        "n": n,
        "x0": xs[0],
        "y0": ys[0],
        "x1": xs[-1],
        "y1": ys[-1],
    }


def count_color(
    frame: dict[str, Any],
    rgb: tuple[int, int, int] | list[int],
    *,
    tol: int = 28,
    region=None,
    step: int = 3,
    stop_at: int | None = None,
) -> int:
    """How many sampled pixels match ``rgb``. Cheap 'is this UI up?' test."""
    x0, y0, x1, y1 = _box(frame, region)
    step = max(1, int(step))
    data = frame["data"]
    bpr = int(frame["bpr"])
    tr, tg, tb = int(rgb[0]), int(rgb[1]), int(rgb[2])
    n = 0
    for y in range(y0, y1, step):
        row = y * bpr
        for x in range(x0, x1, step):
            i = row + x * 4
            if (abs(data[i] - tr) <= tol
                    and abs(data[i + 1] - tg) <= tol
                    and abs(data[i + 2] - tb) <= tol):
                n += 1
                if stop_at is not None and n >= stop_at:
                    return n
    return n


def scan_column(
    frame: dict[str, Any],
    x: int,
    rgb: tuple[int, int, int] | list[int] | None = None,
    *,
    tol: int = 28,
    y0: int | None = None,
    y1: int | None = None,
    step: int = 2,
    pred=None,
) -> list[dict[str, int]]:
    """Vertical runs where the pixel matches ``rgb`` (or ``pred(r,g,b)``).

    Returns ``[{y0, y1, h}, ...]``. Use this for a playhead, a gap, a
    scrollbar thumb, a timeline — anything that is a band of color.
    """
    w = int(frame["w"])
    h = int(frame["h"])
    x = 0 if x < 0 else (w - 1 if x >= w else int(x))
    ya = 0 if y0 is None else max(0, int(y0))
    yb = h if y1 is None else min(h, int(y1))
    step = max(1, int(step))
    data = frame["data"]
    bpr = int(frame["bpr"])
    runs: list[dict[str, int]] = []
    start = None
    last = ya
    if pred is None:
        if rgb is None:
            raise ValueError("scan_column needs rgb= or pred=")
        tr, tg, tb = int(rgb[0]), int(rgb[1]), int(rgb[2])

        def pred(r, g, b, _tr=tr, _tg=tg, _tb=tb, _tol=tol):
            return (abs(r - _tr) <= _tol
                    and abs(g - _tg) <= _tol
                    and abs(b - _tb) <= _tol)

    for y in range(ya, yb, step):
        i = y * bpr + x * 4
        ok = pred(data[i], data[i + 1], data[i + 2])
        if ok:
            if start is None:
                start = y
            last = y
        elif start is not None:
            runs.append({"y0": start, "y1": last, "h": last - start})
            start = None
    if start is not None:
        runs.append({"y0": start, "y1": last, "h": last - start})
    return runs


def scan_row(
    frame: dict[str, Any],
    y: int,
    rgb: tuple[int, int, int] | list[int] | None = None,
    *,
    tol: int = 28,
    x0: int | None = None,
    x1: int | None = None,
    step: int = 2,
    pred=None,
) -> list[dict[str, int]]:
    """Horizontal runs. Same contract as ``scan_column``."""
    w = int(frame["w"])
    h = int(frame["h"])
    y = 0 if y < 0 else (h - 1 if y >= h else int(y))
    xa = 0 if x0 is None else max(0, int(x0))
    xb = w if x1 is None else min(w, int(x1))
    step = max(1, int(step))
    data = frame["data"]
    bpr = int(frame["bpr"])
    runs: list[dict[str, int]] = []
    start = None
    last = xa
    if pred is None:
        if rgb is None:
            raise ValueError("scan_row needs rgb= or pred=")
        tr, tg, tb = int(rgb[0]), int(rgb[1]), int(rgb[2])

        def pred(r, g, b, _tr=tr, _tg=tg, _tb=tb, _tol=tol):
            return (abs(r - _tr) <= _tol
                    and abs(g - _tg) <= _tol
                    and abs(b - _tb) <= _tol)

    row = y * bpr
    for x in range(xa, xb, step):
        i = row + x * 4
        ok = pred(data[i], data[i + 1], data[i + 2])
        if ok:
            if start is None:
                start = x
            last = x
        elif start is not None:
            runs.append({"x0": start, "x1": last, "w": last - start})
            start = None
    if start is not None:
        runs.append({"x0": start, "x1": last, "w": last - start})
    return runs


def largest_run(runs: list[dict[str, int]]) -> dict[str, int] | None:
    """Tallest column run (``h``) or widest row run (``w``)."""
    if not runs:
        return None
    return max(runs, key=lambda r: int(r.get("h") or r.get("w") or 0))


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
