"""Warm daemon — keep pyobjc loaded so agent steps aren't cold-starting Python.

Security:
  - Socket mode 0600 (owner only)
  - Token file ~/.desktop-harness/daemon.token (0600); every request must include it
  - Single-instance via PID file

Protocol (newline-delimited JSON over Unix socket):
  → {"op":"exec","code":"…","token":"…"}
  ← {"ok":true,"stdout":"...","stderr":""}
"""
from __future__ import annotations

import io
import json
import os
import secrets
import socket
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SOCKET_PATH = Path(os.environ.get(
    "DH_SOCKET",
    Path.home() / "Library" / "Caches" / "desktop-harness" / "daemon.sock",
))
PID_PATH = SOCKET_PATH.with_suffix(".pid")
TOKEN_PATH = Path(os.environ.get(
    "DH_TOKEN_PATH",
    Path.home() / ".desktop-harness" / "daemon.token",
))

# Presence (halo + "Hands off" island) is shown by scripts run through
# this daemon and is only ever hidden by a script explicitly calling
# hide_agent_presence(). The daemon outlives any single script — if the
# calling agent's turn just ends (chat marks the task done, no more calls
# come in) nothing else revisits that state, so the overlay sits on screen
# indefinitely. ACCEPT_POLL_SECONDS makes the accept() loop below wake up
# periodically even with no request pending; PRESENCE_IDLE_HIDE_SECONDS is
# how long with no exec request before it self-clears. Both run on the
# daemon's single (main) thread — required, see presence.py's threading note.
ACCEPT_POLL_SECONDS = 3.0
PRESENCE_IDLE_HIDE_SECONDS = float(os.environ.get("DH_PRESENCE_IDLE_HIDE", "20"))


def socket_path() -> Path:
    return SOCKET_PATH


def _read_token() -> str | None:
    try:
        if TOKEN_PATH.exists():
            return TOKEN_PATH.read_text().strip() or None
    except Exception:
        pass
    return None


def _write_token() -> str:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_hex(24)
    TOKEN_PATH.write_text(tok)
    os.chmod(TOKEN_PATH, 0o600)
    return tok


def is_running() -> bool:
    # Inside the daemon process a ping would deadlock (single-threaded
    # accept loop is busy running the current script).
    if os.environ.get("DH_IN_DAEMON") == "1":
        return True
    if not SOCKET_PATH.exists():
        return False
    try:
        resp = client_request({"op": "ping"}, timeout=0.4)
        return bool(resp.get("ok") and resp.get("pong"))
    except Exception:
        return False


def client_request(payload: dict, timeout: float = 60.0) -> dict:
    tok = _read_token()
    if tok and "token" not in payload:
        payload = {**payload, "token": tok}
    data = (json.dumps(payload) + "\n").encode()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(SOCKET_PATH))
        s.sendall(data)
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    if not buf:
        raise RuntimeError("daemon closed connection")
    return json.loads(buf.decode())


def exec_via_daemon(code: str, timeout: float = 60.0) -> dict:
    return client_request({"op": "exec", "code": code}, timeout=timeout)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def serve() -> None:
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Single instance
    if PID_PATH.exists():
        try:
            old = int(PID_PATH.read_text().strip())
            if _pid_alive(old) and old != os.getpid():
                # probe socket
                if is_running():
                    raise SystemExit(
                        f"daemon already running (pid {old}). "
                        f"Use: desktop-harness daemon stop"
                    )
        except ValueError:
            pass
        except SystemExit:
            raise
        except Exception:
            pass

    if SOCKET_PATH.exists():
        try:
            SOCKET_PATH.unlink()
        except OSError:
            pass

    token = _write_token()
    os.environ["DH_IN_DAEMON"] = "1"

    from .helpers import namespace

    ns = namespace()
    ns["helpers"] = __import__("desktop_harness.helpers", fromlist=["*"])

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(SOCKET_PATH))
    os.chmod(SOCKET_PATH, 0o600)
    srv.listen(8)
    # Times out accept() periodically so the idle-presence check below runs
    # even when no request comes in; the *accepted* connection socket does
    # not inherit this (Python only forces blocking on it when no global
    # default timeout is set), so in-flight requests/long-running scripts
    # are unaffected.
    srv.settimeout(ACCEPT_POLL_SECONDS)
    PID_PATH.write_text(str(os.getpid()))
    try:
        os.chmod(PID_PATH, 0o600)
    except OSError:
        pass
    print(f"desktop-harness daemon listening on {SOCKET_PATH}", flush=True)
    print(f"token: {TOKEN_PATH} (0600)", flush=True)

    last_activity = time.monotonic()
    try:
        while True:
            try:
                conn, _ = srv.accept()
            except (TimeoutError, socket.timeout):
                # No request in a while — self-clear a stale presence
                # overlay instead of leaving it on screen until some
                # future script happens to call hide_agent_presence().
                idle = time.monotonic() - last_activity
                if idle >= PRESENCE_IDLE_HIDE_SECONDS:
                    try:
                        from . import presence
                        if presence.active():
                            presence.hide()
                    except Exception:
                        pass
                    # Monitor stays up while a Stage window exists; otherwise
                    # drop it so we don't leave a stale picture on screen.
                    try:
                        from . import stage as _stage
                        if _stage.monitor_active() and _stage._find_stage_window() is None:
                            _stage.hide_monitor()
                    except Exception:
                        pass
                continue
            with conn:
                def _reply(payload: bytes | dict) -> None:
                    # Client may have closed (timeout, killed agent) — never
                    # let a BrokenPipe take down the whole daemon; that left
                    # agents hung on a dead socket looking like "shell stuck".
                    try:
                        if isinstance(payload, dict):
                            payload = (json.dumps(payload) + "\n").encode()
                        conn.sendall(payload)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass

                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(1 << 20)
                    if not chunk:
                        break
                    buf += chunk
                if not buf:
                    continue
                try:
                    req = json.loads(buf.decode())
                except json.JSONDecodeError as e:
                    _reply({"ok": False, "error": str(e)})
                    continue
                # Auth
                if req.get("token") != token:
                    _reply(b'{"ok":false,"error":"unauthorized (bad or missing token)"}\n')
                    continue
                op = req.get("op")
                if op == "ping":
                    _reply(b'{"ok":true,"pong":true}\n')
                    continue
                if op == "quit":
                    _reply(b'{"ok":true}\n')
                    break
                if op == "exec":
                    code = req.get("code") or ""
                    out_b, err_b = io.StringIO(), io.StringIO()
                    ok = True
                    err_msg = ""
                    try:
                        with redirect_stdout(out_b), redirect_stderr(err_b):
                            exec(
                                compile(code, "<desktop-harness-daemon>", "exec"),
                                ns,
                                ns,
                            )
                    except Exception:
                        ok = False
                        err_msg = traceback.format_exc()
                    last_activity = time.monotonic()
                    _reply({
                        "ok": ok,
                        "stdout": out_b.getvalue(),
                        "stderr": err_b.getvalue() + err_msg,
                    })
                    continue
                _reply({"ok": False, "error": f"unknown op {op}"})
    finally:
        srv.close()
        for p in (SOCKET_PATH, PID_PATH):
            try:
                p.unlink()
            except OSError:
                pass
