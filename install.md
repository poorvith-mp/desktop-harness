# desktop-harness install

## Requirements

- macOS Sequoia+ recommended (earlier may work)
- Python 3.10+ 
- **Accessibility** + **Screen Recording** for the terminal/app that runs the harness

## Fast install

```bash
git clone https://github.com/xfreeze2/desktop-harness.git
cd desktop-harness
chmod +x install.sh && ./install.sh
export PATH="$HOME/.local/bin:$PATH"
desktop-harness selftest
```

## Manual install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa pyobjc-framework-ApplicationServices
pip install -e . --no-deps
```

Put on PATH:

```bash
mkdir -p ~/.local/bin
ln -sf "$(pwd)/.venv/bin/desktop-harness" ~/.local/bin/desktop-harness
```

Grok Build skill:

```bash
mkdir -p ~/.grok/skills/desktop-harness
desktop-harness skill > ~/.grok/skills/desktop-harness/SKILL.md
```

## Permissions

```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
```

Enable the **host that runs commands** (Ghostty, Terminal, iTerm, or Grok).  
Screen Recording applies after a full quit/relaunch of that host.

```bash
desktop-harness --doctor
desktop-harness selftest
```
