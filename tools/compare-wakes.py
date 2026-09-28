#!/usr/bin/env python3
"""afplay ラッパーが本当に要るかを、既存のログだけで判定する道具。

問いは1つ：「ラッパーだけが拾った、他マシンの blocked/done があるか」。
0件なら、常駐のポーリングだけで足りている＝ラッパーを消してよい。

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

    watch = [(t, m) for t, m in read(watch_log) if t >= since]
    sounds = [(t, m) for t, m in read(sound_log) if t >= since and "WAKE" in m]
    if not watch:
        print(f"watch.log に {a.days} 日ぶんの記録がありません: {watch_log}")
        return
    if not sounds:
        print(f"ラッパーの記録がありません（入れていない？）: {sound_log}")
        return

    wakes = [t for t, m in watch if re.match(r"WAKE\b", m)]
    announced = [t for t, m in watch if "announced" in m]

    # 他マシンのペインが blocked / done へ移った時刻を集める
    remote_attention = []
    prev = {}
    for t, m in watch:
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
    for t, m in sounds:
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

    print(f"対象: 直近 {a.days} 日 / 同一視の窓 {a.window} 秒")
    print(f"  ラッパーが点けた回数        : {len(sounds)}")
    print(f"    ├ recess 自身の通知音     : {own}")
    print(f"    ├ 常駐も点けていた        : {covered}")
    print(f"    ├ 拾う出来事が無かった    : {nothing}")
    print(f"    └ ラッパーだけが拾った ★  : {len(miss)}")
    print()
    if miss:
        print("★ の内訳（この件数が0なら、ラッパーを消してよい）:")
        for t, (x, k, v) in miss[:20]:
            print(f"  {t:%F %T}  {k} -> {v}")
    else:
        print("判定: ラッパーだけが拾った他マシンの呼び出しは 0 件。常駐のポーリングで足りています。")


if __name__ == "__main__":
    main()
