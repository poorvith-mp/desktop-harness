"""Visible smoke demo — open TextEdit, move the real mouse, type a line."""
from __future__ import annotations

import time


def run_demo() -> int:
    from . import helpers as H

    print("desktop-harness live demo")
    print("Watch: soft blue ring + top pill 'Agent active — hands off'\n")

    print("1) frontmost:", H.frontmost_app())
    print("2) mouse at:", H.mouse_pos())
    H.enable_agent_cursor(True)

    print("3) open TextEdit")
    H.open_app("TextEdit")
    time.sleep(0.4)

    # New doc if needed
    H.hotkey("cmd", "n")
    time.sleep(0.35)

    wins = [w for w in H.list_windows() if w["app"] == "TextEdit"]
    if wins:
        w = wins[0]
        cx = w["x"] + w["w"] / 2
        cy = w["y"] + w["h"] / 2
        print(f"4) move mouse into TextEdit window ({cx:.0f},{cy:.0f})")
        H.move_to(cx, cy, duration=0.4)
        H.wiggle(amplitude=14, cycles=2, duration=0.4)
        H.click(cx, cy, duration=0.08)
    else:
        print("4) no TextEdit window bounds — typing anyway")

    msg = "desktop-harness works — built with Grok Build"
    print(f"5) type: {msg!r}")
    H.type_text(msg)
    time.sleep(0.6)

    print("6) labels sample:")
    for line in H.labels("TextEdit")[:8]:
        print("  ", line)

    H.hide_agent_presence()
    print("\nDemo complete. Presence hidden. TextEdit left open.")
    return 0
