#!/bin/sh
# Recess のモード切り替え。off ファイルの有無で常駐の振る舞いを変える（常駐自体は止めない）。
# 使い方: recess on | off | toggle | status   （herdr からは: herdr plugin action invoke recess.toggle）
set -eu
STATE_DIR="$HOME/.local/state/recess"
OFF="$STATE_DIR/off"
SEEN_HINT="$STATE_DIR/hint-seen"   # 使い方の案内を一度でも出したか（--hint で毎回出せる）
mkdir -p "$STATE_DIR"

notify() { command -v herdr >/dev/null 2>&1 && herdr notification show "$1" --body "$2" >/dev/null 2>&1 || true; }
status() { if [ -e "$OFF" ]; then echo "Recess: OFF"; else echo "Recess: ON"; fi; }

hint() {
  cat <<'HINT'

  使う前に、もう1枚のウインドウで動画を開き、一時停止して置いてください。
  Recess はスペースキーを1回送るだけなので、動画が止まっていないと逆向きになります。
  ターミナルに戻ったら、動画は止まっている。これが正しい状態です。

HINT
}

case "${1:-status}" in
  on)
    rm -f "$OFF"; status
    if [ "${2:-}" = "--hint" ] || [ ! -e "$SEEN_HINT" ]; then
      hint; : > "$SEEN_HINT"
    fi
    notify "Recess: ON" "もう1枚のウインドウで動画を開き、一時停止して置いてください"
    ;;
  off)    : > "$OFF"; status; notify "Recess: OFF" "見張るだけ。連れ出し・呼び戻しをしない" ;;
  toggle) if [ -e "$OFF" ]; then "$0" on; else "$0" off; fi ;;
  status) status ;;
  hint)   hint ;;
  *) echo "usage: recess on [--hint] | off | toggle | status | hint" >&2; exit 2 ;;
esac
