"""Unit tests for windows.find_app resolution logic."""
from __future__ import annotations

from desktop_harness import windows


SAMPLE_APPS = [
    {"name": "Safari", "bundle_id": "com.apple.Safari", "pid": 101, "active": True, "hidden": False},
    {"name": "TextEdit", "bundle_id": "com.apple.TextEdit", "pid": 102, "active": False, "hidden": False},
    {"name": "Sublime Text Helper", "bundle_id": "com.sublimetext.helper", "pid": 103, "active": False, "hidden": False},
    {"name": "Visual Studio Code", "bundle_id": "com.microsoft.VSCode", "pid": 104, "active": False, "hidden": False},
    {"name": "Music", "bundle_id": "com.apple.Music", "pid": 105, "active": False, "hidden": False},
]


def test_find_app_exact_name(monkeypatch):
    monkeypatch.setattr(windows, "list_apps", lambda: SAMPLE_APPS)
    app = windows.find_app("Safari")
    assert app is not None
    assert app["pid"] == 101
    assert app["name"] == "Safari"


def test_find_app_exact_bundle_id(monkeypatch):
    monkeypatch.setattr(windows, "list_apps", lambda: SAMPLE_APPS)
    app = windows.find_app("com.microsoft.VSCode")
    assert app is not None
    assert app["pid"] == 104
    assert app["name"] == "Visual Studio Code"


def test_find_app_startswith(monkeypatch):
    monkeypatch.setattr(windows, "list_apps", lambda: SAMPLE_APPS)
    # "Text" startswith matches "TextEdit" (pid 102) vs "Sublime Text Helper" (doesn't start with Text)
    app = windows.find_app("Text")
    assert app is not None
    assert app["name"] == "TextEdit"
    assert app["pid"] == 102


def test_find_app_shortest_substring(monkeypatch):
    monkeypatch.setattr(windows, "list_apps", lambda: SAMPLE_APPS)
    # Query "Edit" matches "TextEdit" (shortest substring match)
    app = windows.find_app("Edit")
    assert app is not None
    assert app["name"] == "TextEdit"


def test_find_app_not_found(monkeypatch):
    monkeypatch.setattr(windows, "list_apps", lambda: SAMPLE_APPS)
    monkeypatch.setattr(
        windows.NSRunningApplication,
        "runningApplicationsWithBundleIdentifier_",
        lambda _: [],
    )
    assert windows.find_app("NonExistentApp") is None
    assert windows.find_app("") is None
