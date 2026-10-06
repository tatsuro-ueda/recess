# Recess: install guide

English first, 日本語は後半（[日本語へ](#recess-導入方法日本語)）. Back to the [README](../README.md). Specification: [spec.md](spec.md).

## Requirements

- macOS 14 or later. Tried on 14.3.1 only.
- herdr 0.9.1 or later, with `herdr` on PATH. `install.sh` records where it found herdr and hands that path to the resident program.
- python3 3.8 or later, standard library only. `/usr/bin/python3` works once the Command Line Tools are installed (`xcode-select --install`); without them `install.sh` looks for another python3 on PATH and stops if there is none.
- If `herdr machine list` has `enabled` machines: ssh to them must work without a prompt (key auth), and `herdr` must be on PATH in a non-interactive shell there. A machine that stops answering is logged as unreachable and its last known state is kept.
- A terminal whose process name is in `iTerm2 Terminal Ghostty kitty Alacritty WezTerm cmux` (see Settings). Only iTerm2 has been tried.

## Install

Two lines. Download, read, then run. Don't pipe curl into sh.

```sh
curl -fsSLO https://raw.githubusercontent.com/tatsuro-ueda/recess/main/install.sh
sh install.sh
```

Source and install files live on GitHub:

```sh
curl -fsSLO https://raw.githubusercontent.com/tatsuro-ueda/recess/main/install.sh
```

`install.sh` fetches the resident program, `recess-watch.py`, when it runs (from the same host, falling back to GitHub), unless a copy sits next to it. If you read before you run, read both; GitHub has the same files.

`install.sh` needs no sudo and does four things:

1. Puts the resident program at `~/.local/share/recess/recess-watch.py` (python3, standard library only).
2. Builds `~/Applications/Recess.app` on your Mac with `osacompile`, from the one line above. Nothing pre-built is downloaded. If a healthy Recess.app is already there, it is kept.
3. Writes `~/Library/LaunchAgents/jp.feel-physics.recess.plist` (RunAtLoad, KeepAlive, PATH = the directory where it found `herdr`, then `~/.local/bin:/usr/local/bin:/opt/homebrew/bin` and the system paths) and loads it.
4. Only with `sh install.sh --with-afplay`: puts a wrapper at `~/.local/bin/afplay` (see "The optional afplay wrapper"). Off by default.

Options:

- `--with-afplay`: see 4 above.
- `--rebuild-app`: rebuild Recess.app even if a healthy one exists. The permission may be lost (see "Known weaknesses").
- `--fetch`: download `recess-watch.py` even if a copy sits next to `install.sh`.
- `--dry-run`: print what it would do, change nothing, no network.

Running `install.sh` again without options is safe. It keeps Recess.app, puts `recess-watch.py` and the plist in place again, and re-registers the launchd job.

Recess starts right away, but it cannot press space until you do the next section.

## Give the permissions to Recess.app, and to nothing else

1. Open System Settings > Privacy & Security > Accessibility.
2. Click "+", press Cmd+Shift+G, type `~/Applications/Recess.app`, click Open, and turn the switch on.
3. The first time space is pressed, macOS asks whether "Recess" may control "System Events". Allow it. This is Automation permission, a second and separate prompt.
4. Do not add python3, Terminal, iTerm or anything else.

See what you just allowed:

```sh
osadecompile ~/Applications/Recess.app/Contents/Resources/Scripts/main.scpt
```

It prints the one line.

Try it: pause a video in the browser, run this in the terminal, and click the video within 5 seconds.

```sh
sleep 5; open -g -W ~/Applications/Recess.app
```

The video should start. If nothing happens, see "Known weaknesses" about permission after a rebuild.

Why not python3: Accessibility lets a process send any key to any app. The resident program is code an AI wrote, running unattended, with ssh into your other machines. Giving it that permission means trusting all of that at once. Giving it to a one-line app means trusting one line.

## Switch it on and off

Recess keeps watching, but you decide when it may move you:

```sh
recess status    # ON or OFF, plus every pane and what is holding a trip back
recess off       # watch only. No browser trips, no call-backs
recess on        # back to normal
recess toggle
```

`recess` is a symlink in `~/.local/bin`. The same switch is registered as a herdr plugin, so you can bind it to a key or run it from herdr:

```sh
herdr plugin action invoke recess.toggle   # also recess.on / recess.off / recess.status
```


## Who wrote this

The code was written by an AI, coding agents running in the terminal. The purpose, the permissions and the way to stop it were decided by the author. It worked on the author's Mac (macOS 14.3.1, herdr 0.9.1, Safari, Netflix) on the night it was written, 2026-09-25 to 26, and the lines above are the ones that held. That is the whole track record so far.


---


---

# Recess 導入方法（日本語）

[README へ戻る](../README.md)。仕様の詳細は [spec.md](spec.md#recess-仕様詳細日本語)。

## 動作の前提

- macOS 14 以降。確かめたのは 14.3.1 だけ。
- herdr 0.9.1 以降。`herdr` が PATH にあること。`install.sh` は見つけた場所を記録して、常駐プログラムに渡します。
- python3 3.8 以降（標準ライブラリのみ）。`/usr/bin/python3` は Command Line Tools（`xcode-select --install`）が入っていれば足ります。無ければ `install.sh` は PATH 上の別の python3 を探し、それも無ければ止まります。
- `herdr machine list` に `enabled` のマシンがある場合：そこへ ssh が聞き返し無しで通ること（鍵認証）と、相手側の非対話シェルで `herdr` が PATH にあること。応答しなくなったマシンは unreachable としてログに出し、最後に分かった状態を持ち続けます。
- プロセス名が `iTerm2 Terminal Ghostty kitty Alacritty WezTerm cmux` のどれかであるターミナル（「設定」参照）。確かめたのは iTerm2 だけ。

## 導入

2行です。落として、読んで、実行する。curl を sh へパイプしないでください。

```sh
curl -fsSLO https://raw.githubusercontent.com/tatsuro-ueda/recess/main/install.sh
sh install.sh
```

ソースと導入ファイルの正本は GitHub です：

```sh
curl -fsSLO https://raw.githubusercontent.com/tatsuro-ueda/recess/main/install.sh
```

`install.sh` は実行時に常駐本体 `recess-watch.py` も取得します（同じホストから。落ちていれば GitHub から）。隣に同じファイルが置いてあればそれを使います。読んでから実行したい人は両方を読んでください。GitHub に同じものがあります。

`install.sh` は sudo 不要で、やることは4つ：

1. 常駐プログラムを `~/.local/share/recess/recess-watch.py` に置く（python3 標準ライブラリのみ）。
2. 上の1行から、あなたの Mac 上で `osacompile` を使って `~/Applications/Recess.app` を作る。ビルド済みのものは落としません。壊れていない Recess.app が既にあれば、そのまま残します。
3. `~/Library/LaunchAgents/jp.feel-physics.recess.plist` を書いて読み込む（RunAtLoad, KeepAlive, PATH は `herdr` が見つかったフォルダ、続けて `~/.local/bin:/usr/local/bin:/opt/homebrew/bin` とシステムのパス）。
4. `sh install.sh --with-afplay` のときだけ、`~/.local/bin/afplay` にラッパーを置く（「任意の afplay ラッパー」を参照）。既定では入れません。

オプション：

- `--with-afplay`：上の4。
- `--rebuild-app`：壊れていない Recess.app があっても作り直す。許可が外れることがあります（「分かっている弱点」を参照）。
- `--fetch`：`install.sh` の隣に `recess-watch.py` があっても使わず、取得元から取り直す。
- `--dry-run`：何をするかだけ表示して、何も変えない。通信もしない。

オプション無しで `install.sh` をもう一度走らせても大丈夫です。Recess.app は残し、`recess-watch.py` と plist を置き直して、launchd の登録をやり直します。

Recess はすぐ動き始めますが、次の節をやるまでスペースは押せません。

## 許可を Recess.app にだけ出す

1. システム設定 > プライバシーとセキュリティ > アクセシビリティ を開く。
2. 「+」を押し、Cmd+Shift+G で `~/Applications/Recess.app` と入力して「開く」。スイッチをオンにする。
3. 初めてスペースが送られるとき、macOS が「"Recess" が "System Events" を制御することを許可しますか」と聞いてきます。許可してください。これはオートメーション許可で、アクセシビリティとは別の2つ目のダイアログです。
4. python3、ターミナル、iTerm など、他のものは追加しない。

いま許可したものの中身を見る：

```sh
osadecompile ~/Applications/Recess.app/Contents/Resources/Scripts/main.scpt
```

1行だけ表示されます。

試す：ブラウザで動画を止めておき、ターミナルでこれを実行して、5秒以内に動画をクリックする。

```sh
sleep 5; open -g -W ~/Applications/Recess.app
```

動画が動き出すはずです。何も起きなければ「分かっている弱点」の、作り直し後の許可の項を見てください。

なぜ python3 に出さないか：アクセシビリティ許可は、そのプロセスがどのアプリにもどんなキーでも送れる許可です。常駐プログラムは AI が書いたコードで、見ていない間も動き、他のマシンへの ssh も握っています。そこに許可を出すのは、それ全部をまとめて信じることです。1行のアプリに出すのは、1行を信じることです。

## ON と OFF の切り替え

常駐は動いたまま、連れ出しと呼び戻しだけを止められます。

```sh
recess status    # ON / OFF と、ペイン一覧・いま連れ出しを妨げているもの
recess off       # 見張るだけ。ブラウザへ行かず、呼び戻しもしない
recess on        # 元に戻す
recess toggle
```

`recess` は `~/.local/bin` のシンボリックリンクです。同じ切り替えが herdr のプラグインとしても登録されるので、herdr から実行したりキーに割り当てたりできます。

```sh
herdr plugin action invoke recess.toggle   # recess.on / recess.off / recess.status も同じ
```


## 誰が書いたか

このコードは AI に書かせました。ターミナルで動くコーディングエージェントです。目的と、権限と、止め方を決めたのは作者です。書いた夜（2026年9月25日から26日）に作者の Mac（macOS 14.3.1、herdr 0.9.1、Safari、Netflix）で動き、上に書いた線がそのとき持ちこたえた線です。実績はいまのところそれだけです。


