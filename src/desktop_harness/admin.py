"""desktop-harness --doctor"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def run_doctor() -> int:
    print("desktop-harness doctor\n")
    fails = 0

    def check(name: str, ok: bool, detail: str = ""):
        nonlocal fails
        status = "PASS" if ok else "FAIL"
        if not ok:
            fails += 1
        extra = f" — {detail}" if detail else ""
        print(f"  [{status}] {name}{extra}")

    # pyobjc
    try:
        import Quartz  # noqa: F401
        import AppKit  # noqa: F401
        from ApplicationServices import AXIsProcessTrusted  # noqa: F401
        check("pyobjc frameworks (Quartz, AppKit, ApplicationServices)", True)
    except Exception as e:
        check("pyobjc frameworks", False, str(e))
        print("\ninstall deps in the project venv, then re-run --doctor")
        return 1

    # Accessibility
    try:
        from ApplicationServices import AXIsProcessTrusted
        trusted = bool(AXIsProcessTrusted())
        check("Accessibility permission (AX + input)", trusted,
              "ok" if trusted else "System Settings → Privacy & Security → Accessibility")
    except Exception as e:
        check("Accessibility permission", False, str(e))

    # Screen Recording — try a tiny capture
    try:
        from . import capture as cap
        path = cap.screenshot(path=Path(tempfile.gettempdir()) / "dh-doctor.png")
        size = Path(path).stat().st_size
        check("Screen Recording (window/display capture)", size > 1000,
              f"{size} bytes" if size > 1000 else "empty capture — grant Screen Recording")
    except Exception as e:
        check("Screen Recording (window/display capture)", False, str(e))

    # Live AX
    try:
        from . import windows, ax
        front = windows.frontmost_app()
        if front:
            nodes = ax.ax_snapshot(front["pid"], max_nodes=20, interactive_only=True)
            check("AX snapshot (frontmost app)", len(nodes) > 0,
                  f"{front['name']}: {len(nodes)} nodes")
        else:
            check("AX snapshot (frontmost app)", False, "no frontmost app")
    except Exception as e:
        check("AX snapshot (frontmost app)", False, str(e))

    # Window list
    try:
        from . import windows
        wins = windows.list_windows()
        check("window list", len(wins) > 0, f"{len(wins)} on-screen windows")
    except Exception as e:
        check("window list", False, str(e))

    print()
    if fails:
        print(f"{fails} check(s) failed. Fix the first FAIL; later ones often depend on it.")
        print("Open panes:")
        print('  open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"')
        print('  open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"')
        print("After granting Screen Recording, fully quit and restart the terminal / Grok.")
        return 1
    print("all clear — AX-first desktop control is ready.")
    print("tip: prefer labels / find / click_text over ax_snapshot or screenshot loops.")
    return 0
