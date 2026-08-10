#!/usr/bin/env bash
# Dense observe loop: many screenshots during move + click so lag is visible in frames.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/tmp/dh-observe}"
mkdir -p "$OUT"
rm -f "$OUT"/*.png

export PATH="${HOME}/.local/bin:${PATH}"
export DH_NO_DAEMON=1
export DH_PRESENCE=1

# High-frequency captures while demo runs
(
  for i in $(seq -w 1 24); do
    sleep 0.28
    screencapture -x "$OUT/f$i.png" 2>/dev/null || true
  done
) &
CAP=$!

cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

desktop-harness <<'PY'
import time
print("hold")
enable_agent_cursor(True)
time.sleep(1.2)
print("sweep")
for i in range(0, 30):
    move_to(240 + i * 16, 300 + i * 8, duration=0.04)
print("square")
for x, y in [(380, 320), (640, 320), (640, 540), (380, 540), (380, 320)]:
    move_to(float(x), float(y), duration=0.35)
    time.sleep(0.05)
print("clicks")
click(520, 420, duration=0.1)
time.sleep(0.35)
click(520, 420, duration=0.1)
time.sleep(0.9)
hide_agent_presence()
print("done")
PY

wait "$CAP" 2>/dev/null || true
echo "frames: $(ls -1 "$OUT"/*.png 2>/dev/null | wc -l) in $OUT"
ls "$OUT" | head -30
