#!/bin/sh
# Recess uninstaller for macOS — install.sh が入れたものを外す
#
# 使い方:
#   sh uninstall.sh [--purge] [--dry-run]
#
# やること:
#   1. launchd の登録を外す（常駐を止める）
#   2. plist（~/Library/LaunchAgents/jp.feel-physics.recess.plist）を消す
#   3. ~/Applications/Recess.app を消す
#   4. ~/.local/share/recess を消す
#   5. ~/.local/bin/afplay は、中身が Recess のラッパーであるときだけ消す
#   6. ~/.local/state/recess（ログと状態）は --purge のときだけ消す
#   7. アクセシビリティ／オートメーションの一覧からの削除は手動なので、その手順を表示する
#
# 方針: sudo は使わない（root では動かさない）。消すのは Recess が作ったものだけ。
set -eu

# ---------- 小道具（$HOME を使う前に定義する） ----------

say()  { printf '%s\n' "$*"; }
warn() { printf '警告: %s\n' "$*" >&2; }
die()  { printf 'エラー: %s\n' "$*" >&2; exit 1; }

# ---------- 変数を組み立てる前に止めるべきもの ----------

[ "$(uname -s)" = "Darwin" ] || die "macOS 専用です（このOS: $(uname -s)）"
[ -n "${HOME:-}" ] && [ -d "$HOME" ] || die "\$HOME が見つかりません"
UID_NUM="$(id -u)"
# root で走ると gui/0 に登録は無く、$HOME 配下も自分のものではないので、何も正しく消せない
[ "$UID_NUM" -ne 0 ] || die "sudo なしで実行してください（root では外せません）"

LABEL="jp.feel-physics.recess"
BUNDLE_ID="jp.feel-physics.Recess"
SHARE_DIR="$HOME/.local/share/recess"
STATE_DIR="$HOME/.local/state/recess"
BIN_DIR="$HOME/.local/bin"
APP="$HOME/Applications/Recess.app"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
WATCH_PY="$SHARE_DIR/recess-watch.py"
AFPLAY_WRAPPER="$BIN_DIR/afplay"
AFPLAY_MARKER="recess-afplay-wrapper"   # install.sh が置いたラッパーにはこの行がある

PURGE=0
DRY_RUN=0

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  [dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

# 結果の報告。dry-run では「〜ます」（予定）、本番では「〜ました」（結果）で言い分ける（$1 = 動詞の連用形、$2 = 対象）
did() {
  if [ "$DRY_RUN" -eq 1 ]; then
    say "  [dry-run] ${1}ます: ${2}"
  else
    say "  ${1}ました: ${2}"
  fi
}

# 自分の管理下（$HOME の中で、Recess のもの）だけを rm -rf する
safe_rm_rf() {
  case "$1" in
    "$HOME"/?*) ;;
    *) die "安全のため消しません（\$HOME の外です）: $1" ;;
  esac
  case "$1" in
    *"/.."*|*"/../"*) die "安全のため消しません（.. を含みます）: $1" ;;
  esac
  rm -rf "$1"
}

usage() {
  cat <<'EOF'
Recess uninstaller (macOS)

  sh uninstall.sh [オプション]

オプション:
  --purge     ログと状態（~/.local/state/recess）も消す
  --dry-run   何をするかだけ表示して、何も変えない
  -h, --help  この説明を表示する
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --purge)   PURGE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "知らないオプションです: $1" ;;
  esac
  shift
done

say "Recess uninstaller (macOS)"
[ "$DRY_RUN" -eq 1 ] && say "※ --dry-run: 表示だけで、何も変えません"
say ""

# ---------- 1. launchd ----------

say "[1/7] launchd の登録を外します"
if launchctl print "gui/$UID_NUM/$LABEL" >/dev/null 2>&1; then
  # 外せなくても止まらず、あとの削除へ進む（plist が消えれば次回ログインからは載らない）
  if run launchctl bootout "gui/$UID_NUM/$LABEL"; then
    did 外し "gui/$UID_NUM/$LABEL"
  else
    warn "外せませんでした: gui/$UID_NUM/${LABEL}（続行します。手で外すなら launchctl bootout gui/$UID_NUM/${LABEL}）"
  fi
else
  say "  登録されていません: gui/$UID_NUM/$LABEL"
fi
# launchd 以外から手で起動した常駐が残っていれば止める。
# pkill -f は argv の部分一致（正規表現）で、vim で recess-watch.py を開いているだけのプロセスまで落とすので使わない。
# 「<python3 系の1語> <常駐スクリプトのフルパス>」のちょうど2語のものだけを止める（/usr/bin/python3 は argv[0] が .../MacOS/Python になるので大文字も見る）
for pid in $(pgrep -f "$WATCH_PY" 2>/dev/null || true); do
  args="$(ps -ww -o args= -p "$pid" 2>/dev/null || true)"
  case "$args" in
    *" $WATCH_PY") first="${args% $WATCH_PY}" ;;
    *) continue ;;
  esac
  case "$first" in
    *" "*) continue ;;                 # 引数が3つ以上（-c など）は対象外
    *[Pp]ython*)
      if [ "$DRY_RUN" -eq 1 ]; then
        say "  [dry-run] 手動起動の常駐を止めます (pid $pid)"
      elif kill "$pid" 2>/dev/null; then
        say "  手動起動の常駐も止めました (pid $pid)"
      fi ;;
  esac
done

# ---------- 2. plist ----------

say "[2/7] plist を消します"
if [ -f "$PLIST" ]; then
  run rm -f "$PLIST"
  did 消し "$PLIST"
else
  say "  ありません: $PLIST"
fi

# ---------- 3. Recess.app ----------

say "[3/7] Recess.app を消します"
# シンボリックリンクや壊れた残骸（フォルダでないもの）も、この名前なら Recess のものとして消す
if [ -e "$APP" ] || [ -L "$APP" ]; then
  run safe_rm_rf "$APP"
  did 消し "$APP"
else
  say "  ありません: $APP"
fi
# install.sh が置き換えの途中で止まったときに残りうる「脇へどけた旧 app」も消す
for old in "$HOME/Applications"/.Recess.app.old.*; do
  if [ -e "$old" ] || [ -L "$old" ]; then
    run safe_rm_rf "$old"
    did 消し "${old}（作り直しの残骸）"
  fi
done

# ---------- 4. 常駐スクリプト ----------

say "[4/7] 常駐スクリプトの置き場を消します"
if command -v herdr >/dev/null 2>&1; then
  run herdr plugin unlink recess >/dev/null 2>&1 || true
  say "  herdr プラグイン recess の登録を外しました（無ければ何もしません）"
fi
if [ -L "$BIN_DIR/recess" ]; then
  case "$(readlink "$BIN_DIR/recess")" in "$SHARE_DIR"/*) run rm -f "$BIN_DIR/recess"; did 消し "$BIN_DIR/recess" ;; esac
fi
if [ -d "$SHARE_DIR" ]; then
  run safe_rm_rf "$SHARE_DIR"
  did 消し "$SHARE_DIR"
else
  say "  ありません: $SHARE_DIR"
fi

# ---------- 5. afplay ラッパー ----------

say "[5/7] afplay ラッパーを確認します"
if [ -e "$AFPLAY_WRAPPER" ] || [ -L "$AFPLAY_WRAPPER" ]; then
  if grep -q "$AFPLAY_MARKER" "$AFPLAY_WRAPPER" 2>/dev/null; then
    run rm -f "$AFPLAY_WRAPPER"
    did 消し "${AFPLAY_WRAPPER}（Recess のラッパーでした）"
  else
    say "  Recess のものではないので残します: $AFPLAY_WRAPPER"
  fi
else
  say "  ありません: $AFPLAY_WRAPPER"
fi

# ---------- 6. 状態とログ ----------

say "[6/7] 状態とログ"
if [ -d "$STATE_DIR" ]; then
  if [ "$PURGE" -eq 1 ]; then
    run safe_rm_rf "$STATE_DIR"
    did 消し "$STATE_DIR"
  else
    say "  残しました: ${STATE_DIR}（消すなら sh uninstall.sh --purge）"
  fi
else
  say "  ありません: $STATE_DIR"
fi

# ---------- 7. 手動の後片づけ ----------

say "[7/7] 手動で消すもの（macOS の許可一覧は、このスクリプトからは消しません）"
say "  システム設定 → プライバシーとセキュリティ → アクセシビリティ で Recess を選び「−」で消す"
say "  同じく プライバシーとセキュリティ → オートメーション に Recess が残っていれば消す"
say "  （オートメーションの分は tccutil reset AppleEvents $BUNDLE_ID で消えることがあります・未検証。通らなければ手で消してください）"
say ""
say "Done. Recess is removed (Accessibility entry: remove it by hand)."
