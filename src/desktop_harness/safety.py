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
    "1password", "bitwarden", "keychain", "lastpass", "keepass",
    "dashlane", "nordpass", "enpass", "secrets", "wallet", "bank",
)
_SENSITIVE_BUNDLE_SUBSTR = (
    "1password", "bitwarden", "keychain", "lastpass", "keepass",
    "dashlane", "nordpass", "enpass",
)

_AUDIT = Path(os.environ.get(
    "DH_AUDIT_LOG",
    Path.home() / ".desktop-harness" / "audit.jsonl",
))


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
    """Block mutations when a sensitive app is already focused."""
    if allow_sensitive():
        return
    try:
        from . import windows as winmod
        front = winmod.frontmost_app()
    except Exception:
        return
    if not front:
        return
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
