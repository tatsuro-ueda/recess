#!/bin/sh
# Recess mode switch. The presence of the off file changes what the daemon does (the daemon keeps running).
# Usage: recess on [--hint] | off | toggle | status | hint   (from herdr: herdr plugin action invoke recess.toggle)
set -eu
STATE_DIR="$HOME/.local/state/recess"
OFF="$STATE_DIR/off"
SEEN_HINT="$STATE_DIR/hint-seen"   # whether the hint has been shown once (--hint shows it again)
STATUS_JSON="$STATE_DIR/status.json"   # the daemon writes this every poll; `status` only reads it
STATUS_MAX_AGE=15                      # seconds. Older than this means the daemon is not running
mkdir -p "$STATE_DIR"

notify() { command -v herdr >/dev/null 2>&1 && herdr notification show "$1" --body "$2" >/dev/null 2>&1 || true; }
mode_line() { if [ -e "$OFF" ]; then echo "Recess: OFF"; else echo "Recess: ON"; fi; }

# Pane list and what is holding the trip back. All values come from the daemon's own
# decision (status.json). Nothing is judged here: a second copy of the rules would drift
# and lie about why Recess is not firing.
detail() {
  py="$(command -v python3 2>/dev/null || true)"
  [ -n "$py" ] || return 0
  [ -f "$STATUS_JSON" ] || return 0
  "$py" - "$STATUS_JSON" "$STATUS_MAX_AGE" <<'RENDER'
import datetime, json, sys, unicodedata

def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

def clip(s, n):
    out = ""
    for c in s:
        if width(out) + width(c) > n:
            return out + "…"
        out += c
    return out

def pad(s, n):
    return s + " " * max(n - width(s), 0)

try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    age = (datetime.datetime.now()
           - datetime.datetime.strptime(d["written_at"], "%Y-%m-%d %H:%M:%S")).total_seconds()
except Exception:
    sys.exit(0)

print()
if age > float(sys.argv[2]):
    print(f"  常駐の記録が {int(age)} 秒前で止まっています（内訳は出せません）。")
    print("  起こす: launchctl kickstart -k gui/$(id -u)/jp.feel-physics.recess")
    sys.exit(0)

blocking = d["blocking"]
if d["mode"] != "ON":
    print("いま連れ出せるか: いいえ（recess が OFF。`recess on` で戻ります）")
elif d["can_play"]:
    print("いま連れ出せるか: はい")
elif blocking:
    print(f"いま連れ出せるか: いいえ（ペイン {len(blocking)} 件が妨げています）")
else:
    why = []
    if not d["front_is_terminal"]:
        why.append(f"最前面が {d['front_app']}")
    if d["hands_off_seconds"] < d["hands_off_needed"]:
        why.append(f"手が乗っている（{d['hands_off_seconds']}s / {d['hands_off_needed']}s 必要）")
    if not d["any_working"]:
        why.append("働いているAIが居ない")
    if d["focused_pane"] is None:
        why.append("見ている端末にフォーカス中のペインが無い")
    if d["return_cooldown_left"] > 0:
        why.append(f"呼び戻し直後の猶予 残り {d['return_cooldown_left']}s")
    if not d["pending_off"]:
        why.append("用事明けの印が無い（次に用事が片付いた瞬間を待っています）")
    print("いま連れ出せるか: いいえ（ペインは全部ok。" + " / ".join(why) + "）")

print(f"  最前面 {d['front_app']}{' ✓' if d['front_is_terminal'] else ' ✗'}"
      f" / 手を離して {d['hands_off_seconds']}s（{d['hands_off_needed']}s必要）"
      f" / 連れ出し先 {d['video_app']}")
print()

order = {"blocked": 0, "done": 0}
for p in sorted(d["panes"], key=lambda p: (p["blocking"] is None, p["ignored"], p["key"])):
    machine, pane = p["key"].split("/", 1)
    if p["ignored"]:
        verdict = "ok（無視リスト）"
    elif p["blocking"]:
        verdict = f"妨げている（{p['blocking']}）"
    elif p["status"] == "working":
        verdict = "ok（この相手を待てる）"
    elif p["reading"]:
        verdict = "ok（読み中。見ているタブの外）"
    else:
        verdict = "ok"
    print(f"  {pad(clip(machine, 14), 14)} {pad(clip(p['title'] or pane, 32), 32)} "
          f"{pad(p['status'], 8)} {verdict}")
RENDER
}

status() { mode_line; detail; }

hint() {
  cat <<'HINT'

  Open a video in the window right behind this one, and leave it paused.
  Recess only sends one space key, so a video that is already playing ends up inverted.
  Back at the terminal, the video is paused. That is the right state.

HINT
}

case "${1:-status}" in
  on)
    rm -f "$OFF"; mode_line
    if [ "${2:-}" = "--hint" ] || [ ! -e "$SEEN_HINT" ]; then
      hint; : > "$SEEN_HINT"
    fi
    notify "Recess: ON" "Open a video in the window right behind this one, and leave it paused"
    ;;
  off)    : > "$OFF"; mode_line; notify "Recess: OFF" "Watching only. No trips to the browser, no call-backs" ;;
  toggle) if [ -e "$OFF" ]; then "$0" on; else "$0" off; fi ;;
  status) status ;;
  hint)   hint ;;
  *) echo "usage: recess on [--hint] | off | toggle | status | hint" >&2; exit 2 ;;
esac
