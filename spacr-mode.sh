#!/bin/sh
# Spacr のモード切り替え。off ファイルの有無で常駐の振る舞いを変える（常駐自体は止めない）。
# 使い方: spacr on | off | toggle | status   （herdr からは: herdr plugin action invoke spacr.toggle）
set -eu
STATE_DIR="$HOME/.local/state/spacr"
OFF="$STATE_DIR/off"
mkdir -p "$STATE_DIR"
notify() { command -v herdr >/dev/null 2>&1 && herdr notification show "$1" --body "$2" >/dev/null 2>&1 || true; }
status() { if [ -e "$OFF" ]; then echo "Spacr: OFF"; else echo "Spacr: ON"; fi; }
case "${1:-status}" in
  on)     rm -f "$OFF"; status; notify "Spacr: ON" "AI が働く間はブラウザへ。呼ばれたら戻る" ;;
  off)    : > "$OFF"; status; notify "Spacr: OFF" "見張るだけ。連れ出し・呼び戻しをしない" ;;
  toggle) if [ -e "$OFF" ]; then "$0" on; else "$0" off; fi ;;
  status) status ;;
  *) echo "usage: spacr on|off|toggle|status" >&2; exit 2 ;;
esac
