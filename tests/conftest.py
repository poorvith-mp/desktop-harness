"""Pytest configuration and mocks for non-macOS test environments."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure src/ is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Mock macOS-only pyobjc modules on Linux / Windows CI runners
for mod_name in ["Quartz", "AppKit", "ApplicationServices", "CoreFoundation", "Foundation"]:
    if mod_name not in sys.modules:
        try:
            __import__(mod_name)
        except ImportError:
            sys.modules[mod_name] = MagicMock()
