"""Tool schemas + local executor for Grok Voice → desktop-harness.

Voice models don't control the Mac directly. They call these functions;
we execute them with the harness helpers.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from . import helpers as H

# --- OpenAI/xAI Realtime-compatible function tool definitions ---

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "list_apps",
        "description": "List running Mac applications (name, bundle id, active).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "open_app",
        "description": "Open or focus a Mac app by name (e.g. Safari, TextEdit, System Settings).",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Application name"},
            },
            "required": ["name"],
        },
    },
    {
        "type": "function",
        "name": "screen_labels",
        "description": (
            "Read visible UI labels from the Accessibility tree "
            "(fast; prefer this over guessing coordinates)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "app": {
                    "type": "string",
                    "description": "Optional app name; default frontmost",
                },
                "limit": {"type": "integer", "description": "Max labels", "default": 30},
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "click_text",
        "description": (
            "Click/press a control whose title or label contains the given text. "
            "Uses Accessibility first."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "app": {"type": "string", "description": "Optional app scope"},
            },
            "required": ["text"],
        },
    },
    {
        "type": "function",
        "name": "type_text",
        "description": "Type unicode text into the focused field via the keyboard.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "type": "function",
        "name": "hotkey",
        "description": "Press a keyboard shortcut, e.g. keys=['cmd','s'] or ['cmd','shift','t'].",
        "parameters": {
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Modifier and key names: cmd, shift, alt, ctrl, letters, return, escape",
                },
            },
            "required": ["keys"],
        },
    },
    {
        "type": "function",
        "name": "move_mouse",
        "description": "Move the real mouse pointer to global screen coordinates.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
                "duration": {"type": "number", "default": 0.2},
            },
            "required": ["x", "y"],
        },
    },
    {
        "type": "function",
        "name": "click_xy",
        "description": "Move to global coordinates and left-click.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
                "double": {"type": "boolean", "default": False},
            },
            "required": ["x", "y"],
        },
    },
    {
        "type": "function",
        "name": "mouse_pos",
        "description": "Return current mouse pointer position.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "wiggle_mouse",
        "description": "Small wiggle at the pointer to show the agent is thinking.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]


# Read-only tools may run without --live. Everything else is a Mac mutation
# and needs an explicit live opt-in — consent in the model prompt alone is not
# a gate (see GitHub issue #3).
READ_ONLY_TOOLS = frozenset({"list_apps", "screen_labels", "mouse_pos"})
MUTATING_TOOLS = frozenset(
    {
        "open_app",
        "click_text",
        "type_text",
        "hotkey",
        "move_mouse",
        "click_xy",
        "wiggle_mouse",
    }
)


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "result": data}, default=str)


def _err(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


def execute(
    name: str,
    arguments: dict[str, Any] | str,
    *,
    dry_run: bool = False,
    live: bool = False,
) -> str:
    """Run a voice tool. Returns JSON string for function_call_output.

    Safety: mutating tools refuse unless ``live=True`` (or the call is a
    dry-run that never touches the Mac). Read-only tools always run when not
    dry-running. This is enforced in code — not only in the model prompt.
    """
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            return _err(f"invalid arguments JSON: {arguments[:200]}")
    arguments = arguments or {}

    if dry_run:
        return _ok({"dry_run": True, "tool": name, "arguments": arguments})

    if name in MUTATING_TOOLS and not live:
        return _err(
            f"refused {name!r}: voice scaffold mutates the Mac only with "
            f"--live (or live=True). Re-run with --live after the user clearly "
            f"asks for that action. Read-only tools (list_apps, screen_labels, "
            f"mouse_pos) work without --live."
        )

    try:
        if name == "list_apps":
            apps = H.list_apps()
            return _ok([{"name": a["name"], "active": a["active"]} for a in apps[:40]])

        if name == "open_app":
            info = H.open_app(arguments["name"])
            return _ok(info)

        if name == "screen_labels":
            labs = H.labels(
                arguments.get("app"),
                limit=int(arguments.get("limit") or 30),
            )
            return _ok(labs)

        if name == "click_text":
            hit = H.click_text(arguments["text"], app=arguments.get("app"))
            return _ok(hit)

        if name == "type_text":
            H.type_text(arguments["text"])
            return _ok({"typed": len(arguments["text"])})

        if name == "hotkey":
            keys = arguments.get("keys") or []
            H.hotkey(*keys)
            return _ok({"keys": keys})

        if name == "move_mouse":
            pos = H.move_to(
                float(arguments["x"]),
                float(arguments["y"]),
                duration=float(arguments.get("duration") or 0.2),
            )
            return _ok(pos)

        if name == "click_xy":
            H.click(
                float(arguments["x"]),
                float(arguments["y"]),
                double=bool(arguments.get("double")),
            )
            return _ok({"clicked": True})

        if name == "mouse_pos":
            return _ok(H.mouse_pos())

        if name == "wiggle_mouse":
            return _ok(H.wiggle())

        return _err(f"unknown tool: {name}")
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}")


def handlers(*, dry_run: bool = False, live: bool = False) -> dict[str, Callable[..., str]]:
    """Map name → callable(**kwargs) returning JSON string."""

    def make(n: str):
        def _fn(**kwargs):
            return execute(n, kwargs, dry_run=dry_run, live=live)
        return _fn

    return {t["name"]: make(t["name"]) for t in TOOL_DEFINITIONS}


SESSION_INSTRUCTIONS = """You are a Mac desktop voice co-pilot.
You control the user's real Mac through tools (open apps, read UI labels, click, type, mouse).

Rules:
- Prefer screen_labels / click_text over raw coordinates.
- Prefer open_app + click_text over guessing.
- Never send messages, post, purchase, or delete files unless the user clearly confirms in voice.
- Keep spoken replies short; act with tools when the user asks you to do something on the Mac.
- If a control is missing, call screen_labels and try again.
"""
