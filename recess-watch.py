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
             読み中のあいだは、サイドバーのエージェント名（claude など）を「You are reading...」
             に差し替える（herdr pane report-metadata の display-only な display_agent。TTL 付き
             なので常駐が落ちたら自然に消える）。idle と reading は herdr から見ると同じ idle で、
             画面では見分けられないため（ユーザー報告 2026-09-28）。
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
  RECESS_POLL_SECONDS            状態を集める間隔（既定 2）
  RECESS_HANDS_OFF_SECONDS       「手を離した」とみなす秒数（既定 3）
  RECESS_RETURN_COOLDOWN_SECONDS 呼び戻し後にブラウザへ行かない秒数（既定 0。行き来が気になるときだけ 5 など）
  RECESS_TERMINAL_APPS           ターミナルとみなすプロセス名。空白区切り
                                （既定 "iTerm2 Terminal Ghostty kitty Alacritty WezTerm cmux"）
  RECESS_BROWSER_APPS            ブラウザとみなすアプリ名。名前に空白を含むのでカンマ区切り
                                （既定 "Safari,Comet,Google Chrome,Firefox,Arc,Brave Browser,Microsoft Edge"）
  RECESS_VIDEO_APP               動画を見るアプリを決め打ちしたいときだけ（例 Safari）
  RECESS_DEFAULT_TERMINAL        まだターミナルを見ていないうちに呼ばれたとき open -a に渡す名前（既定 iTerm）
  RECESS_READING_LABEL           読み中のペインに出す文言（既定 "You are reading..."。空にすると出さない）
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


def ssh_herdr(target, remote_cmd):
    """他マシンの herdr を叩く。状態収集と表示の差し替えで同じ経路（多重化した ssh）を使う。"""
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ControlMaster=auto", "-o", f"ControlPath={SSH_CTL}",
           "-o", "ControlPersist=600", "-o", "ConnectTimeout=5", "-o", "ServerAliveInterval=15",
           "-o", "LogLevel=ERROR", target, remote_cmd]
    return run(cmd, timeout=10)


def remote_agents(target):
    rc, out, _ = ssh_herdr(target, "herdr agent list")
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


SPACE_APP = os.path.join(HOME, "Applications", "Recess.app")
LAST_TERMINAL = {"name": os.environ.get("RECESS_DEFAULT_TERMINAL", "iTerm")}   # open -a に渡す名前。プロセス名 iTerm2 → アプリ名 iTerm
TERMINAL_OPEN_NAMES = {"iTerm2": "iTerm"}


ANNOUNCE_OFF = os.path.join(STATE_DIR, "announce-off")   # このファイルを作ると「Moving to ◯◯」の通知を止める
ANNOUNCE_SECONDS = float(os.environ.get("RECESS_ANNOUNCE_SECONDS", "5"))   # 「Moving to ◯◯」を読む時間。0 で即移る

READING_LABEL = os.environ.get("RECESS_READING_LABEL", "You are reading...")   # 読み中の状態表示。空で出さない
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
    """ブラウザを見ているときだけ、スペースを送ってからターミナルを前に出す。ターミナルを見ているなら何もしない。"""
    app = front_app()
    if app in TERMINAL_APPS:
        log(f"RETURN {reason}: already on terminal ({app}) -> no toggle")
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
        self.reading = set()    # keys
        self.active = "local"   # 最後にフォーカスが動いた端末
        self.pending_off = False
        self.last_return_at = -1e9   # 最後に呼び戻した時刻（monotonic）
        self.tab_of = {}             # key -> "endpoint/tab_id"（同じタブの2ペインは一体で判断する）
        self.fg_prev = None          # 前回 foreground だったか（None は起動直後）
        self.labeled = {}       # key -> 最後に state_label を貼った時刻（monotonic）
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
        return ssh_herdr(target, " ".join(["herdr"] + [shlex.quote(a) for a in argv]))

    def sync_reading_labels(self, focused_key):
        """読み中のペインだけ、サイドバーのエージェント名を読み中の文言へ差し替える。
        idle と reading は herdr から見ると同じなので、ここだけが画面上の見分け方になる。
        状態表示（state_label）ではなくエージェント名（display_agent）を使うのは、
        サイドバーの行構成に state_text が無いと状態の文字がどこにも出ないため（2026-09-29 実測）。"""
        if not READING_LABEL:
            return
        # 読んでいる人は1人しかいない。印を出すのは「見ている端末で、いま開いているペイン」だけ。
        # reading 集合そのものは複数持つ（同じタブの相方や他マシンぶんも判定に使う）が、
        # 画面に3つ同時に出ると、どれを読んでいるのか分からなくなる（ユーザー報告 2026-09-29）。
        wanted = {focused_key} if focused_key in self.reading else set()
        # 消すほうを先にやる。付けてから消すと、その1秒だけ2つ出る（2026-09-30 にログで9回確認）
        for key in [k for k in self.labeled if k not in wanted]:
            self.labeled.pop(key, None)
            if DRY_RUN:
                continue
            rc, _, err = self.report_metadata(key, ["--source", "recess", "--clear-display-agent"])
            # 消せなくても TTL で消えるので、記録だけ残して先へ進む
            log(f"LABEL {key} cleared" if rc == 0 else f"LABEL {key} clear failed: {err.strip()[:120]}")
        at = time.monotonic()
        for key in sorted(wanted):
            if at - self.labeled.get(key, -1e9) < READING_TTL / 3:
                continue   # まだ有効。貼り直しは TTL の 1/3 ごと
            if DRY_RUN:
                self.labeled[key] = at
                continue
            rc, _, err = self.report_metadata(key, [
                "--source", "recess", "--display-agent", READING_LABEL,
                "--ttl-ms", str(int(READING_TTL * 1000))])
            if rc == 0:
                if key not in self.labeled:
                    log(f"LABEL {key} -> {READING_LABEL!r}")
                self.labeled[key] = at
            else:
                log(f"LABEL {key} failed: {err.strip()[:120]}")

    def tick(self):
        enabled = not os.path.exists(OFF_FILE)
        if enabled != getattr(self, "_enabled_logged", None):
            log(f"MODE  {'ON' if enabled else 'OFF'}")
            self._enabled_logged = enabled
        self.enabled = enabled
        eps = self.collect()
        now, focus, fstat = {}, {}, {}
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
                now[key] = a.get("agent_status", "?")
                self.tab_of[key] = f"{ep}/{(a.get('tab_id') or a['pane_id'])}"
                if a.get("focused"):
                    focus[ep] = key
            fstat[ep] = now.get(focus[ep]) if focus[ep] else None

        # 見ている端末: 最後にフォーカスが動いた側
        for ep in focus:
            if ep in self.prev_focus and focus[ep] != self.prev_focus[ep]:
                self.active = ep
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
        # reading の終了: 見ている端末で別の idle ペインへ移った / reading ペインが idle でなくなった
        afp = focus.get(self.active)
        if afp and afp not in self.reading:   # 移った先の状態は問わない（working のペインへ移っても読み終わり）
            self.reading = {k for k in self.reading if not k.startswith(self.active + "/")}
        self.reading = {k for k in self.reading if now.get(k) == "idle"}
        self.sync_reading_labels(focus.get(self.active))

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
        view = in_view(self.active)
        view_working = [k for k in view if now.get(k) == "working"]
        view_reading = [k for k in view if k in self.reading]
        # foreground = 人の手が要る（blocked / done がどこかにある、または見ているタブに reading がある）
        # background = idle と working だけ。ブラウザへ行くのは foreground → background へ移った瞬間だけ
        # （2026-09-26 変更。background の中で状態が変わっても、それだけでは行かない）
        fg_now = bool(attention) or bool(view_reading)
        if self.fg_prev is None:
            self.fg_prev = fg_now            # 起動直後は遷移とみなさない
        if self.fg_prev and not fg_now:
            self.pending_off = True
            log(f"FG->BG: attention gone, reading gone -> browser armed (working anywhere: {any(v == 'working' for v in now.values())})")
        elif fg_now:
            self.pending_off = False
        self.fg_prev = fg_now
        # 実際に行けるのは、どこかに working があるときだけ（見ているタブに限らない。ユーザー判断 2026-09-26）。
        # 全部 idle なら待つ相手がいないので行かない。無ければ armed のまま待つ
        any_working = any(v == "working" for v in now.values())
        want_off = (not attention) and afp is not None and any_working and not view_reading

        app = front_app()
        if app in TERMINAL_APPS:
            LAST_TERMINAL["name"] = TERMINAL_OPEN_NAMES.get(app, app)
        elif app in BROWSER_APPS:            # ブラウザだけ覚える（システム設定などを戻り先にしない）
            LAST_OTHER_APP["name"] = app

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
