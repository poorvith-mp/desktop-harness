"""Unit tests for agent-workspace path resolution."""
from __future__ import annotations

from pathlib import Path
from desktop_harness import helpers


def test_resolve_workspace_env_override(monkeypatch, tmp_path):
    custom_ws = tmp_path / "custom-ws"
    monkeypatch.setenv("DH_AGENT_WORKSPACE", str(custom_ws))
    resolved = helpers._resolve_agent_workspace()
    assert resolved == custom_ws


def test_resolve_workspace_source_checkout(monkeypatch, tmp_path):
    monkeypatch.delenv("DH_AGENT_WORKSPACE", raising=False)
    fake_repo_root = tmp_path / "repo"
    fake_source_ws = fake_repo_root / "agent-workspace"
    fake_source_ws.mkdir(parents=True)

    monkeypatch.setattr(helpers, "REPO_ROOT", fake_repo_root)
    resolved = helpers._resolve_agent_workspace()
    assert resolved == fake_source_ws


def test_resolve_workspace_fallback_to_user_home(monkeypatch, tmp_path):
    monkeypatch.delenv("DH_AGENT_WORKSPACE", raising=False)
    fake_repo_root = tmp_path / "site-packages" / "desktop_harness"  # No agent-workspace dir here
    fake_home = tmp_path / "user_home"
    fake_home.mkdir(parents=True)

    monkeypatch.setattr(helpers, "REPO_ROOT", fake_repo_root)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    resolved = helpers._resolve_agent_workspace()
    assert resolved == fake_home / ".desktop-harness" / "agent-workspace"
