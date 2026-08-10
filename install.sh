#!/usr/bin/env bash
# One-shot install for desktop-harness (macOS)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> desktop-harness install"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -U pip
pip install -q \
  pyobjc-framework-Quartz \
  pyobjc-framework-Cocoa \
  pyobjc-framework-ApplicationServices
pip install -q -e . --no-deps

mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/desktop-harness" << EOF
#!/bin/sh
exec "$ROOT/.venv/bin/desktop-harness" "\$@"
EOF
chmod +x "$HOME/.local/bin/desktop-harness" "$ROOT/desktop-harness"

# Grok Build skill (if present)
if [ -d "$HOME/.grok" ]; then
  mkdir -p "$HOME/.grok/skills/desktop-harness"
  "$ROOT/.venv/bin/desktop-harness" skill > "$HOME/.grok/skills/desktop-harness/SKILL.md"
  echo "==> registered Grok skill ~/.grok/skills/desktop-harness"
fi

echo ""
echo "==> grant permissions (required once):"
echo '  open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"'
echo '  open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"'
echo "  Enable your Terminal/Ghostty/Grok host, then restart it after Screen Recording."
echo ""
echo "==> ensure ~/.local/bin is on PATH"
echo '  export PATH="$HOME/.local/bin:$PATH"'
echo ""
"$ROOT/.venv/bin/desktop-harness" --doctor || true
echo ""
echo "Done. Try:  desktop-harness selftest"
echo "       or:  desktop-harness demo"
