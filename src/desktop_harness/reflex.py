"""In-process see→act loop for games and other frame-timed work.

The chat loop cannot fly a plane. A model turn is hundreds of milliseconds
to several seconds; Vesper Cut wrecks in less than that. This module keeps
the *decision* next to the pixels and the keys — one process, no PNG, no
round-trip.

The model still chooses the policy (which pixels matter, which keys to
hold). The loop only executes it at display rate.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from . import capture as _capture
from . import input as _input
from . import presence as _presence
from . import windows as _windows


class ControlStopped(RuntimeError):
    pass


def grab_frame(app: str | None = None, window_id: int | None = None) -> dict[str, Any]:
    return _capture.grab_frame(app=app, window_id=window_id)


def pixel(frame: dict[str, Any], x: int, y: int) -> tuple[int, int, int]:
    return _capture.pixel(frame, x, y)


def keys_hold(names=None):
    return _input.keys_hold(names)


def key_down(name: str) -> str:
    return _input.key_down(name)


def key_up(name: str) -> str:
    return _input.key_up(name)


def release_keys() -> None:
    _input.release_keys()


def run_loop(
    step: Callable[[dict[str, Any]], Any],
    *,
    app: str | int | None = None,
    window_id: int | None = None,
    hz: float = 36.0,
    seconds: float = 12.0,
    max_frames: int | None = None,
    on_stop: str = "release",
) -> dict[str, Any]:
    """Call ``step(frame)`` at ``hz`` until time/frames/Stop/step says stop.

    Do **not** call ``screenshot()`` or write files inside ``step`` — that
    is the whole point. Disk PNG is 10–50× slower than ``grab_frame`` and
    will miss the frame you meant to act on.

    ``step`` receives a RAM frame from ``grab_frame``. Return values:

    - ``None`` / ``{}`` / truthy without ``stop`` → keep going
    - ``{"stop": True, ...}`` → end the loop (keys released)
    - raise ``ControlStopped`` if the user clicked the Working chip

    Presence is pumped so Stop still works. Keys this loop held are
    always released in ``finally``.
    """
    from .presence import ControlStopped as _CS

    hz = max(4.0, min(float(hz), 90.0))
    period = 1.0 / hz
    deadline = time.monotonic() + max(0.05, float(seconds))
    frames = 0
    last: Any = None
    t0 = time.monotonic()
    last_pump = 0.0
    wid = int(window_id) if window_id is not None else None
    app_name = None if isinstance(app, int) else app

    try:
        while time.monotonic() < deadline:
            if max_frames is not None and frames >= max_frames:
                break
            if _presence.stopped():
                raise _CS("user stopped desktop-harness from the Working chip")
            now = time.monotonic()
            if now - last_pump > 0.08:
                _presence.poll(deep=False)
                last_pump = now
                if _presence.stopped():
                    raise _CS("user stopped desktop-harness from the Working chip")

            if wid is None and app_name:
                try:
                    fr = _windows.window_frame(app_name)
                    wid = int(fr["id"])
                except Exception:
                    pass
            try:
                frame = _capture.grab_frame(app=app_name, window_id=wid)
            except RuntimeError:
                wid = None
                _windows._invalidate_window_cache()
                fr = _windows.window_frame(app_name)
                wid = int(fr["id"])
                frame = _capture.grab_frame(app=app_name, window_id=wid)
            frame["i"] = frames
            frame["t"] = now - t0
            last = step(frame)
            frames += 1
            if isinstance(last, dict) and last.get("stop"):
                break
            slept = time.monotonic() - now
            remain = period - slept
            if remain > 0.001:
                # Don't spin AppKit every frame — that is slower than the
                # game. Sleep, and let the 80ms poll above take Stop clicks.
                time.sleep(remain)
    finally:
        if on_stop == "release":
            _input.release_keys()

    elapsed = time.monotonic() - t0
    return {
        "frames": frames,
        "seconds": elapsed,
        "hz": (frames / elapsed) if elapsed > 0 else 0.0,
        "last": last,
    }
