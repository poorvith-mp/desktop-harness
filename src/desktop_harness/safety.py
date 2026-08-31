"""Safety gates for real-desktop control.

Runtime blocks:
  - Opening / focusing apps with sensitive name or bundle substrings
    (unless DH_ALLOW_SENSITIVE=1)
  - Mutating actions while a sensitive app is frontmost
    (unless DH_ALLOW_SENSITIVE=1)

DH_SAFE=1 (default) is also agent policy documentation: no shell escape
helpers ship in this package.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_SENSITIVE_NAME_SUBSTR = (
    # "password" (not "1password") so Apple's own Passwords.app matches too —
    # "1password" is not a substring of "Passwords".
    "password", "bitwarden", "keychain", "lastpass", "keepass",
    "dashlane", "nordpass", "enpass", "proton pass", "secrets", "wallet", "bank",
)
_SENSITIVE_BUNDLE_SUBSTR = (
    "1password", "bitwarden", "keychain", "lastpass", "keepass",
    "dashlane", "nordpass", "enpass",
    "com.apple.passwords", "me.proton.pass",
)

_AUDIT = Path(os.environ.get(
    "DH_AUDIT_LOG",
    Path.home() / ".desktop-harness" / "audit.jsonl",
))


_PROTECTED_SYSTEM_PROCESSES = {
    "csrss.exe", "explorer.exe", "lsass.exe", "services.exe",
    "smss.exe", "svchost.exe", "system", "wininit.exe", "winlogon.exe"
}


def is_protected_process(name: str) -> bool:
    """Check if process name is a critical OS component."""
    if not name:
        return False
    return name.lower().strip() in _PROTECTED_SYSTEM_PROCESSES


def allow_sensitive() -> bool:
    return os.environ.get("DH_ALLOW_SENSITIVE", "").lower() in ("1", "true", "yes")


def safe_mode() -> bool:
    v = os.environ.get("DH_SAFE", "1").lower()
    return v not in ("0", "false", "no")


def _looks_sensitive(name: str = "", bundle_id: str = "") -> bool:
    low = (name or "").lower()
    bid = (bundle_id or "").lower()
    for s in _SENSITIVE_NAME_SUBSTR:
        if s in low:
            return True
    for s in _SENSITIVE_BUNDLE_SUBSTR:
        if s in bid:
            return True
    return False


def check_app_allowed(name: str, bundle_id: str = "") -> None:
    if allow_sensitive():
        return
    if _looks_sensitive(name, bundle_id):
        raise PermissionError(
            f"refusing to control sensitive app {name!r} ({bundle_id or 'no bundle'}). "
            f"Set DH_ALLOW_SENSITIVE=1 if you really mean it."
        )


def check_frontmost_allowed() -> None:
    """Block mutations when a sensitive app is already focused.

    Fails closed: if the frontmost app cannot be determined we refuse rather
    than proceed. Swallowing the error here meant a transient AX/NSWorkspace
    failure silently disabled the gate for that call, which is the one moment
    it most needs to hold.
    """
    if allow_sensitive():
        return
    from . import windows as winmod
    try:
        front = winmod.frontmost_app()
    except Exception as e:
        raise PermissionError(
            f"refusing to act: cannot determine the frontmost app "
            f"({type(e).__name__}: {e}). Set DH_ALLOW_SENSITIVE=1 to override."
        ) from e
    if not front:
        raise PermissionError(
            "refusing to act: no frontmost app could be determined. "
            "Set DH_ALLOW_SENSITIVE=1 to override."
        )
    check_app_allowed(front.get("name") or "", front.get("bundle_id") or "")


def check_helper_allowed(name: str) -> None:
    # No high-risk shell helpers ship today; keep hook for future.
    blocked = frozenset({"run_shell", "shell", "osascript_raw"})
    if name in blocked and safe_mode() and not allow_sensitive():
        raise PermissionError(
            f"helper {name!r} blocked in safe mode (DH_SAFE=1)."
        )


def audit(event: str, detail: dict[str, Any] | None = None) -> None:
    try:
        _AUDIT.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": time.time(), "event": event, "detail": detail or {}}
        with _AUDIT.open("a") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


CONFIRM_GUIDANCE = (
    "Before sending messages, posting, purchasing, deleting data, changing "
    "security/privacy settings, or entering passwords: STOP and ask the user."
)
