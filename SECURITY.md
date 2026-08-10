# Security

`desktop-harness` can control a real Mac (mouse, keyboard, UI). Treat it like granting Accessibility to a new app.

## Runtime protections

| Control | Behavior |
|---------|----------|
| `DH_ALLOW_SENSITIVE` | Default off. Blocks open/focus and mutations while password-manager-like apps are targeted or frontmost. |
| Audit log | `~/.desktop-harness/audit.jsonl` for key mutations |
| Warm daemon | Unix socket **mode 0600** + **token** at `~/.desktop-harness/daemon.token` (0600). Requests without the token are rejected. |

The daemon is a **local privileged exec endpoint** (it can run harness scripts with Accessibility). Only your user account should read the token/socket. Do not run the daemon on shared multi-user machines without understanding this.

## Recommendations

- Only install from a source you trust  
- Review agent scripts before `always-approve` / unattended runs  
- Keep default sensitive-app blocks; do not set `DH_ALLOW_SENSITIVE=1` casually  
- Agents should refuse outbound actions (messages, purchases, deletes) without human confirmation  
- Prefer `desktop-harness daemon stop` when finished with a long session  

## Reporting

Open a GitHub issue for vulnerabilities. Do not file public issues that include secrets or personal screen contents.
