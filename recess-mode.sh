#!/bin/sh
# Recess mode switch. The presence of the off file changes what the daemon does (the daemon keeps running).
# Usage: recess on [--hint] | off | toggle | status | hint   (from herdr: herdr plugin action invoke recess.toggle)
set -eu
STATE_DIR="$HOME/.local/state/recess"
OFF="$STATE_DIR/off"
SEEN_HINT="$STATE_DIR/hint-seen"   # whether the hint has been shown once (--hint shows it again)
mkdir -p "$STATE_DIR"

notify() { command -v herdr >/dev/null 2>&1 && herdr notification show "$1" --body "$2" >/dev/null 2>&1 || true; }
status() { if [ -e "$OFF" ]; then echo "Recess: OFF"; else echo "Recess: ON"; fi; }

hint() {
  cat <<'HINT'

  Open a video in the window right behind this one, and leave it paused.
  Recess only sends one space key, so a video that is already playing ends up inverted.
  Back at the terminal, the video is paused. That is the right state.

HINT
}

case "${1:-status}" in
  on)
    rm -f "$OFF"; status
    if [ "${2:-}" = "--hint" ] || [ ! -e "$SEEN_HINT" ]; then
      hint; : > "$SEEN_HINT"
    fi
    notify "Recess: ON" "Open a video in the window right behind this one, and leave it paused"
    ;;
  off)    : > "$OFF"; status; notify "Recess: OFF" "Watching only. No trips to the browser, no call-backs" ;;
  toggle) if [ -e "$OFF" ]; then "$0" on; else "$0" off; fi ;;
  status) status ;;
  hint)   hint ;;
  *) echo "usage: recess on [--hint] | off | toggle | status | hint" >&2; exit 2 ;;
esac
