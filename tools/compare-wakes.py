#!/usr/bin/env python3
"""afplay ラッパーが本当に要るかを、既存のログだけで判定する道具。

問いは1つ：「ラッパーだけが拾った、他マシンの blocked/done があるか」。
0件なら、常駐のポーリングだけで足りている＝ラッパーを消してよい。

数えるのは recess が ON だった時間だけ。OFF の間は常駐が点灯を見送る
（watch.log の「OFF: would return ... -> skipped」）ので、OFF を混ぜると
「常駐が点けず、ラッパーだけが点けた」に見える件が量産される。
逆に、OFF を外した結果 ON の母数が空になったときは 0 件と言わず、判定を保留する。

使い方:
  python3 tools/compare-wakes.py                         # 既定（公開版の置き場）
  python3 tools/compare-wakes.py --state-dir <dir> --sound-log <file> --days 1
"""
import argparse
import datetime
import io
import os
import re

TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ")
STATE = re.compile(r"^state: (.*?) \|")
MIN_SAMPLES = 20   # ON の点灯がこれ未満なら、0 件でも断定しない


def ts(line):
    m = TS.match(line)
    return datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") if m else None


def read(path):
    if not os.path.exists(path):
        return []
    out = []
    for line in io.open(path, encoding="utf-8", errors="replace"):
        t = ts(line)
        if t:
            out.append((t, line[20:].rstrip()))
    return out


def mode_spans(watch):
    """watch.log の MODE 行 → [(開始, 終了, ONか)]。MODE 行が無いログは全部 ON 扱い（昔の常駐）。"""
    spans, cur, start = [], True, watch[0][0]
    for t, m in watch:
        if m.startswith("MODE "):
            on = m.split()[1] == "ON"
            if on != cur:
                spans.append((start, t, cur))
                cur, start = on, t
    spans.append((start, watch[-1][0], cur))
    return spans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-dir", default=os.path.expanduser("~/.local/state/recess"))
    ap.add_argument("--sound-log", default=None, help="ラッパーの記録（既定 <state-dir>/sound.log）")
    ap.add_argument("--days", type=int, default=1, help="今から何日ぶんを見るか")
    ap.add_argument("--window", type=int, default=5, help="同じ出来事とみなす秒数")
    a = ap.parse_args()

    watch_log = os.path.join(a.state_dir, "watch.log")
    sound_log = a.sound_log or os.path.join(a.state_dir, "sound.log")
    since = datetime.datetime.now() - datetime.timedelta(days=a.days)

    # ON/OFF の区間と出来事は「ログ全体」から組む。--days で切った窓の中だけを見ると、
    # 窓より前にあった MODE OFF を読み落として OFF の時間を ON と誤解する
    # （2026-10-04: 10/01 の OFF が --days 2 の窓外にあり、★が14件の偽陽性になった）。
    watch_all = read(watch_log)
    watch = [(t, m) for t, m in watch_all if t >= since]
    sounds = [(t, m) for t, m in read(sound_log) if t >= since and "WAKE" in m]
    if not watch:
        print(f"watch.log に {a.days} 日ぶんの記録がありません: {watch_log}")
        print("常駐が止まっていたか、置き場が違います（--state-dir で指定できます）。")
        return
    if not sounds:
        print(f"ラッパーの記録がありません（入れていない？）: {sound_log}")
        return

    spans = mode_spans(watch_all)

    def mode_at(t):
        for begin, end, on in spans:
            if begin <= t <= end:
                return on
        return None   # 常駐が記録していない時間

    wakes = [t for t, m in watch_all if re.match(r"WAKE\b", m)]
    announced = [t for t, m in watch_all if "announced" in m]

    # 他マシンのペインが blocked / done へ移った時刻を集める
    remote_attention = []
    prev = {}
    for t, m in watch_all:
        sm = STATE.match(m)
        if not sm:
            continue
        now = {}
        for pair in sm.group(1).split():
            if "=" in pair:
                k, v = pair.rsplit("=", 1)
                now[k] = v
        for k, v in now.items():
            if v in ("blocked", "done") and prev.get(k) not in ("blocked", "done") and not k.startswith("local/"):
                remote_attention.append((t, k, v))
        prev = now

    near = lambda t, times: any(abs((t - x).total_seconds()) <= a.window for x in times)
    own, covered, miss, nothing = 0, 0, [], 0
    while_off, outside = 0, 0
    for t, m in sounds:
        state = mode_at(t)
        if state is None:
            outside += 1                  # 常駐のログが無い時間
            continue
        if not state:
            while_off += 1                # recess が OFF の時間
            continue
        if near(t, announced):
            own += 1                      # recess 自身の通知音
        elif near(t, wakes):
            covered += 1                  # 常駐も点けていた
        else:
            hit = [(x, k, v) for x, k, v in remote_attention if abs((t - x).total_seconds()) <= a.window]
            if hit:
                miss.append((t, hit[0]))  # 他マシンの呼び出しを、ラッパーだけが拾った
            else:
                nothing += 1              # 拾うべき出来事が無い音

    def overlap(begin, end):
        lo, hi = max(begin, watch[0][0]), min(end, watch[-1][0])
        return max((hi - lo).total_seconds(), 0)

    on_hours = sum(overlap(s, b) for s, b, on in spans if on) / 3600
    all_hours = (watch[-1][0] - watch[0][0]).total_seconds() / 3600
    judged = own + covered + nothing + len(miss)

    print(f"対象: 直近 {a.days} 日 / 同一視の窓 {a.window} 秒")
    print(f"ログの範囲: {watch[0][0]:%F %T} 〜 {watch[-1][0]:%F %T}")
    print(f"recess が ON だった時間: {on_hours:.1f}h / {all_hours:.1f}h")
    print()
    print(f"  ラッパーが点けた回数            : {len(sounds)}")
    print(f"    ├ recess が OFF の時間（除外） : {while_off}")
    print(f"    ├ 常駐のログが無い時間（除外） : {outside}")
    print(f"    └ ON の時間（判定の母数）      : {judged}")
    print(f"        ├ recess 自身の通知音      : {own}")
    print(f"        ├ 常駐も点けていた         : {covered}")
    print(f"        ├ 拾う出来事が無かった     : {nothing}")
    print(f"        └ ラッパーだけが拾った ★   : {len(miss)}")
    print()
    if miss:
        print("★ の内訳:")
        for t, (x, k, v) in miss[:20]:
            print(f"  {t:%F %T}  {k} -> {v}")
        print()
        print(f"判定: ★が {len(miss)} 件。常駐が拾えていない呼び出しがあるので、まだ消さないでください。")
        return
    if judged == 0:
        print("判定: できません。ON の時間にラッパーが鳴った記録が1件もありません。")
        if while_off:
            print(f"      この期間の点灯 {while_off} 回はすべて recess が OFF の時間でした。")
            print("      `recess on` に戻し、1日ぶん溜めてからもう一度流してください。")
        return
    if judged < MIN_SAMPLES:
        print(f"判定: 保留。★は0件ですが、ON の時間の点灯が {judged} 回しかありません"
              f"（{MIN_SAMPLES} 回を目安にしています）。もう少し溜めてから決めてください。")
        return
    print("判定: ラッパーだけが拾った他マシンの呼び出しは 0 件。常駐のポーリングで足りています。")


if __name__ == "__main__":
    main()
