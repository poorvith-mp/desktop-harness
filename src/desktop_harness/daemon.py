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

    from .helpers import namespace

    ns = namespace()
    ns["helpers"] = __import__("desktop_harness.helpers", fromlist=["*"])

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(SOCKET_PATH))
    os.chmod(SOCKET_PATH, 0o600)
    srv.listen(8)
    PID_PATH.write_text(str(os.getpid()))
    try:
        os.chmod(PID_PATH, 0o600)
    except OSError:
        pass
    print(f"desktop-harness daemon listening on {SOCKET_PATH}", flush=True)
    print(f"token: {TOKEN_PATH} (0600)", flush=True)

    try:
        while True:
            conn, _ = srv.accept()
            with conn:
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
                    conn.sendall(
                        (json.dumps({"ok": False, "error": str(e)}) + "\n").encode()
                    )
                    continue
                # Auth
                if req.get("token") != token:
                    conn.sendall(
                        b'{"ok":false,"error":"unauthorized (bad or missing token)"}\n'
                    )
                    continue
                op = req.get("op")
                if op == "ping":
                    conn.sendall(b'{"ok":true,"pong":true}\n')
                    continue
                if op == "quit":
                    conn.sendall(b'{"ok":true}\n')
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
                    resp = {
                        "ok": ok,
                        "stdout": out_b.getvalue(),
                        "stderr": err_b.getvalue() + err_msg,
                    }
                    conn.sendall((json.dumps(resp) + "\n").encode())
                    continue
                conn.sendall(
                    (
                        json.dumps({"ok": False, "error": f"unknown op {op}"}) + "\n"
                    ).encode()
                )
    finally:
        srv.close()
        for p in (SOCKET_PATH, PID_PATH):
            try:
                p.unlink()
            except OSError:
                pass
