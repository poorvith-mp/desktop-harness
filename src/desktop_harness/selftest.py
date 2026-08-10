"""Non-destructive self-test for release confidence."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable


def run_selftest() -> int:
    from . import helpers as H
    from .admin import run_doctor
    from .ax import frame_on_screen

    print("desktop-harness selftest\n")
    fails = 0

    def check(name: str, fn: Callable[[], None]):
        nonlocal fails
        t0 = time.time()
        try:
            fn()
            ms = int((time.time() - t0) * 1000)
            print(f"  [PASS] {name} ({ms}ms)")
        except Exception as e:
            fails += 1
            print(f"  [FAIL] {name}: {type(e).__name__}: {e}")

    print("— doctor —")
    doc = run_doctor()
    if doc != 0:
        fails += 1
        print("  (doctor reported failures)\n")
    else:
        print()

    print("— core —")

    def _apps():
        assert len(H.list_apps()) >= 1

    def _wins():
        assert len(H.list_windows()) >= 1

    def _front():
        assert H.frontmost_app() is not None

    def _labels():
        assert isinstance(H.labels(limit=5), list)

    def _mouse():
        p = H.mouse_pos()
        assert "x" in p and "y" in p

    def _move_restore():
        p0 = H.mouse_pos()
        H.move_to(p0["x"] + 30, p0["y"] + 20, duration=0.05)
        H.move_to(p0["x"], p0["y"], duration=0.05)
        p1 = H.mouse_pos()
        assert abs(p1["x"] - p0["x"]) < 12 and abs(p1["y"] - p0["y"]) < 12

    def _shot():
        path = H.screenshot()
        assert Path(path).stat().st_size > 1000

    def _media_api():
        st = H.media_transport()
        assert st["state"] in ("playing", "paused", "unknown")

    def _frame_filter():
        assert frame_on_screen({"x": 100, "y": 100, "w": 50, "h": 50})
        assert not frame_on_screen({"x": 50, "y": 50, "w": 0, "h": 10})
        assert not frame_on_screen({"x": 100, "y": 9000, "w": 40, "h": 40})

    for name, fn in [
        ("list_apps", _apps),
        ("list_windows", _wins),
        ("frontmost_app", _front),
        ("labels", _labels),
        ("mouse_pos", _mouse),
        ("move_to restore", _move_restore),
        ("screenshot", _shot),
        ("media_transport api", _media_api),
        ("frame_on_screen filter", _frame_filter),
    ]:
        check(name, fn)

    print("\n— light GUI (TextEdit) —")

    def _textedit():
        H.open_app("TextEdit")
        # Terminal/agent hosts often steal focus back — re-activate until front
        deadline = time.time() + 3.0
        while time.time() < deadline:
            front = H.frontmost_app()
            if front and front.get("name") == "TextEdit":
                break
            H.activate("TextEdit", wait=0.15)
            time.sleep(0.1)
        front = H.frontmost_app()
        assert front and front.get("name") == "TextEdit", front
        H.hotkey("cmd", "n")
        time.sleep(0.3)
        # focus again after new window
        H.activate("TextEdit", wait=0.15)
        token = f"dh-selftest-{int(time.time())}"
        H.type_text(token)
        time.sleep(0.2)
        front = H.frontmost_app()
        assert front and front.get("name") == "TextEdit", front
        print(f"      typed {token!r} into TextEdit (left open)")

    check("TextEdit open+type", _textedit)

    print("\n— daemon —")

    def _daemon_roundtrip():
        import os
        import subprocess
        import sys
        from . import daemon as d
        # stop then bg start
        if d.is_running():
            try:
                d.client_request({"op": "quit"}, timeout=2)
            except Exception:
                pass
            time.sleep(0.2)
        # start bg via CLI
        subprocess.check_call(
            [sys.executable, "-m", "desktop_harness.run", "daemon", "start", "--bg"],
            env={**os.environ, "PATH": os.environ.get("PATH", "")},
        )
        assert d.is_running(), "daemon not running after --bg"
        resp = d.exec_via_daemon("print(1+1)")
        assert resp.get("ok") and "2" in (resp.get("stdout") or "")
        d.client_request({"op": "quit"}, timeout=2)

    check("daemon bg + exec", _daemon_roundtrip)

    print()
    if fails:
        print(f"{fails} failure(s). Fix before release.")
        return 1
    print("all selftests passed.")
    return 0
