#!/bin/sh
# Recess installer for macOS — herdr の AI に呼ばれたらスペースキーを1回押す小さな常駐を入れる
#
# 使い方（パイプ実行ではなく、いったん保存してから実行する）:
#   curl -fsSLO https://raw.githubusercontent.com/tatsuro-ueda/recess/main/install.sh
#   sh install.sh [--with-afplay] [--rebuild-app] [--fetch] [--dry-run]
#
# このスクリプトは実行時に常駐本体 recess-watch.py も取得する（同梱されていなければ）。
# 読んでから入れたい人は https://raw.githubusercontent.com/tatsuro-ueda/recess/main/recess-watch.py（GitHub にも同じもの）を先に読む。
#
# やること:
#   1. macOS 14 以降と必須コマンド（herdr 0.9.1+, python3, osacompile, launchctl, lsappinfo, codesign, plutil, PlistBuddy）を確認
#   2. ~/.local/share/recess と ~/.local/state/recess を作る
#   3. recess-watch.py を置く（同じフォルダに同梱されていればそこから、無ければ RECESS_BASE_URL から取得。--fetch で取得を強制）
#   4. ~/Applications/Recess.app を osacompile で生成（一時フォルダで組み立てて署名まで確かめてから置く。
#      既にあって壊れていなければ作り直さない。--rebuild-app で作り直す）
#   5. launchd の plist を生成して登録する（RunAtLoad / KeepAlive）
#   6. --with-afplay のときだけ ~/.local/bin/afplay（効果音の横取り）を置く
#   7. アクセシビリティ許可の手順・ログの場所・止め方を表示する
#
# 方針: sudo は使わない（root では動かさない）。消すのは自分が作ったものだけ。何度実行しても同じ結果になる（冪等）。
# 環境変数: RECESS_BASE_URL（既定 GitHub raw の main）、RECESS_FALLBACK_URL（既定 GitHub raw の HEAD）。どちらも https のみ（curl --proto '=https'）
set -eu

# ---------- 小道具（$HOME を使う前に定義する） ----------

say()  { printf '%s\n' "$*"; }
warn() { printf '警告: %s\n' "$*" >&2; }
die()  { printf 'エラー: %s\n' "$*" >&2; exit 1; }

# ---------- 変数を組み立てる前に止めるべきもの ----------

[ "$(uname -s)" = "Darwin" ] || die "macOS 専用です（このOS: $(uname -s)）"
[ -n "${HOME:-}" ] && [ -d "$HOME" ] || die "\$HOME が見つかりません"
UID_NUM="$(id -u)"
# root で走ると $HOME 配下が root 所有になり、launchd の gui/0 も無いので必ず失敗する。あとで自分では消せなくなる
[ "$UID_NUM" -ne 0 ] || die "sudo なしで実行してください（root では入れられません）"

RECESS_VERSION="0.1.0"
APP_BUILD="1"                          # Recess.app の中身（AppleScript・Info.plist）を変えたら上げる。版が違えば作り直す
LABEL="jp.feel-physics.recess"          # launchd のラベル（plist のファイル名にもなる）
BUNDLE_ID="jp.feel-physics.Recess"      # Recess.app の識別子（アクセシビリティ許可はこれに紐づく）
USAGE_DESC="前面のアプリへスペースキーを1回送るために、System Events を使います。"  # オートメーション許可のダイアログに出る文
BASE_URL="${RECESS_BASE_URL:-https://raw.githubusercontent.com/tatsuro-ueda/recess/main}"
FALLBACK_URL="${RECESS_FALLBACK_URL:-https://raw.githubusercontent.com/tatsuro-ueda/recess/HEAD}"
MIN_MACOS="14"
MIN_HERDR="0.9.1"

SHARE_DIR="$HOME/.local/share/recess"   # 常駐スクリプトの置き場
STATE_DIR="$HOME/.local/state/recess"   # 状態とログ
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/Applications"
APP="$APP_DIR/Recess.app"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/$LABEL.plist"
WATCH_PY="$SHARE_DIR/recess-watch.py"
AFPLAY_WRAPPER="$BIN_DIR/afplay"
AFPLAY_MARKER="recess-afplay-wrapper"   # この文字列が入っていれば「Recess が置いたラッパー」と判断する
LEGACY_PLIST="$PLIST_DIR/jp.feel-physics.herdr-dark-while-working.plist"  # 作者の旧版（触らない）

WITH_AFPLAY=0
REBUILD_APP=0
FETCH=0
DRY_RUN=0
OLD_APP=""     # Recess.app を置き換えるとき、旧 app を一時的に脇へどけた先（cleanup が後始末する）

# ---------- 小道具（続き） ----------

# --dry-run のときは実行せず、何をするかだけ表示する
run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  [dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

# $1 >= $2 なら 0 を返す（"14.3.1" と "14" のような比較もできる）
vercmp() {
  awk -v a="$1" -v b="$2" 'BEGIN {
    n = split(a, x, "."); m = split(b, y, ".")
    for (i = 1; i <= (n > m ? n : m); i++) {
      p = (x[i] == "" ? 0 : x[i]) + 0; q = (y[i] == "" ? 0 : y[i]) + 0
      if (p < q) exit 1
      if (p > q) exit 0
    }
    exit 0
  }'
}

# plist（XML）に埋め込む文字列をエスケープする（$HOME に & などが入っていても壊れないように）
xml_escape() {
  printf '%s' "$1" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g'
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
Recess installer (macOS)

  sh install.sh [オプション]

オプション:
  --with-afplay   herdr の効果音を横取りする ~/.local/bin/afplay も入れる（任意）
  --rebuild-app   ~/Applications/Recess.app を作り直す（アクセシビリティの許可が外れることがある）
  --fetch         同じフォルダに recess-watch.py があっても使わず、取得元から取り直す
  --dry-run       何をするかだけ表示して、何も変えない（通信もしない）
  -h, --help      この説明を表示する

環境変数:
  RECESS_BASE_URL       recess-watch.py の取得元（既定 GitHub raw の main。https のみ）
  RECESS_FALLBACK_URL   取得元が落ちているときの予備（既定 GitHub raw。https のみ）
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --with-afplay) WITH_AFPLAY=1 ;;
    --rebuild-app) REBUILD_APP=1 ;;
    --fetch)       FETCH=1 ;;
    --dry-run)     DRY_RUN=1 ;;
    -h|--help)     usage; exit 0 ;;
    *) usage >&2; die "知らないオプションです: $1" ;;
  esac
  shift
done

# 一時フォルダ（終了時に自分で消す）
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/recess-install.XXXXXX")"

# 終了時の後始末。die や Ctrl-C で途中停止しても、一時フォルダと「脇へどけた旧 Recess.app」を残さない。
# 新しい app が置けていれば旧 app を消し、置けていなければ旧 app を元の場所へ戻す（許可済みの app を失わない）
cleanup() {
  rc=$?
  if [ -n "$OLD_APP" ] && { [ -e "$OLD_APP" ] || [ -L "$OLD_APP" ]; }; then
    if [ -e "$APP" ] || [ -L "$APP" ]; then
      rm -rf "$OLD_APP"
    else
      mv "$OLD_APP" "$APP" 2>/dev/null || true
    fi
  fi
  rm -rf "$TMP_DIR"
  exit $rc
}
trap cleanup EXIT

# install.sh と同じフォルダ（同梱の recess-watch.py を探す場所）
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || printf '.')"

say "Recess installer $RECESS_VERSION (macOS)"
[ "$DRY_RUN" -eq 1 ] && say "※ --dry-run: 表示だけで、何も変えません"
say ""

# ---------- 1. 環境確認 ----------

say "[1/7] 環境を確認します"

OS_VER="$(sw_vers -productVersion 2>/dev/null || printf '0')"
vercmp "$OS_VER" "$MIN_MACOS" || die "macOS $OS_VER は対象外です。macOS $MIN_MACOS 以降が必要です"
say "  macOS $OS_VER"

# macOS 標準のはずのコマンド
for c in osacompile launchctl lsappinfo codesign plutil; do
  command -v "$c" >/dev/null 2>&1 || die "必須コマンドが見つかりません: ${c}（macOS 標準のコマンドです。PATH を確認してください）"
done
[ -x /usr/libexec/PlistBuddy ] || die "/usr/libexec/PlistBuddy が見つかりません（macOS 標準のはずです）"

# herdr（CLI が PATH にあること）
HERDR_BIN="$(command -v herdr 2>/dev/null)" || die "herdr が見つかりません。herdr $MIN_HERDR 以降を入れて、PATH に通してから実行してください"
HERDR_VER="$("$HERDR_BIN" --version 2>/dev/null | awk 'NR==1 {print $2}')"
case "$HERDR_VER" in
  ''|*[!0-9.]*)
    warn "herdr のバージョンが読み取れません（'$HERDR_VER'）。$MIN_HERDR 以降であることを前提に続けます" ;;
  *)
    vercmp "$HERDR_VER" "$MIN_HERDR" || die "herdr $HERDR_VER は古いです。$MIN_HERDR 以降が必要です（herdr update で更新できます）"
    say "  herdr $HERDR_VER ($HERDR_BIN)" ;;
esac

# python3。/usr/bin/python3 は Command Line Tools が無いと「開発ツールを入れますか」のダイアログを出す
# 「スタブ」なので、先に xcode-select で実体があるかを見る
if [ -x /usr/bin/python3 ] && xcode-select -p >/dev/null 2>&1; then
  PYTHON3="/usr/bin/python3"
else
  PYTHON3="$(command -v python3 2>/dev/null || true)"
  if [ -z "$PYTHON3" ] || [ "$PYTHON3" = "/usr/bin/python3" ]; then
    die "使える python3 がありません。'xcode-select --install' で Command Line Tools を入れるか、python.org / Homebrew の python3 を入れてください"
  fi
fi
# -B: バイトコードのキャッシュを書かせない（Apple の python3 は ~/Library/Caches/com.apple.python に書く。--dry-run で何も残さないため）
"$PYTHON3" -B -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null \
  || die "python3 が古いか動きません: ${PYTHON3}（3.8 以降が必要です）"
say "  python3 $("$PYTHON3" -B -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])') ($PYTHON3)"

# launchd の gui ドメイン（GUI にログインしたユーザーのセッション）。SSH だけのログインだと無いことがある
GUI_DOMAIN_OK=1
if ! launchctl print "gui/$UID_NUM" >/dev/null 2>&1; then
  GUI_DOMAIN_OK=0
  warn "launchd の gui/$UID_NUM ドメインが見えません。Mac の画面にログインした状態のターミナルから実行してください（SSH 越しだと [5/7] の登録に失敗します。ファイルは置かれるので、あとで登録だけやり直せます）"
fi

if [ -f "$LEGACY_PLIST" ]; then
  warn "旧版（jp.feel-physics.herdr-dark-while-working）も登録されています。Recess と両方が動くとスペースが2回送られるので、どちらかを止めてください。このスクリプトは旧版に触りません"
fi

# ---------- 2. フォルダ ----------

say "[2/7] フォルダを用意します"
run mkdir -p "$SHARE_DIR" "$STATE_DIR"
say "  $SHARE_DIR"
say "  $STATE_DIR"

# ---------- 3. recess-watch.py ----------

say "[3/7] recess-watch.py を置きます"

fetch_file() {
  # $1 = ファイル名、$2 = 保存先。取得元 → 予備 の順に試す。HTTPS 以外は拒否する
  command -v curl >/dev/null 2>&1 || die "curl が見つかりません（同梱の $1 が無いので取得が必要です）"
  for base in "$BASE_URL" "$FALLBACK_URL"; do
    url="${base%/}/$1"
    say "  取得: $url"
    if curl -fsSL --proto '=https' --tlsv1.2 --retry 2 --retry-delay 1 --connect-timeout 10 --max-time 60 -o "$2" "$url"; then
      return 0
    fi
    warn "取得できませんでした: $url"
  done
  return 1
}

fetch_watch_py() {
  # $1 = 保存先。取得元 → 予備 の順に試す。HTTPS 以外は拒否する
  command -v curl >/dev/null 2>&1 || die "curl が見つかりません（同梱の recess-watch.py が無いので取得が必要です）"
  for base in "$BASE_URL" "$FALLBACK_URL"; do
    url="${base%/}/recess-watch.py"
    say "  取得: $url"
    if curl -fsSL --proto '=https' --tlsv1.2 --retry 2 --retry-delay 1 --connect-timeout 10 --max-time 60 -o "$1" "$url"; then
      return 0
    fi
    warn "取得できませんでした: $url"
  done
  return 1
}

STAGED_PY="$TMP_DIR/recess-watch.py"
BUNDLED_PY="$SCRIPT_DIR/recess-watch.py"
if [ "$FETCH" -eq 0 ] && [ -f "$BUNDLED_PY" ]; then
  # 同梱ファイルは無条件に優先する。~/Downloads に古い版が残っていると古い版を入れ直すことになるので、日付を見せておく
  say "  同梱の recess-watch.py を使います: $BUNDLED_PY"
  say "  （$(stat -f '更新 %Sm・%z バイト' -t '%Y-%m-%d %H:%M' "$BUNDLED_PY" 2>/dev/null || printf '日付不明')。取得元の最新を使うなら --fetch を付けるか、このファイルを消してから実行）"
  cp "$BUNDLED_PY" "$STAGED_PY"
elif [ "$DRY_RUN" -eq 1 ]; then
  # dry-run では通信もしない
  say "  [dry-run] 取得: ${BASE_URL%/}/recess-watch.py（予備: ${FALLBACK_URL%/}/recess-watch.py）"
else
  fetch_watch_py "$STAGED_PY" || die "recess-watch.py を取得できませんでした。ネットワークか RECESS_BASE_URL（${BASE_URL}）を確認してください"
fi
if [ -f "$STAGED_PY" ]; then
  [ -s "$STAGED_PY" ] || die "recess-watch.py が空です"
  # 置く前に Python として読めるかだけ確かめる（実行はしない）
  "$PYTHON3" -B -c 'import ast, sys; ast.parse(open(sys.argv[1], encoding="utf-8").read())' "$STAGED_PY" \
    || die "取得した recess-watch.py が Python として読めません（途中で切れた可能性があります）"
fi
# -S: 一時ファイルへ書いてから rename する（途中で止まっても、書きかけの recess-watch.py が本番パスに残らない）
run install -S -m 0755 "$STAGED_PY" "$WATCH_PY"
say "  $WATCH_PY"

# モード切替（recess on/off）と herdr プラグイン（アクション）。同梱があればそれを、無ければ取得
for f in recess-mode.sh herdr-plugin.toml; do
  staged="$TMP_DIR/$f"
  if [ "$FETCH" -eq 0 ] && [ -f "$SCRIPT_DIR/$f" ]; then
    cp "$SCRIPT_DIR/$f" "$staged"
  elif [ "$DRY_RUN" -eq 1 ]; then
    say "  [dry-run] 取得: ${BASE_URL%/}/$f"
  else
    fetch_file "$f" "$staged" || die "$f を取得できませんでした"
  fi
  if [ -f "$staged" ]; then
    [ -s "$staged" ] || die "$f が空です"
    case "$f" in *.sh) mode=0755 ;; *) mode=0644 ;; esac
    run install -S -m "$mode" "$staged" "$SHARE_DIR/$f"
    say "  $SHARE_DIR/$f"
  fi
done
run mkdir -p "$BIN_DIR"
run ln -sf "$SHARE_DIR/recess-mode.sh" "$BIN_DIR/recess"
say "  ${BIN_DIR}/recess（recess on|off|toggle|status。PATH に ${BIN_DIR} が無ければフルパスで）"
if [ "$DRY_RUN" -eq 1 ]; then
  say "  [dry-run] herdr plugin link ${SHARE_DIR}（herdr のアクション: recess.on / recess.off / recess.toggle / recess.status）"
else
  "$HERDR_BIN" plugin unlink recess >/dev/null 2>&1 || true
  if "$HERDR_BIN" plugin link "$SHARE_DIR" >/dev/null 2>&1; then
    say "  herdr プラグイン recess を登録しました（herdr plugin action invoke recess.toggle で切り替え）"
  else
    warn "herdr プラグインの登録に失敗しました（herdr サーバーが動いていないときは、あとで 'herdr plugin link ${SHARE_DIR}' を実行）"
  fi
fi

# ---------- 4. Recess.app ----------

say "[4/7] Recess.app を用意します"

# 既にある Recess.app が健全か: 署名が通り、識別子と版が合っていること。
# 途中で失敗した過去の残骸（封が破れた app）をこの判定で見抜き、温存しない
app_is_healthy() {
  [ -d "$APP" ] || return 1
  codesign --verify --strict "$APP" >/dev/null 2>&1 || return 1
  [ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist" 2>/dev/null)" = "$BUNDLE_ID" ] || return 1
  [ "$(/usr/libexec/PlistBuddy -c 'Print :RecessAppBuild' "$APP/Contents/Info.plist" 2>/dev/null)" = "$APP_BUILD" ] || return 1
  return 0
}

# 一時フォルダに組み立てる: osacompile → Info.plist 調整 → ad-hoc 署名 → 検証。
# ここで失敗しても本番パス（~/Applications）には何も残らない
build_app() {
  BUILD_APP="$TMP_DIR/Recess.app"
  # 中身は1行。前面のアプリへスペースキー（key code 49）を1回送るだけ。
  # osacompile は成功時も stderr に ".: replacing existing signature" と出すことがあるので、失敗したときだけ見せる
  osacompile -o "$BUILD_APP" -e 'tell application "System Events" to key code 49' 2>"$TMP_DIR/osacompile.err" \
    || { cat "$TMP_DIR/osacompile.err" >&2; die "osacompile に失敗しました"; }
  INFO_PLIST="$BUILD_APP/Contents/Info.plist"
  pb() { /usr/libexec/PlistBuddy -c "$1" "$INFO_PLIST"; }
  # osacompile の既定には CFBundleIdentifier が無い。許可はこの識別子に紐づくので固定する
  pb "Set :CFBundleIdentifier $BUNDLE_ID" 2>/dev/null || pb "Add :CFBundleIdentifier string $BUNDLE_ID"
  # Dock に出さない（0.5秒だけ起動するアプリなので、跳ねると邪魔になる）
  pb "Set :LSUIElement true" 2>/dev/null || pb "Add :LSUIElement bool true"
  # System Events を使う理由（オートメーション許可のダイアログに出る文）
  pb "Set :NSAppleEventsUsageDescription $USAGE_DESC" 2>/dev/null || pb "Add :NSAppleEventsUsageDescription string $USAGE_DESC"
  # 版。中身を変えたら APP_BUILD を上げる → 次回の実行で「版が違う」と判定され、作り直される
  pb "Set :RecessAppBuild $APP_BUILD" 2>/dev/null || pb "Add :RecessAppBuild string $APP_BUILD"
  # Info.plist を書き換えると署名の封が破れるので、ad-hoc（開発者IDなし）で署名し直す。
  # 失敗を捨てると「封が破れたまま無言終了」になるので、stderr を残して止める
  codesign --force --sign - "$BUILD_APP" 2>"$TMP_DIR/codesign.err" \
    || { cat "$TMP_DIR/codesign.err" >&2; die "Recess.app の署名に失敗しました"; }
  codesign --verify --strict "$BUILD_APP" 2>"$TMP_DIR/codesign.err" \
    || { cat "$TMP_DIR/codesign.err" >&2; die "組み立てた Recess.app の署名確認に失敗しました"; }
}

APP_STATUS="kept"
if [ "$REBUILD_APP" -eq 0 ] && app_is_healthy; then
  say "  既にあり、壊れていないので作り直しません: ${APP}（作り直すには --rebuild-app）"
else
  if [ ! -e "$APP" ] && [ ! -L "$APP" ]; then
    APP_STATUS="created"
    say "  作ります: $APP"
  elif [ "$REBUILD_APP" -eq 1 ]; then
    APP_STATUS="rebuilt"
    say "  --rebuild-app なので作り直します: $APP"
  else
    APP_STATUS="rebuilt"
    say "  既にありますが、署名が通らないか識別子・版が違うので作り直します: $APP"
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    say "  [dry-run] osacompile で一時フォルダに組み立て → Info.plist 調整（${BUNDLE_ID} / LSUIElement / RecessAppBuild=${APP_BUILD}）→ codesign → 検証 → ${APP} へ置く"
  else
    build_app
    mkdir -p "$APP_DIR"
    # 旧 app は消さずに同じフォルダ内で脇へどけ（rename だけなので一瞬）、新しい app を置けたあとで消す。
    # 置けなかったときは cleanup が旧 app を戻すので、許可済みの app を失わない
    if [ -e "$APP" ] || [ -L "$APP" ]; then
      OLD_APP="$APP_DIR/.Recess.app.old.$$"
      safe_rm_rf "$OLD_APP"
      mv "$APP" "$OLD_APP"
    fi
    mv "$BUILD_APP" "$APP" || die "Recess.app を置けませんでした: $APP"
    if ! codesign --verify --strict "$APP" 2>"$TMP_DIR/codesign.err"; then
      cat "$TMP_DIR/codesign.err" >&2
      safe_rm_rf "$APP"   # 壊れた app を本番パスに残さない（旧 app があれば cleanup が戻す）
      die "置いた Recess.app の署名確認に失敗しました: $APP"
    fi
    if [ -n "$OLD_APP" ]; then
      safe_rm_rf "$OLD_APP"
      OLD_APP=""
    fi
  fi
  say "  ${APP}（${BUNDLE_ID}, build ${APP_BUILD}）"
fi

# ---------- 5. launchd ----------

say "[5/7] launchd に登録します"

# herdr のあるフォルダを PATH の先頭に足す（~/.local/bin 以外に入っていても見つかるように）
HERDR_DIR="$(dirname "$HERDR_BIN")"
AGENT_PATH="$BIN_DIR:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
case ":$AGENT_PATH:" in
  *":$HERDR_DIR:"*) ;;
  *) AGENT_PATH="$HERDR_DIR:$AGENT_PATH" ;;
esac

# launchd は ~ や $HOME を展開しないので、ここで絶対パスに直して書き込む。
# 環境変数の名前は recess-watch.py が読むもの（RECESS_HERDR_BIN）に合わせる。
# KeepAlive は「異常終了したときだけ再起動」にする。recess-watch.py が前提（herdr など）を失って
# exit 0 で終わったとき、5秒おきに起動し直す無限ループにならないようにするため
STAGED_PLIST="$TMP_DIR/$LABEL.plist"
cat >"$STAGED_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(xml_escape "$PYTHON3")</string>
    <string>$(xml_escape "$WATCH_PY")</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$(xml_escape "$AGENT_PATH")</string>
    <key>RECESS_HERDR_BIN</key><string>$(xml_escape "$HERDR_BIN")</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key><false/>
  </dict>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>$(xml_escape "$STATE_DIR/watch.stdout.log")</string>
  <key>StandardErrorPath</key><string>$(xml_escape "$STATE_DIR/watch.stderr.log")</string>
</dict>
</plist>
EOF
plutil -lint -s "$STAGED_PLIST" >/dev/null || die "生成した plist が壊れています: $STAGED_PLIST"

run mkdir -p "$PLIST_DIR"
run install -S -m 0644 "$STAGED_PLIST" "$PLIST"
say "  $PLIST"

# 過去に launchctl disable / unload -w されていると bootstrap が "119: Service is disabled" で落ちるので、先に enable する（冪等・無害）。
# 登録済みなら外してから入れ直す（bootstrap は二重登録を拒むため）。未登録の bootout は失敗してよい
if [ "$DRY_RUN" -eq 1 ]; then
  run launchctl enable "gui/$UID_NUM/$LABEL"
  run launchctl bootout "gui/$UID_NUM/$LABEL"
  run launchctl bootstrap "gui/$UID_NUM" "$PLIST"
else
  launchctl enable "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 || true
  launchctl bootout "gui/$UID_NUM/$LABEL" >/dev/null 2>&1 || true
  n=0
  while ! launchctl bootstrap "gui/$UID_NUM" "$PLIST" 2>"$TMP_DIR/bootstrap.err"; do
    n=$((n + 1))
    if [ "$n" -ge 5 ]; then
      cat "$TMP_DIR/bootstrap.err" >&2
      if [ "$GUI_DOMAIN_OK" -eq 0 ]; then
        die "launchd への登録に失敗しました（gui/$UID_NUM ドメインが見えません。SSH 越しだとこうなります）。ファイルは置き終わっています。Mac の画面にログインしたターミナルから sh install.sh をもう一度実行するか、launchctl bootstrap gui/$UID_NUM $PLIST を打てば動きます（次回ログイン時には自動で載ります）"
      fi
      die "launchd への登録に失敗しました。ファイルは置き終わっています。上のメッセージを直してから sh install.sh をもう一度実行するか、launchctl bootstrap gui/$UID_NUM $PLIST を打ってください"
    fi
    sleep 1   # bootout 直後は前の登録が消えきっていないことがあるので、少し待って再試行する
  done
  sleep 1   # 登録直後は state = xpcproxy（起動中）なので、落ち着いてから読む
  JOB_STATE="$(launchctl print "gui/$UID_NUM/$LABEL" 2>/dev/null | awk '/^\tstate = / {print $3; exit}')"
  say "  登録しました: gui/$UID_NUM/${LABEL}（state = ${JOB_STATE:-unknown}）"
fi

# ---------- 6. afplay ラッパー（任意） ----------

say "[6/7] afplay ラッパー（効果音の横取り・任意）"

AFPLAY_STATUS="none"
if [ "$WITH_AFPLAY" -eq 0 ]; then
  say "  --with-afplay が無いので入れません"
elif { [ -e "$AFPLAY_WRAPPER" ] || [ -L "$AFPLAY_WRAPPER" ]; } && ! grep -q "$AFPLAY_MARKER" "$AFPLAY_WRAPPER" 2>/dev/null; then
  warn "既に別の afplay ラッパーがあるので上書きしません: ${AFPLAY_WRAPPER}（Recess のものは '$AFPLAY_MARKER' という行を含みます）"
  AFPLAY_STATUS="skipped"
else
  STAGED_AFPLAY="$TMP_DIR/afplay"
  cat >"$STAGED_AFPLAY" <<'EOF'
#!/bin/sh
# recess-afplay-wrapper v1 — uninstall.sh はこの行を見て「Recess が置いたもの」と判断する
# herdr が効果音（完了・質問）を鳴らす瞬間だけ Recess に知らせ、画面を点ける。
# 他マシンのエージェントの出来事も Mac の herdr 側で音になるので、ここで拾える。
# それ以外の呼び出しは何もせず本物の afplay へ渡す。
parent="$(ps -o comm= -p "$PPID" 2>/dev/null)"
case "$parent" in
  *herdr*)
    state="$HOME/.local/state/recess"   # recess-watch.py の STATE_DIR と同じ場所（固定。環境変数では変えられない）
    mkdir -p "$state" 2>/dev/null
    printf '%s WAKE (sound: %s)\n' "$(date '+%F %T')" "$(basename "${1:-?}")" >>"$state/sound.log" 2>/dev/null
    printf '%s\n' "${1:-?}" >"$state/sound-event" 2>/dev/null   # 最後に鳴った音の記録（今の recess-watch.py はこのファイルを読まない）
    caffeinate -u -t 2 >/dev/null 2>&1 &
    ;;
esac
exec /usr/bin/afplay "$@"
EOF
  run mkdir -p "$BIN_DIR"
  run install -S -m 0755 "$STAGED_AFPLAY" "$AFPLAY_WRAPPER"
  AFPLAY_STATUS="installed"
  say "  $AFPLAY_WRAPPER"
  # herdr から見た afplay がこのラッパーになるには、PATH で ~/.local/bin が /usr/bin より前に要る
  if [ "$DRY_RUN" -eq 0 ]; then
    RESOLVED_AFPLAY="$(command -v afplay 2>/dev/null || true)"
    [ "$RESOLVED_AFPLAY" = "$AFPLAY_WRAPPER" ] \
      || warn "このシェルでは afplay が $RESOLVED_AFPLAY に解決されます。herdr を起動するシェルの PATH で $BIN_DIR を /usr/bin より前に置いてください（例: export PATH=\"\$HOME/.local/bin:\$PATH\"）"
  fi
fi

# ---------- 7. 案内 ----------

if [ "$DRY_RUN" -eq 1 ]; then
  say "[7/7] --dry-run なので、何も変えていません（実行するには --dry-run を外してもう一度）"
else
  say "[7/7] 入れ終わりました"
fi
say ""
say "次にやること（手動・1回だけ）:"
say "  システム設定 → プライバシーとセキュリティ → アクセシビリティ を開き、"
say "  「+」で $APP を追加してオンにする"
say "  （置き場は自分のホームの Applications フォルダです。/Applications ではありません。open $APP_DIR で Finder に出せます）"
case "$APP_STATUS" in
  rebuilt) say "  ※ Recess.app を作り直しました。許可が外れていたら、一覧の古い Recess を「−」で消してから「+」で入れ直してください（中身が同じ作り直しなら、そのまま残ることがあります）" ;;
esac
say "  初めてスペースが送られるとき「Recess が System Events を制御しようとしています」と聞かれたら「許可」を選ぶ"
say "  （これはオートメーションの許可で、アクセシビリティとは別の2つ目。どちらも相手は Recess.app だけで、python3 には許可を出しません）"
say ""
say "ログ:      $STATE_DIR/watch.log（常駐の記録）"
say "           $STATE_DIR/watch.stderr.log（launchd から起動できないときはここ。stdout は watch.stdout.log）"
say "止める:    launchctl bootout gui/$UID_NUM/$LABEL"
say "動かす:    launchctl bootstrap gui/$UID_NUM $PLIST"
say "様子を見る: launchctl print gui/$UID_NUM/$LABEL | grep state"
say "切り替え:  recess on|off|toggle|status（herdr からは herdr plugin action invoke recess.toggle）"
say "外す:      sh uninstall.sh（ログも消すなら --purge）"
case "$AFPLAY_STATUS" in
  installed) say "afplay:    ${AFPLAY_WRAPPER}（herdr の効果音を横取りして画面を点けます）" ;;
esac
say ""
if [ "$DRY_RUN" -eq 1 ]; then
  say "Done (dry-run). Nothing was changed."
else
  say "Done. Grant Accessibility to $APP, then Recess is live."
fi
