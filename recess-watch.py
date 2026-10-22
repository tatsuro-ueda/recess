#!/usr/bin/env python3
"""Recess — AI が働いている間はブラウザの動画を再生し、呼ばれたら止めてターミナルへ戻る常駐。

名前の由来: 「スペースキーを1回押すだけの小さなアプリ（Recess.app）」。
このファイルは AI（Claude）に書かせ、判断は作者（植田）がした。

何をするか
  herdr のエージェント状態を Mac＋他マシン（herdr machine list の enabled なもの）から
  2秒おきに集め、次の2つを1か所で判定する。
  見ている : 「見ている端末（最後にフォーカスが動いた側）」で、フォーカス中のペインと同じタブに
             あるペイン全部（herdr の tab_id で束ねる。同じタブの2ペインは一体で判断する）。
  待ち時間 : 見ているタブのどれかの AI が working で、そのタブに読み中（reading）のペインが無く、
             blocked/done がどこにも無く、手を離して HANDS_OFF 秒、最前面がターミナルのとき
             → 最後に見ていたブラウザ（既定 Safari）を前に出し、Recess.app でスペース1回（再生）。
             idle は「次を打つ準備」なので行かない。
  呼ばれた : どこかに blocked(ask) / done(stop・未読) が新しく現れた、または見ているタブのペインが
             working→idle になったとき → 画面を点け、最前面がブラウザならスペース1回（一時停止）
             →0.3秒→ターミナルを前に出す。ターミナルを見ているなら押さない。
  猶予     : 呼び戻し後 RETURN_COOLDOWN 秒はブラウザへ行かない（既定 0）。
  reading  : 見ているタブのペインが done/working→idle になったら読み中。
             見ている端末で別のペインへ移ったら終わる。
             画面に印を出すのは、そのうち「いま開いているペイン」1つだけ（読む人は1人）。
             読み中のあいだは「reading」、読み終わって離れたら「read」と出す（herdr pane report-metadata の
             display-only なカスタムトークン `$recess`。TTL 付きなので常駐が落ちたら自然に消える）。
             idle と reading は herdr から見ると同じ idle で、画面では見分けられないため
             （ユーザー報告 2026-09-28）。
             サイドバーの行に `$recess` を置いていれば、そのトークンで出す。置いていなければ
             エージェント名（display_agent）を差し替えて出す。既定の行構成でも必ず出る側へ
             倒すので、設定を触らなくても印は見える。設定例は docs/install.md。
             `$recess` を置くと、その1語だけ色を変えられる。`agent` トークンを塗ると
             claude / codex まで塗られてしまうため（ユーザー判断 2026-10-10）。
             状態の文字（state_label）を使わないのは、サイドバーの行に state_text を入れていないと
             どこにも出ないため（2026-09-29 実測。既定の行構成も state_icon だけ）。
  ジャンプ : Mac のペインが blocked / done になったら herdr agent focus で自動ジャンプ
             （手を離して HANDS_OFF 秒以上、who に SSH ログインが無いとき）。
             呼び戻しだけではターミナルが前に出るところまでで、どのペインが呼んだかは
             自分で探すことになるため（ユーザー判断 2026-09-29）。他マシンのペインへは移れない
             （Mac のローカル herdr がそのペインを持っていない）。

権限
  スペースを押すのは ~/Applications/Recess.app（中身は key code 49 の1行）だけ。
  アクセシビリティ許可と、System Events を制御するオートメーション許可は、このアプリにだけ出す。
  python3 には出さない。
  この常駐が Mac 側で使う道具は権限不要のものだけ: open, lsappinfo, caffeinate, ioreg, who
  （osascript は使わない）。ほかに herdr と、他マシンの状態を取るための ssh を使う
  （鍵は各自の ~/.ssh。パスワードや秘密はこのファイルに持たない）。

分かっている弱点（正直に書く）
  ・スペースは「切り替え」で、再生中かどうかを持たない。ターミナルにいるときは動画を止めておく約束。
  ・Safari＋Netflix でしか確かめていない。
  ・Recess.app を作り直す（install.sh --rebuild-app。壊れているか古い版なら再実行でも作り直す）と
    許可が外れることがある（システム設定で削除→追加し直し）。
    Recess.app が無いときは「cannot open」をログに残してスキップするだけで、落ちはしない。
  ・macOS 14.3.1 と herdr 0.9.1 でしか確かめていない。
  ・作者の Mac 以外で動かした実績はまだ無い。
  ・他マシンでは非対話シェルで `herdr agent list` を実行する。相手の PATH に ~/.local/bin が無いと
    command not found → unreachable 扱いになり、黙って Mac だけの監視になる（ログの
    「remote <label>: unreachable」で気づける）。
  ・enabled なマシンが落ちていると、1周が ConnectTimeout 5秒×台数まで延びる（POLL を超える）。
  ・タブ束ねは `herdr agent list` の tab_id を使う。tab_id を返さない herdr では、ペイン1つずつの判定に戻る。

置き場
  本体   : ~/.local/share/recess/recess-watch.py（python3 標準ライブラリのみ）
  状態   : ~/.local/state/recess/（watch.log ほか）
  launchd: ~/Library/LaunchAgents/jp.feel-physics.recess.plist
           ProgramArguments は install.sh が見つけた python3（通常 /usr/bin/python3）を絶対パスで書き、
           EnvironmentVariables の PATH に ~/.local/bin と herdr のフォルダを入れる（launchd の既定 PATH には無い）。
           KeepAlive は SuccessfulExit=false（異常終了のときだけ再起動）、ThrottleInterval 5 で、落ちても5秒後に戻る。
           同じ役目の常駐を別名で動かしていた人は、両方がスペースを押して打ち消し合うので、
           先に旧いほうを launchctl bootout してから load する。

環境変数（すべて任意。数値が壊れていたら既定へ戻し、起動は止めない）
  RECESS_HERDR_BIN               herdr の場所（既定: PATH から探す → ~/.local/bin/herdr）
  RECESS_REMOTE_HERDR            他マシンでの herdr の場所（既定 "$HOME/.local/bin/herdr"）。
                                相手の PATH に無いときのフォールバックに使う
  RECESS_POLL_SECONDS            状態を集める間隔（既定 2）
  RECESS_HANDS_OFF_SECONDS       「手を離した」とみなす秒数（既定 3）
  RECESS_RETURN_COOLDOWN_SECONDS 呼び戻し後にブラウザへ行かない秒数（既定 0。行き来が気になるときだけ 5 など）
  RECESS_TERMINAL_APPS           ターミナルとみなすプロセス名。空白区切り
                                （既定 "iTerm2 Terminal Ghostty kitty Alacritty WezTerm cmux"）
  RECESS_BROWSER_APPS            ブラウザとみなすアプリ名。名前に空白を含むのでカンマ区切り
                                （既定 "Safari,Comet,Google Chrome,Firefox,Arc,Brave Browser,Microsoft Edge"）
  RECESS_VIDEO_APP               動画を見るアプリを決め打ちしたいときだけ（例 Safari）
  RECESS_DEFAULT_TERMINAL        まだターミナルを見ていないうちに呼ばれたとき open -a に渡す名前（既定 iTerm）
  RECESS_READING_LABEL           読み中のペインに出す文言（既定 "reading"。空にすると出さない）
  RECESS_READ_LABEL              読み終わったペインに出す文言（既定 "read"。空にすると出さない）
  RECESS_READING_NOW_TOKEN       reading を入れるトークン名（既定 "recess_now"）。設定に無ければ recess へ落とす
  RECESS_READ_TOKEN              read を入れるトークン名（既定 "recess_done"）。設定に無ければ recess へ落とす
  RECESS_WORKING_LABEL           作業中のペインに出す文言（既定 "working"。空にすると出さない）
  RECESS_WORKING_TOKEN           working を入れるトークン名（既定 "recess_working"）。設定に無ければ出さない
                                 （$recess へ落とすと作業中の行が全部 to be read と同じ赤になるため）
  RECESS_READING_TOKEN           その文言を入れるカスタムトークン名（既定 "recess"）。サイドバーの行に
                                 $recess があればこれで出し、無ければ display_agent で出す
  RECESS_DRY_RUN=1               判定だけ行い、open / caffeinate / focus / state_label を実行しない

状態は毎回の差分（前回→今回）で見る。
"""
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import time

HOME = os.path.expanduser("~")
STATE_DIR = os.path.join(HOME, ".local/state/recess")
OFF_FILE = os.path.join(STATE_DIR, "off")   # これがあるとき Recess は OFF（状態は追うが、連れ出し・呼び戻し・ジャンプをしない）。recess on/off で切り替える
LOG = os.path.join(STATE_DIR, "watch.log")


def log(msg):
    """ログを1行足す。書けない（ディスク満杯・フォルダ削除など）ことで常駐を止めない。"""
    line = f"{datetime.datetime.now():%F %T} {msg}\n"
    try:
        with open(LOG, "a") as f:
            f.write(line)
    except OSError:
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(LOG, "a") as f:
                f.write(line)
        except OSError:
            pass


ENV_WARNINGS = []   # 起動前に見つけた設定の問題。main() の最初にまとめてログへ出す


def env_number(name, default, cast):
    """環境変数を数値として読む。壊れた値（例: int に "3.5"）は既定へ戻し、import 時に落ちない。"""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return cast(raw)
    except ValueError:
        ENV_WARNINGS.append(f"{name}={raw!r} is not a number -> using default {default}")
        return default


HERDR = (os.environ.get("RECESS_HERDR_BIN")
         or shutil.which("herdr")
         or os.path.join(HOME, ".local/bin/herdr"))
POLL = env_number("RECESS_POLL_SECONDS", 2.0, float)
HANDS_OFF = env_number("RECESS_HANDS_OFF_SECONDS", 3, int)
RETURN_COOLDOWN = env_number("RECESS_RETURN_COOLDOWN_SECONDS", 0, int)  # 呼び戻し後、次にブラウザへ行くまでの最短秒数（既定0。必要なら環境変数で）
TERMINAL_APPS = set(os.environ.get(
    "RECESS_TERMINAL_APPS", "iTerm2 Terminal Ghostty kitty Alacritty WezTerm cmux").split())
REMOTE_STALE = 30          # 秒。取得に失敗した他マシンの状態を、この間は前回の値で持ちこたえる
DRY_RUN = os.environ.get("RECESS_DRY_RUN") == "1"
SSH_CTL = os.path.join(HOME, ".ssh", "ctl-recess-%C")

try:
    os.makedirs(STATE_DIR, exist_ok=True)
except OSError as _e:
    ENV_WARNINGS.append(f"cannot create {STATE_DIR}: {_e!r}")


def run(cmd, timeout=8, input_=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input_)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # timeout など
        return -1, "", str(e)


# ---------- 状態の収集 ----------

def parse_agents(raw):
    try:
        return json.loads(raw)["result"]["agents"]
    except Exception:
        return None


def local_agents():
    rc, out, _ = run([HERDR, "agent", "list"], timeout=5)
    return parse_agents(out) if rc == 0 else None


def machines():
    """herdr machine list の enabled な行 → [(label, target)]。接続先はここからだけ読む（決め打ちしない）。"""
    rc, out, _ = run([HERDR, "machine", "list"], timeout=5)
    result = []
    if rc != 0:
        return result
    for line in out.splitlines():
        cols = line.split("\t")
        if len(cols) >= 5 and cols[4].strip() == "enabled":
            result.append((cols[1].strip(), cols[2].strip()))
    return result


SELECTION_FILE = os.path.join(HOME, ".local", "state", "herdr", "client", "endpoint-selection.json")
_profile_labels = {}


def selected_endpoint():
    """herdr の画面がいま選んでいる台（"local" か machine のラベル）。読めなければ None。

    herdr のクライアントは、台を選ぶたびに selected_profile（machine の ID。Mac なら null）を
    このファイルへ書く。フォーカスの動きから推すと、Mac のフォーカスが動かないまま台を戻ったとき
    に拾えない（2026-10-22。EMG から Mac のペインへ戻っても active=EMG のままで、見ている
    ペインに to be read が付いた）。公開 API ではないので、読めないときは従来の推定へ戻る。
    """
    try:
        with open(SELECTION_FILE, encoding="utf-8") as f:
            profile = json.load(f).get("selected_profile")
    except (OSError, ValueError, AttributeError):
        return None
    if not profile:
        return "local"
    if profile not in _profile_labels:
        rc, out, _ = run([HERDR, "machine", "list"], timeout=5)
        if rc == 0:
            for line in out.splitlines():
                cols = line.split("\t")
                if len(cols) >= 2:
                    _profile_labels[cols[0].strip()] = cols[1].strip()
    return _profile_labels.get(profile)


REMOTE_HERDR = os.environ.get("RECESS_REMOTE_HERDR", "$HOME/.local/bin/herdr")


def remote_herdr_cmd(argv_str):
    """他マシンで herdr を呼ぶコマンド文字列。PATH にあればそれを、無ければ絶対パスを使う。

    非対話シェルの PATH に ~/.local/bin が無い相手では、名前だけで呼ぶと command not found に
    なり、黙って unreachable 扱いになっていた（2026-10-14 に4台で実測。ssh 自体は通っていた）。
    """
    return f'command -v herdr >/dev/null 2>&1 && herdr {argv_str} || {REMOTE_HERDR} {argv_str}'


def ssh_herdr(target, remote_cmd):
    """他マシンの herdr を叩く。状態収集と表示の差し替えで同じ経路（多重化した ssh）を使う。"""
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ControlMaster=auto", "-o", f"ControlPath={SSH_CTL}",
           "-o", "ControlPersist=600", "-o", "ConnectTimeout=5", "-o", "ServerAliveInterval=15",
           "-o", "LogLevel=ERROR", target, remote_cmd]
    return run(cmd, timeout=10)


def remote_agents(target):
    rc, out, _ = ssh_herdr(target, remote_herdr_cmd("agent list"))
    return parse_agents(out) if rc == 0 else None


# ---------- Mac 側の観測・操作 ----------

def hid_idle():
    rc, out, _ = run(["ioreg", "-c", "IOHIDSystem"], timeout=5)
    m = re.search(r'"HIDIdleTime" = (\d+)', out)
    return int(m.group(1)) // 1_000_000_000 if m else 0


def front_app():
    """最前面アプリ名。lsappinfo だけを使う（python3 に System Events の許可を求めない）。"""
    rc, asn, _ = run(["lsappinfo", "front"], timeout=5)
    asn = asn.strip()
    if not asn:
        return "unknown"
    _, lst, _ = run(["lsappinfo", "list"], timeout=5)
    for line in lst.splitlines():
        if asn in line:
            m = re.match(r'\s*\d+\) "([^"]*)"', line)
            return m.group(1) if m else "unknown"
    return "unknown"


def ssh_login_present():
    _, out, _ = run(["who"], timeout=5)
    return "(" in out


def wake(reason):
    log(f"WAKE  {reason}")
    if not DRY_RUN:
        try:
            subprocess.Popen(["caffeinate", "-u", "-t", "2"])
        except OSError as e:   # macOS には必ずあるが、無くても常駐は止めない
            log(f"WAKE  caffeinate failed: {e!r}")


VIDEO_APP_FIXED = os.environ.get("RECESS_VIDEO_APP", "")     # 決め打ちしたいときだけ指定（例 Safari / Comet）
BROWSER_APPS = {name.strip() for name in os.environ.get(
    "RECESS_BROWSER_APPS", "Safari,Comet,Google Chrome,Firefox,Arc,Brave Browser,Microsoft Edge").split(",")
    if name.strip()}
LAST_OTHER_APP = {"name": "Safari"}                        # 最後に見ていたブラウザ（既定 Safari）


def video_app():
    return VIDEO_APP_FIXED or LAST_OTHER_APP["name"]


def token_for(label):
    """印の文言に対応するトークン名。設定に置かれていなければ READING_TOKEN へ落とす。"""
    wanted = {READING_LABEL: READING_NOW_TOKEN, READ_LABEL: READ_TOKEN,
              WORKING_LABEL: WORKING_TOKEN}.get(label)
    if not wanted:
        return READING_TOKEN              # to be read は従来どおり $recess
    try:
        return wanted if f"${wanted}" in _herdr_config_text() else READING_TOKEN
    except OSError:
        return READING_TOKEN


SPACE_APP = os.path.join(HOME, "Applications", "Recess.app")
LAST_TERMINAL = {"name": os.environ.get("RECESS_DEFAULT_TERMINAL", "iTerm")}   # open -a に渡す名前。プロセス名 iTerm2 → アプリ名 iTerm
TERMINAL_OPEN_NAMES = {"iTerm2": "iTerm"}


STATUS_FILE = os.path.join(STATE_DIR, "status.json")   # recess status が読む現在地。判定はここでは行わず、tick が決めた値をそのまま並べる

IGNORE_FILE = os.path.join(STATE_DIR, "ignore")   # 1行に1つ、ペイン名の一部を書く。合うペインは無いものとして扱う（定期実行のループなど）


def ignored_titles():
    """IGNORE_FILE の各行（空行と # で始まる行を除く）。毎回読み直すので、書き換えれば再起動なしで効く。"""
    try:
        with open(IGNORE_FILE) as f:
            return [s.strip() for s in f if s.strip() and not s.strip().startswith("#")]
    except OSError:
        return []


def is_ignored(agent, patterns):
    title = agent.get("terminal_title_stripped") or agent.get("terminal_title") or ""
    return any(p in title for p in patterns)


ANNOUNCE_OFF = os.path.join(STATE_DIR, "announce-off")   # このファイルを作ると「Moving to ◯◯」の通知を止める
ANNOUNCE_SECONDS = float(os.environ.get("RECESS_ANNOUNCE_SECONDS", "5"))   # 「Moving to ◯◯」を読む時間。0 で即移る

READING_LABEL = os.environ.get("RECESS_READING_LABEL", "reading")   # 読み中の印。空で出さない
READ_LABEL = os.environ.get("RECESS_READ_LABEL", "read")            # 読み終わったペインの印。空で出さない
TO_BE_READ_LABEL = os.environ.get("RECESS_TO_BE_READ_LABEL", "to be read")   # done（未読）の印。空で出さない
READING_TOKEN = os.environ.get("RECESS_READING_TOKEN", "recess")       # サイドバーの行に $<この名前> で置く
# 印は意味ごとに色を変えたいが、1つのトークンに入れると全部同じ色になる。意味ごとに
# トークンを分け、設定に無いものは READING_TOKEN へ落とす（既存の設定のままでも印は消えない）。
#   to be read … 次に読む候補。目立つべき（赤・太字）
#   reading    … いま見ている場所。自分で分かっているので目立たなくてよい（通常色）
#   read       … 用は済んだ。探せば読める程度でよい（補助色）
READING_NOW_TOKEN = os.environ.get("RECESS_READING_NOW_TOKEN", "recess_now")
READ_TOKEN = os.environ.get("RECESS_READ_TOKEN", "recess_done")
# working は4つ目の印（2026-10-22 ユーザー指定「作業中は黄色で working に」）。他の3つと違い、
# 設定にトークンが無ければ出さない。$recess へ落とすと作業中の行まで赤くなり、赤の意味が壊れる。
WORKING_LABEL = os.environ.get("RECESS_WORKING_LABEL", "working")
WORKING_TOKEN = os.environ.get("RECESS_WORKING_TOKEN", "recess_working")
ALL_TOKENS = {READING_TOKEN, READING_NOW_TOKEN, READ_TOKEN, WORKING_TOKEN}
HERDR_CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config")),
                            "herdr", "config.toml")


def _herdr_config_text():
    """herdr の設定からコメント行を除いた本文。

    `#` で始まる行を落とすのは、コメントアウトした設定を「有効」と誤認しないため
    （2026-10-14。保留にした案をコメントで残したら、そのトークンを使い続けて印が消えた）。
    """
    with open(HERDR_CONFIG, encoding="utf-8") as f:
        return "\n".join(line for line in f if not line.lstrip().startswith("#"))


def reading_uses_token():
    """読み中の印を、カスタムトークンで出すか、エージェント名の差し替えで出すか。

    サイドバーの行に `$<トークン名>` を置いている人にはトークンで書く。独立した
    トークンなので、その1語だけ色を変えられる（`agent` を塗ると claude / codex まで塗られる）。
    置いていない人には display_agent でエージェント名を差し替える。既定の行構成には
    `agent` があるので、設定を触っていなくても必ず画面に出る。
    herdr に実効設定を読む API が無いので、設定ファイルの文字列を見るだけにしている
    （TOML は解析しない）。読めなければ「必ず出るほう」へ倒す。印が黙って消えるのが
    いちばん悪いため（ユーザー判断 2026-10-10「それはだめでしょ」）。
    """
    try:
        return f"${READING_TOKEN}" in _herdr_config_text()
    except OSError:
        return False
READING_TTL = max(POLL * 6, 15.0)   # 秒。貼り直しの間隔より長くし、常駐が落ちたら TTL 切れで消える


def notify(title, body):
    """どのアプリへ移るかを画面に出す。ターミナルを見ていないときに気づけるのが目的。"""
    if os.path.exists(ANNOUNCE_OFF):
        return
    run([HERDR, "notification", "show", title, "--body", body], timeout=5)


def toggle_video(why):
    """権限不要の open で前面化を確認し、専用アプリからスペースを1回送る。"""
    # Python は open / lsappinfo だけを使う。キー送信の権限は Recess.app が持つ。
    target = video_app()
    log(f"TOGGLE {why} -> target={target} (front={front_app()})")
    if why == "play" and ANNOUNCE_SECONDS > 0 and not os.path.exists(ANNOUNCE_OFF):
        # 画面が移る前に知らせる。移ってから出しても、もう読めない（ユーザー報告 2026-09-28）
        notify("Recess", f"Moving to {target} in {ANNOUNCE_SECONDS:g}s")
        log(f"TOGGLE {why} -> announced {target}, waiting {ANNOUNCE_SECONDS:g}s")
        deadline = time.monotonic() + ANNOUNCE_SECONDS
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            time.sleep(min(1.0, left))
            if hid_idle() < 1:      # 読んでいる間に手が戻ったら行かない。次に手が止まればまた知らせる
                # 予告を読んだ人が「結局どうなったか」を知れるようにする（ユーザー報告 2026-09-28）
                notify("Recess", "Moving is cancelled")
                log(f"TOGGLE {why} -> cancelled: hands back on")
                return "cancelled"
    rc, _, err = run(["open", "-a", target], timeout=5)
    if rc != 0:
        log(f"TOGGLE {why} -> skipped: cannot open {target}: {err.strip()[:80]}")
        if why == "play":
            notify("Recess", f"Could not open {target}")
        return False
    deadline = time.monotonic() + 3
    while front_app() != target:
        if time.monotonic() >= deadline:
            log(f"TOGGLE {why} -> skipped: {target} did not become frontmost")
            if why == "play":
                notify("Recess", f"Could not bring {target} to the front")
            return False
        time.sleep(0.1)
    time.sleep(0.2)
    if front_app() != target:
        log(f"TOGGLE {why} -> skipped: focus left {target}")
        if why == "play":
            notify("Recess", f"Focus left {target}")
        return False
    rc, _, err = run(["open", "-g", "-W", SPACE_APP], timeout=15)
    # open の終了コードはアプレットの終了だけを示す。動画の再生状態は検証できない。
    result = "helper exited (playback unverified)" if rc == 0 else err.strip()[:80]
    log(f"TOGGLE {why} -> {target}: {result}")
    if why == "play" and rc != 0:
        notify("Recess", f"Could not send space to {target}")
    return rc == 0


def video_play(reason):
    """ブラウザを前に出し、専用アプリからスペースを送る。中止したときは "cancelled" を返す。"""
    log(f"PLAY  {reason}")
    if DRY_RUN:
        return True
    return toggle_video("play")


def video_pause_and_return(reason):
    """動画を見ているときだけ、スペースを送ってから帰り先を前に出す。それ以外は理由を残して何もしない。"""
    app = front_app()
    if app not in BROWSER_APPS:
        # 以前は「ターミナル以外＝ブラウザ」と決めつけていたので、VS Code・Zoom・ロック画面でも
        # 画面を奪っていた（2026-10-03 のログで Code 7件・zoom.us 4件・loginwindow 81件）。
        # 動画が動いているのはブラウザだけなので、それを見ている人にだけ返す（ユーザー判断 2026-10-13）。
        log(f"RETURN {reason}: skipped: you are in {app}, not watching a video")
        return
    log(f"RETURN {reason} from {app}")
    if DRY_RUN:
        return
    toggle_video("pause")
    time.sleep(0.3)
    run(["open", "-a", LAST_TERMINAL["name"]], timeout=5)


def jump(pane_id, reason):
    log(f"JUMP  -> {pane_id} {reason}")
    if DRY_RUN:
        return
    rc, _, err = run([HERDR, "agent", "focus", pane_id], timeout=5)
    if rc != 0:   # 失敗しても JUMP と記録されていたので、結果まで残す
        log(f"JUMP  -> {pane_id} failed: {err.strip()[:120]}")


# ---------- 判定 ----------

class Watcher:
    def __init__(self):
        self.prev = {}          # key -> status
        self.prev_focus = {}    # endpoint -> key or None
        self.reading = set()    # keys（いま読んでいる）
        self.read_done = set()  # keys（読み終わって離れた。そのペインが働き出したら消す）
        self.unread = set()     # keys（見ていないうちに working/done → idle になった。開くまで to be read）
        self.active = "local"   # 最後にフォーカスが動いた端末
        self.pending_off = False
        self.last_return_at = -1e9   # 最後に呼び戻した時刻（monotonic）
        self.titles = {}        # key -> ペイン名。取れなかった端末のぶんは前回の名前を残す
        self.tab_of = {}             # key -> "endpoint/tab_id"（同じタブの2ペインは一体で判断する）
        self.fg_prev = None          # 前回 foreground だったか（None は起動直後）
        self.labeled = {}       # key -> (最後に印を貼った時刻（monotonic）, そのときの文言)
        self.targets = {}       # endpoint -> ssh の接続先（local は持たない）
        self.remote_cache = {}  # label -> (agents, time)
        self.remote_down = set()
        self.last_summary = ""

    def collect(self):
        """{endpoint: agents or None}"""
        eps = {"local": local_agents()}
        now = time.time()
        for label, target in machines():
            self.targets[label] = target
            ag = remote_agents(target)
            if ag is None:
                cached = self.remote_cache.get(label)
                if cached and now - cached[1] < REMOTE_STALE:
                    ag = cached[0]
                if label not in self.remote_down:
                    log(f"remote {label}: unreachable (using cached for {REMOTE_STALE}s)")
                    self.remote_down.add(label)
            else:
                self.remote_cache[label] = (ag, now)
                if label in self.remote_down:
                    log(f"remote {label}: back")
                    self.remote_down.discard(label)
            eps[label] = ag
        return eps

    # ---------- 読み中の表示 ----------

    def report_metadata(self, key, args):
        """display-only なペイン情報を書く。他マシンぶんは状態収集と同じ ssh で流す。"""
        ep, pane_id = key.split("/", 1)
        argv = ["pane", "report-metadata", pane_id] + args   # pane_id が先。= 形式のオプションは通らない
        if ep == "local":
            return run([HERDR] + argv, timeout=5)
        target = self.targets.get(ep)
        if not target:
            return -1, "", f"no ssh target for {ep}"
        return ssh_herdr(target, remote_herdr_cmd(" ".join(shlex.quote(a) for a in argv)))

    def sync_reading_labels(self, focused_key, statuses):
        """読み中のペインに `reading`、読み終わったペインに `read` の印を出す。
        idle と reading は herdr から見ると同じなので、ここだけが画面上の見分け方になる。
        state_label ではないのは、行構成に state_text が無いと出ないため（2026-09-29 実測）。
        display_agent でもないのは、それが `agent` トークンの値を上書きする仕組みで、
        色を付けると claude / codex まで同じ色になるため。カスタムトークンなら
        その1語だけ色を変えられる（ユーザー判断 2026-10-10「赤字にして」）。
        reading と read は同じトークンに入るので色は同じ赤になる（2026-10-14）。"""
        if not (READING_LABEL or READ_LABEL or TO_BE_READ_LABEL or WORKING_LABEL):
            return
        use_token = reading_uses_token()
        try:   # working はトークンで出せるときだけ（display_agent で出すと claude / codex が消える）
            show_working = bool(WORKING_LABEL) and use_token and f"${WORKING_TOKEN}" in _herdr_config_text()
        except OSError:
            show_working = False
        if use_token != getattr(self, "_label_via_token", None):
            log(f"LABEL via {'$' + READING_TOKEN if use_token else 'display_agent'}")
            self._label_via_token = use_token
        # 印は3つだけ（ユーザー判断 2026-10-14「read, reading, to be read だけ表示されていれば ok」）。
        #   done            -> to be read（まだ読んでいない）
        #   idle かつ見ている -> reading（いま読んでいる。人は1人なので常に1つ）
        #   idle かつ未読    -> to be read（見ていないうちに終わった。2026-10-22 追加）
        #   idle かつ見ていない -> read（もう読み終わっている）
        #   blocked         -> to be read（質問待ちも「読んで答える」ので未読と同じ）
        #   working         -> working（黄。設定に $recess_working があるとき・2026-10-22 追加）
        #                      無ければ従来どおり、読んだ記録があるあいだは read を残す
        wanted = {}
        for key, status in statuses.items():
            if key.split("/", 1)[0] in self.remote_down:
                continue       # 応答しない端末へ ssh を投げ続けない
            if status in ("done", "blocked"):
                label = TO_BE_READ_LABEL   # blocked も「人が読んで答える」ので未読と同じ扱い
            elif status == "working":
                if show_working:
                    label = WORKING_LABEL
                else:
                    label = READ_LABEL if key in self.read_done else None
            elif key == focused_key:
                label = READING_LABEL
            elif key in self.unread:
                label = TO_BE_READ_LABEL   # 見ていないうちに idle になった＝まだ読んでいない
            else:
                label = READ_LABEL
            if label:
                wanted[key] = label
        # 消すほうを先にやる。付けてから消すと、その1秒だけ2つ出る（2026-09-30 にログで9回確認）
        for key in [k for k in self.labeled if k not in wanted]:
            self.labeled.pop(key, None)
            if DRY_RUN:
                continue
            # 両方消す。設定を書き換えて方式が変わった直後でも、前の印が残らない
            clears = []
            for tok in ALL_TOKENS:
                clears += ["--clear-token", tok]
            rc, _, err = self.report_metadata(key, ["--source", "recess"] + clears
                                              + ["--clear-display-agent"])
            # 消せなくても TTL で消えるので、記録だけ残して先へ進む
            log(f"LABEL {key} cleared" if rc == 0 else f"LABEL {key} clear failed: {err.strip()[:120]}")
        at = time.monotonic()
        for key, label in sorted(wanted.items()):
            prev_at, prev_label = self.labeled.get(key, (-1e9, None))
            if label == prev_label and at - prev_at < READING_TTL / 3:
                continue   # 同じ文言でまだ有効。貼り直しは TTL の 1/3 ごと
            if DRY_RUN:
                self.labeled[key] = (at, label)
                continue
            if use_token:
                tok = token_for(label)
                mark = ["--token", f"{tok}={label}", "--clear-display-agent"]
                for other in ALL_TOKENS - {tok}:
                    mark += ["--clear-token", other]   # 意味が変わったとき前の色が残らない
            else:
                mark = ["--display-agent", label]
                for tok in ALL_TOKENS:
                    mark += ["--clear-token", tok]
            rc, _, err = self.report_metadata(key, ["--source", "recess"] + mark + [
                "--ttl-ms", str(int(READING_TTL * 1000))])
            if rc == 0:
                if label != prev_label:   # 文言が変わったときだけ記録する（貼り直しは書かない）
                    log(f"LABEL {key} -> {label!r}")
                self.labeled[key] = (at, label)
            else:
                log(f"LABEL {key} failed: {err.strip()[:120]}")

    def write_status(self, now, attention, view, afp, app, ignored_panes):
        """recess status が読む現在地を書く。ここでは判定しない。

        tick が決めた値をそのまま並べる。status 側に判定を書くと、常駐の本当の判断と
        ずれて嘘をつくため（ユーザー判断 2026-10-06）。
        ペイン単位で連れ出しを妨げるのは blocked/done と読み中の2つだけ。読み中は
        2026-10-14 から全マシンを見る（見ているタブに限らない）。
        """
        view_set = set(view)
        panes = []
        for key in sorted(now):
            status = now[key]
            reading = key in self.reading
            if status in ("blocked", "done"):
                blocking = "呼び出しが残っている"
            elif reading:
                blocking = "読み中"   # 2026-10-14 から端末をまたいで効く
            else:
                blocking = None            # working は待つ相手として必要。idle も妨げない
            panes.append({"key": key, "title": self.titles.get(key, ""), "status": status,
                          "tab": self.tab_of.get(key), "reading": reading,
                          "in_view": key in view_set, "ignored": False, "blocking": blocking})
        for p in ignored_panes:
            panes.append({"key": p["key"], "title": p["title"], "status": p["status"],
                          "tab": p.get("tab"), "reading": False, "in_view": False,
                          "ignored": True, "blocking": None})

        idle = hid_idle()
        cooldown_left = max(RETURN_COOLDOWN - (time.monotonic() - self.last_return_at), 0)
        any_working = any(v == "working" for v in now.values())
        blocking = [p["key"] for p in panes if p["blocking"]]
        snapshot = {
            "written_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "ON" if self.enabled else "OFF",
            "front_app": app,
            "front_is_terminal": app in TERMINAL_APPS,
            "hands_off_seconds": idle,
            "hands_off_needed": HANDS_OFF,
            "any_working": any_working,
            "focused_pane": afp,
            "pending_off": bool(self.pending_off),
            "return_cooldown_left": round(cooldown_left, 1),
            "video_app": video_app(),
            "blocking": blocking,
            "panes": panes,
        }
        snapshot["can_play"] = bool(
            self.enabled and snapshot["pending_off"] and not attention and afp is not None
            and any_working and not blocking and cooldown_left <= 0
            and idle >= HANDS_OFF and snapshot["front_is_terminal"])
        tmp = STATUS_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False)
            os.replace(tmp, STATUS_FILE)
        except OSError as e:
            log(f"status: 書けませんでした: {e!r}")

    def tick(self):
        enabled = not os.path.exists(OFF_FILE)
        if enabled != getattr(self, "_enabled_logged", None):
            log(f"MODE  {'ON' if enabled else 'OFF'}")
            self._enabled_logged = enabled
        self.enabled = enabled
        eps = self.collect()
        ignore = ignored_titles()
        now, focus, fstat = {}, {}, {}
        ignored_panes = []      # 無視リストに合ったペイン。now には入れないが status には出す
        for ep, agents in eps.items():
            if agents is None:
                # 取れなかった端末は前回の値を引き継ぐ（消えたと誤解しない）
                for k, v in self.prev.items():
                    if k.startswith(ep + "/"):
                        now[k] = v
                focus[ep] = self.prev_focus.get(ep)
                fstat[ep] = now.get(focus[ep]) if focus[ep] else None
                continue
            focus[ep] = None
            for a in agents:
                key = f"{ep}/{a['pane_id']}"
                title = a.get("terminal_title_stripped") or a.get("terminal_title") or ""
                if is_ignored(a, ignore):
                    ignored_panes.append({"key": key, "title": title,
                                          "tab": f"{ep}/{a.get('tab_id') or a['pane_id']}",
                                          "status": a.get("agent_status", "?")})
                    continue
                self.titles[key] = title
                now[key] = a.get("agent_status", "?")
                self.tab_of[key] = f"{ep}/{(a.get('tab_id') or a['pane_id'])}"
                if a.get("focused"):
                    focus[ep] = key
            fstat[ep] = now.get(focus[ep]) if focus[ep] else None

        # 見ている端末: 最後にフォーカスが動いた側
        for ep in focus:
            if ep in self.prev_focus and focus[ep] != self.prev_focus[ep]:
                self.active = ep
        sel = selected_endpoint()   # 分かるならこちらが正本（フォーカスの動きは推定にすぎない）
        if sel in focus:
            self.active = sel
        if self.active not in focus:
            self.active = "local"

        # 「見ているペイン群」: 各端末で、フォーカス中のペインと同じタブにあるペイン全部
        def in_view(ep):
            fp = focus.get(ep)
            if not fp:
                return []
            tab = self.tab_of.get(fp)
            return [k for k in now if k.startswith(ep + "/") and self.tab_of.get(k) == tab] or [fp]

        # reading の開始（どの端末でも、見ていたタブのペインが done/working → idle）
        for ep in focus:
            for k in in_view(ep):
                if now.get(k) == "idle" and self.prev.get(k) in ("done", "working"):
                    self.reading.add(k)
        # reading の終了: 各端末で、その端末のフォーカスが reading でないペインへ移った / reading ペインが idle でなくなった
        # 端末ごとに独立して消す。active 端末だけを特別扱いしていたので、判定を全マシンへ広げると
        # 見ていない端末の reading が残り続けてしまう（2026-10-14）。
        # 未読: 見ていないうちに終わったペイン（2026-10-22 ユーザー指摘「done が自動的に read になってない？」）。
        # herdr はそのサーバーで focused なペインが終わると done を飛ばして idle にする。衛星は
        # たいてい1枚きりのペインを focused と思っているので、終わるたびに idle になり（SP は53回中52回）、
        # 下の判定では「idle で見ていない」= read になっていた。人が実際に見ているのは active な端末の
        # タブだけなので、それ以外で idle になったものは、開くまで to be read にする。
        looking = set(in_view(self.active))
        for k, s in now.items():
            if s == "idle" and self.prev.get(k) in ("done", "working") and k not in looking:
                self.unread.add(k)
        self.unread -= {k for k in looking if now.get(k) == "idle"}   # 開いたら未読ではない
        self.unread &= set(now)
        afp = focus.get(self.active)
        self.read_done -= self.reading          # 読み直し始めたものは read ではない
        gone = set()
        for ep, fp in focus.items():
            if fp and fp not in self.reading:   # その端末で別のペインへ移った
                gone |= {k for k in self.reading if k.startswith(ep + "/")}
        gone |= {k for k in self.reading if now.get(k) != "idle"}   # そのペインが動き出した
        self.reading -= gone
        # 一度読んだ印は working のあいだも残す（ユーザー判断 2026-10-14。AIが動くペインは
        # 「読み終わる」と「次の仕事が始まる」がほぼ同時で、working で消すと read が見えない）。
        # done / blocked は「新しい未読ができた」ので read にしない／残さない。
        NEW_ERRAND = ("done", "blocked")
        self.read_done |= {k for k in gone if now.get(k) not in NEW_ERRAND}
        self.read_done = {k for k in self.read_done if now.get(k) not in NEW_ERRAND}
        self.read_done -= self.unread           # 読んでいないものは read ではない
        self.sync_reading_labels(focus.get(self.active), now)

        changed = (now != self.prev) or (focus != self.prev_focus)
        attention = [k for k, s in now.items() if s in ("blocked", "done")]
        new_attention = [k for k in attention if self.prev.get(k) not in ("blocked", "done")]
        if not self.prev_focus:
            # 起動直後: 既にある blocked/done を「新しく現れた」と誤解して呼び戻さない（再生の判定は行う）
            new_attention = []

        summary = (" ".join(f"{k}={v}" for k, v in sorted(now.items())) +
                   f" | active={self.active} focus={afp}:{fstat.get(self.active)} tab={[k.split('/', 1)[1] for k in in_view(self.active)]}" +
                   f" reading={sorted(self.reading) or '-'}")
        if summary != self.last_summary:
            log(f"state: {summary}")
            self.last_summary = summary

        # 見ていたペインが目の前で終わると herdr は done を飛ばして idle にする。
        # 動画を再生中ならそれも「呼ばれた」扱いにして戻る。
        view_keys = {k for ep in focus for k in in_view(ep)}
        finished_in_view = [k for k in now if now[k] == "idle" and self.prev.get(k) == "working"
                            and k in view_keys]
        if (new_attention or finished_in_view) and not self.enabled:
            log(f"OFF: would return ({new_attention or finished_in_view}) -> skipped")
            self.pending_off = False
        elif new_attention or finished_in_view:
            why = f"new attention: {new_attention}" if new_attention else f"finished in view: {finished_in_view}"
            # 手を離していたかは「呼び戻す前」に測る。呼び戻しで自分がスペースを押すと
            # HID の idle が 0 に戻り、動画を見ていた人まで「手が乗っている」と誤判定するため
            # （2026-09-29 に判明。ブラウザから呼び戻した直後の誤判定が79回ログに残っていた）。
            idle_before = hid_idle()
            wake(why)
            self.pending_off = False
            video_pause_and_return(why)
            self.last_return_at = time.monotonic()
            for k in new_attention:
                if k.startswith("local/") and now[k] in ("done", "blocked"):
                    if ssh_login_present():
                        log("no jump: ssh login present")
                    elif idle_before >= HANDS_OFF:
                        jump(k.split("/", 1)[1], f"(hands-off {idle_before:.0f}s)")
                    else:
                        log(f"no jump: hands on ({idle_before:.0f}s)")

        # ブラウザへ行ってよいか
        fs = fstat.get(self.active)
        # ブラウザへ行くのは「見ているタブのAIが働いていて、待っている」ときだけ。
        # idle（読み中でなくても）は「次を打つ準備」なので行かない
        # （呼び戻された直後に2〜3回ブラウザへ戻されるのは、idle で行く分岐が原因だった）。
        # 同じタブに読み中のペインがあるなら、隣のペインが working でも行かない。
        view = in_view(self.active)   # recess status の「いま見ているタブ」表示に使う（write_status へ渡す）
        # 読み中はどの端末のものでも効かせる。見ているタブだけに絞っていたので、active の選び間違いで
        # 連れ出されていた（2026-10-14 に Mac で読んでいる最中に4回。ユーザー判断で非対称を廃止）。
        any_reading = sorted(self.reading)
        app = front_app()
        if app in TERMINAL_APPS:
            LAST_TERMINAL["name"] = TERMINAL_OPEN_NAMES.get(app, app)
        elif app in BROWSER_APPS:            # ブラウザだけ覚える（システム設定などを戻り先にしない）
            LAST_OTHER_APP["name"] = app

        # foreground = 人の手が要る（blocked / done がどこかにある、または見ているタブに reading がある）
        # background = idle と working だけ。ブラウザへ行くのは foreground → background へ移った瞬間だけ
        # （2026-09-26 変更。background の中で状態が変わっても、それだけでは行かない）
        fg_now = bool(attention) or bool(any_reading)
        if self.fg_prev is None:
            self.fg_prev = fg_now            # 起動直後は遷移とみなさない
        if self.fg_prev and not fg_now:
            # 用事が終わった瞬間にターミナルを見ていた人だけ、動画へ行く。他のウィンドウで
            # 作業している人は休憩中ではないので、その回は見送る。印を残すと、ターミナルへ
            # 戻った瞬間に連れ出されてしまう（ユーザー判断 2026-10-03）。
            if app in TERMINAL_APPS:
                self.pending_off = True
                log(f"FG->BG: attention gone, reading gone -> browser next (working anywhere: {any(v == 'working' for v in now.values())})")
            else:
                log(f"FG->BG: skipped: you are in {app}, not at the terminal")
        elif fg_now:
            self.pending_off = False
        self.fg_prev = fg_now
        # 実際に行けるのは、どこかに working があるときだけ（見ているタブに限らない。ユーザー判断 2026-09-26）。
        # 全部 idle なら待つ相手がいないので行かない。無ければ印を残したまま待つ
        any_working = any(v == "working" for v in now.values())
        want_off = (not attention) and afp is not None and any_working and not any_reading

        if self.pending_off and want_off and self.enabled:
            idle = hid_idle()
            since_return = time.monotonic() - self.last_return_at
            if since_return < RETURN_COOLDOWN:
                pass                        # 呼び戻した直後は、AIが続けて聞いてくるかを見る猶予
            elif idle >= HANDS_OFF:
                if app in TERMINAL_APPS:
                    if video_play(f"{self.active} {afp}:{fs} hands-off={idle}s front={app}") != "cancelled":
                        self.pending_off = False
                else:
                    if getattr(self, "_front_logged", None) != app:
                        log(f"front app is {app} -> keep waiting")
                        self._front_logged = app

        self.write_status(now, attention, view, afp, app, ignored_panes)
        self.prev, self.prev_focus = now, focus


def main():
    log(f"start pid={os.getpid()} herdr={HERDR} poll={POLL}s hands_off={HANDS_OFF}s dry_run={DRY_RUN}")
    for w_msg in ENV_WARNINGS:
        log(f"config: {w_msg}")
    w = Watcher()
    while True:
        t0 = time.time()
        try:
            w.tick()
        except Exception as e:
            log(f"tick error: {e!r}")
        time.sleep(max(0.2, POLL - (time.time() - t0)))


if __name__ == "__main__":
    main()
