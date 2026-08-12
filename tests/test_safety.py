"""Unit tests for safety gates and sensitive app detection."""
from __future__ import annotations

import pytest
from desktop_harness import safety


def test_looks_sensitive_by_name():
    assert safety._looks_sensitive("Passwords")
    assert safety._looks_sensitive("1Password 7")
    assert safety._looks_sensitive("Bitwarden")
    assert safety._looks_sensitive("Apple Keychain Access")
    assert safety._looks_sensitive("Dashlane Password Manager")
    assert safety._looks_sensitive("Proton Pass")
    assert safety._looks_sensitive("Chase Bank")

    assert not safety._looks_sensitive("Safari")
    assert not safety._looks_sensitive("TextEdit")
    assert not safety._looks_sensitive("Visual Studio Code")
    assert not safety._looks_sensitive("Terminal")
    assert not safety._looks_sensitive("Calculator")
    assert not safety._looks_sensitive("Finder")


def test_looks_sensitive_by_bundle_id():
    assert safety._looks_sensitive("", "com.apple.passwords")
    assert safety._looks_sensitive("", "com.agilebits.1password")
    assert safety._looks_sensitive("", "me.proton.pass")
    assert safety._looks_sensitive("", "com.dashlane.Dashlane")

    assert not safety._looks_sensitive("", "com.apple.Safari")
    assert not safety._looks_sensitive("", "com.apple.TextEdit")
    assert not safety._looks_sensitive("", "com.microsoft.VSCode")


def test_check_app_allowed_raises_on_sensitive(monkeypatch):
    monkeypatch.delenv("DH_ALLOW_SENSITIVE", raising=False)
    with pytest.raises(PermissionError, match="refusing to control sensitive app"):
        safety.check_app_allowed("Bitwarden")

    with pytest.raises(PermissionError, match="refusing to control sensitive app"):
        safety.check_app_allowed("My Vault", "com.agilebits.1password")


def test_check_app_allowed_passes_when_override_set(monkeypatch):
    monkeypatch.setenv("DH_ALLOW_SENSITIVE", "1")
    # Should not raise
    safety.check_app_allowed("1Password")
    safety.check_app_allowed("Passwords", "com.apple.passwords")


def test_check_helper_allowed():
    # Safe mode blocks shell helpers
    with pytest.raises(PermissionError, match="blocked in safe mode"):
        safety.check_helper_allowed("run_shell")

    # Allowed safe helpers do not raise
    safety.check_helper_allowed("click")
    safety.check_helper_allowed("find")
