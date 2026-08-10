"""CLI: exec Python with helpers — optionally via warm daemon."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        source = sys.stdin.read()
        if not source.strip():
            _usage()
            sys.exit(2)
        _run_source(source)
        return

    cmd = argv[0]

    if cmd in ("-h", "--help", "help"):
        _usage()
        return

    if cmd in ("-V", "--version", "version"):
        from . import __version__
        print(f"desktop-harness {__version__}")
        return

    if cmd in ("check-update", "update-check"):
        sys.exit(_check_update())

    if cmd in ("--doctor", "doctor"):
        from .admin import run_doctor
        sys.exit(run_doctor())

    if cmd == "skill":
        # Prefer packaged data, then repo-root SKILL.md (editable install)
        candidates = [
            Path(__file__).resolve().parent / "data" / "SKILL.md",
            Path(__file__).resolve().parent.parent.parent / "SKILL.md",
            Path.cwd() / "SKILL.md",
        ]
        for skill in candidates:
            if skill.is_file():
                sys.stdout.write(skill.read_text())
                return
        print("SKILL.md not found (reinstall from source or copy skill)", file=sys.stderr)
        sys.exit(1)
        return

    if cmd == "demo":
        from .demo import run_demo
        sys.exit(run_demo())

    if cmd == "selftest":
        from .selftest import run_selftest
        sys.exit(run_selftest())

    if cmd == "daemon":
        sub = argv[1] if len(argv) > 1 else "start"
        if sub in ("start", "run", "serve"):
            bg = "--bg" in argv or "-d" in argv
            if bg:
                # detach so agents can warm the process without blocking
                log = Path.home() / "Library" / "Caches" / "desktop-harness" / "daemon.log"
                log.parent.mkdir(parents=True, exist_ok=True)
                from . import daemon as d
                if d.is_running():
                    print("already running", d.socket_path())
                    return
                py = sys.executable
                # re-invoke same module
                with open(log, "ab") as lf:
                    subprocess.Popen(
                        [py, "-m", "desktop_harness.run", "daemon", "serve"],
                        stdout=lf, stderr=lf, start_new_session=True,
                        env={**os.environ},
                    )
                # wait briefly for socket
                for _ in range(25):
                    time.sleep(0.1)
                    if d.is_running():
                        print("daemon started (bg)", d.socket_path())
                        return
                print("daemon start timed out; see", log, file=sys.stderr)
                sys.exit(1)
            from .daemon import serve
            serve()
            return
        if sub == "stop":
            from . import daemon as d
            if d.is_running():
                try:
                    d.client_request({"op": "quit"}, timeout=2)
                except Exception:
                    pass
            print("daemon stop requested")
            return
        if sub == "status":
            from . import daemon as d
            print("running" if d.is_running() else "stopped", d.socket_path())
            return
        print("usage: desktop-harness daemon [start|stop|status] [--bg]", file=sys.stderr)
        sys.exit(2)

    if cmd == "-c" and len(argv) >= 2:
        _run_source(argv[1])
        return

    path = Path(cmd)
    if path.is_file():
        _run_source(path.read_text())
        return

    print(f"unknown args: {argv}", file=sys.stderr)
    sys.exit(2)


def _usage() -> None:
    from . import __version__
    print(
        f"desktop-harness {__version__} — Mac control for Grok Build (and shell agents)\n\n"
        "  desktop-harness --version\n"
        "  desktop-harness check-update  # compare to GitHub main (no auto-install)\n"
        "  desktop-harness --doctor\n"
        "  desktop-harness selftest\n"
        "  desktop-harness demo\n"
        "  desktop-harness skill\n"
        "  desktop-harness daemon start [--bg]|stop|status\n"
        "  desktop-harness <<'PY' ... PY\n"
        "  desktop-harness -c 'print(mouse_pos())'\n\n"
        "Not an MCP server. CLI + agent skill.\n"
        "Updates: git pull in your clone, then re-run ./install.sh if needed.\n"
        "Docs: README.md · HOW_IT_WORKS.md · docs/OBSERVE-LOOP.md\n"
    )


def _check_update() -> int:
    """Tell the user if GitHub main is ahead. Does not auto-install (CLI is invisible)."""
    from . import __version__
    import json
    import urllib.request

    print(f"local version: {__version__}")
    # Prefer git checkout state when available
    root = Path(__file__).resolve().parent.parent.parent
    git_dir = root / ".git"
    local_sha = None
    if git_dir.exists():
        try:
            local_sha = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True,
            ).strip()
            print(f"local commit:  {local_sha[:10]}")
        except Exception:
            pass

    url = "https://api.github.com/repos/xfreeze2/desktop-harness/commits/main"
    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json", "User-Agent": "desktop-harness"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        remote_sha = data.get("sha") or ""
        print(f"github main:   {remote_sha[:10]}")
        if local_sha and remote_sha:
            if local_sha == remote_sha:
                print("status: up to date")
                return 0
            print("status: update available")
            print("update:  cd <your-clone> && git pull && ./install.sh")
            print("         (re-copy skill if you use Grok Build)")
            return 0
        print("status: compared versions only (no local git sha)")
        print("update:  git pull in your clone, then ./install.sh")
        return 0
    except Exception as e:
        print(f"status: could not reach GitHub ({type(e).__name__}: {e})")
        print("manual: https://github.com/xfreeze2/desktop-harness")
        return 1


def _want_daemon() -> bool:
    # Auto-use daemon when running; DH_NO_DAEMON=1 forces in-process
    if os.environ.get("DH_NO_DAEMON", "").lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("DH_FORCE_DAEMON", "").lower() in ("1", "true", "yes"):
        return True
    try:
        from . import daemon as d
        return d.is_running()
    except Exception:
        return False


def _run_source(source: str) -> None:
    if _want_daemon():
        from . import daemon as d
        try:
            resp = d.exec_via_daemon(source)
        except Exception as e:
            # fall back to local if daemon flaky
            print(f"# daemon unavailable ({e}); running in-process", file=sys.stderr)
            _exec_local(source)
            return
        sys.stdout.write(resp.get("stdout") or "")
        err = resp.get("stderr") or ""
        if err:
            sys.stderr.write(err)
        if not resp.get("ok", False):
            sys.exit(1)
        return
    _exec_local(source)


def _exec_local(source: str) -> None:
    from . import helpers
    ns = helpers.namespace()
    ns["helpers"] = helpers
    exec(compile(source, "<desktop-harness>", "exec"), ns, ns)


if __name__ == "__main__":
    main()
