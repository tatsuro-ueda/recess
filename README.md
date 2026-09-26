# Recess

AI works, you take recess. Your video plays by itself while the agents work, and pauses to bring you back to the terminal when herdr calls.

![Recess. AI agents are useful, but why do they leave me so strangely exhausted? Brain Fry.](docs/manga-en-1.jpg)

```sh
curl -fsSLO https://raw.githubusercontent.com/tatsuro-ueda/recess/main/install.sh
sh install.sh
```

Then add `~/Applications/Recess.app` to Accessibility. macOS 14 or later, with [herdr](https://herdr.dev) 0.9.1 or later.

I sit in front of the terminal while a few agents work. I am not doing anything. I am waiting to be called, so I cannot leave, and while I watch there is nothing to do. I use agents every day and every day my brain wears down.

Recess hands the waiting time back. While an agent is working it brings the browser to front and sends one space key, so the video plays. When an agent asks a question or finishes, it sends one more space key and brings the terminal to front, so the video pauses. The only thing that sends a key is `Recess.app`, a one-line AppleScript app; the Accessibility permission goes to that app and nothing else, and the Python daemon gets none.

I never watched Netflix. Now I watch it while the AI works. To me, that is surprising.

- **Install guide**: requirements, the two commands, the one permission, on/off, who wrote this → [docs/install.md](docs/install.md)
- **Specification**: how it decides (state diagram), settings, logs and stopping, known weaknesses → [docs/spec.md](docs/spec.md)

Feel Physics / Tatsuro Ueda — [feel-physics.jp](https://feel-physics.jp/). MIT, see [LICENSE](LICENSE).

---

# Recess（日本語）

AI が働く間は休み時間。動画は勝手に再生され、herdr に呼ばれたら止まってターミナルへ戻る。

![Recess 漫画。「AIを使え」って言うけど、もう頭がパンクしそう。脳が油揚げになっちゃう？ AI疲れの新常識「Brain Fry」](docs/manga-ja-1.jpg)

```sh
curl -fsSLO https://raw.githubusercontent.com/tatsuro-ueda/recess/main/install.sh
sh install.sh
```

そのあと `~/Applications/Recess.app` をアクセシビリティに追加する。macOS 14 以降と [herdr](https://herdr.dev) 0.9.1 以降が要る。

AI エージェントがいくつか働いている間、私はターミナルの前に座っている。何もしていない。呼ばれるのを待っているから離れられないし、見ていてもすることはない。毎日使っていて、毎日、頭がすり減っている。

Recess は、その待ち時間を返す。AI が働いている間はブラウザを前に出してスペースキーを1回送るので、動画が動く。AI が質問したか終わったら、スペースをもう1回送ってターミナルを前に出すので、動画が止まる。キーを送るのは AppleScript 1行のアプリ `Recess.app` だけで、アクセシビリティの許可はこのアプリにだけ出す。常駐の python3 には何も渡さない。

もともと私は Netflix をまったく見ない人間だった。それが、AI が働いている間に Netflix を楽しんでいる。私にとっては驚くべきことだ。

- **導入方法**：動作の前提、2行のコマンド、許可、ON/OFF、誰が書いたか → [docs/install.md](docs/install.md#recess-導入方法日本語)
- **仕様詳細**：どう判断しているか（状態遷移図）、設定、ログと止め方、分かっている弱点 → [docs/spec.md](docs/spec.md#recess-仕様詳細日本語)

Feel Physics / 植田達郎 — [feel-physics.jp](https://feel-physics.jp/)。MIT。[LICENSE](LICENSE) を見てください。
