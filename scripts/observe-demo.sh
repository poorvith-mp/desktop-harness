#!/usr/bin/env bash
# Run presence demo + timed screenshots for the observe loop.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/tmp/dh-observe}"
mkdir -p "$OUT"
rm -f "$OUT"/*.png

export PATH="${HOME}/.local/bin:${PATH}"
export DH_NO_DAEMON=1
export DH_PRESENCE=1

(
  sleep 1.3; screencapture -x "$OUT/01-hold.png"
  sleep 2.0; screencapture -x "$OUT/02-move.png"
  sleep 2.0; screencapture -x "$OUT/03-square.png"
  sleep 1.2; screencapture -x "$OUT/04-click.png"
) &
CAP=$!

cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

desktop-harness <<'PY'
import time
print("hold")
enable_agent_cursor(True)
time.sleep(2.2)
print("sweep")
for i in range(0, 24):
    move_to(260 + i * 16, 300 + i * 9, duration=0.05)
print("square")
for x, y in [(380, 320), (640, 320), (640, 540), (380, 540), (380, 320)]:
    move_to(float(x), float(y), duration=0.4)
    time.sleep(0.06)
print("click")
click(520, 420, duration=0.12)
time.sleep(0.45)
click(520, 420, duration=0.12)
time.sleep(1.0)
hide_agent_presence()
print("done")
PY

wait "$CAP" 2>/dev/null || true
echo "shots in $OUT"
ls -la "$OUT"
