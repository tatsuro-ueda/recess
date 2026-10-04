---
status: latest
dateCreated: 2026-10-04
dateModified: 2026-10-04
---

# 開発チェックリスト（Recess）

`docs/` の4文書から生成した派生物。正本は docs 側。docs を直したら `make-development-checklist` を呼び直す。

**使い方**：章ごとに1回だけ「この章は対象か」を判断する。項目ごとに対象かどうかを考えない。
例：画面を動かす数値にも通知にもログにも触らない変更なら、0章とD章は「章ごと対象外（理由）」で通してよい。

---

## 0章: 共通の物差し（12件 ＋ 実測1件）

画面と記録に関わる数値・作法。直す順番は「共通 → 個別 → 部品」なので、この章を最初に置く。

- [ ] やめる手段が1手より深くなっていない（根拠：docs/ux-policy.md 最上位の約束：いつでも1手でやめられる）
- [ ] 画面に関わる数値は共通の物差し表の値を使い、場面ごとに似た値を新設していない（根拠：docs/ux-policy.md 共通の物差し（具体値））
- [ ] 見回りの間隔は2秒（根拠：docs/ux-policy.md 共通の物差し（具体値））
- [ ] 手を離したとみなす時間は3秒（根拠：docs/ux-policy.md 共通の物差し（具体値））
- [ ] 予告を読む時間は5秒（根拠：docs/ux-policy.md 共通の物差し（具体値））
- [ ] 送るキーはスペース1回だけ（根拠：docs/ux-policy.md 共通の物差し（具体値））
- [ ] 画面に出す印は常に1つだけ（根拠：docs/ux-policy.md 共通の物差し（具体値））
- [ ] 1出来事につき通知は1本で、同じ結果を言い分けていない（根拠：docs/ux-policy.md 共通の物差し（具体値））
- [ ] すべてのログ行がタグから始まり、文章がそのまま始まる行が無い（根拠：docs/ux-policy.md 記録の作法1）
- [ ] タグ一覧が1か所にあり、一覧に無いタグで記録しようとしたら落ちる（根拠：docs/ux-policy.md 記録の作法2）
- [ ] ログが3階層（動いた／決めた／見ていた）に分かれている（根拠：docs/ux-policy.md 記録の作法3）
- [ ] 階層の差が1軸だけで示されている（根拠：docs/ux-policy.md 記録の作法4）
- [ ] **実測**：`watch.log` の行頭を集計し、タグが一覧どおりで、画面が動いた記録が背景に埋もれていないことを目で確認した（根拠：docs/ux-policy.md 記録の作法3・docs/functional-design.md 記録）

## A章: 設計判断（8件）

- [ ] キーを送るのは `Recess.app` だけで、python3 に許可を出していない（根拠：docs/architecture.md 権限をアプリ1つに閉じ込める）
- [ ] 常駐が使う Mac 側の道具は権限不要のものだけ（`open` `lsappinfo` `caffeinate` `ioreg` `who`）（根拠：docs/architecture.md 権限をアプリ1つに閉じ込める）
- [ ] `osascript` を使っていない（根拠：docs/architecture.md 権限をアプリ1つに閉じ込める）
- [ ] 状態はイベント待ち受けではなく、一定間隔で集めて前回との差分で判断している（根拠：docs/architecture.md 状態は「集めて、差分で見る」）
- [ ] 新しい状態源は、既存と同じ形に揃えてから1つの列に並べている（根拠：docs/architecture.md 状態源は足せる形にする）
- [ ] 判定の本体が状態源の種類を知らない（根拠：docs/architecture.md 状態源は足せる形にする）
- [ ] 区画を持たない状態源へ移動を指示していない（根拠：docs/architecture.md 状態源は足せる形にする）
- [ ] ある源が黙っても、他の源の判断が続く（根拠：docs/architecture.md 状態源は足せる形にする）

## B章: 責務分担（6件）

- [ ] 判定は `recess-watch.py` の1か所にあり、hook 側や CLI 側に同じ判断を書いていない（根拠：docs/repository-structure.md 決めごと）
- [ ] hook は状態を書くだけで、連れ出すかどうかを決めていない（根拠：docs/repository-structure.md 決めごと）
- [ ] `tools/` のスクリプトを常駐から呼んでいない（根拠：docs/repository-structure.md 決めごと）
- [ ] 状態と記録はすべて `~/.local/state/recess/` の下にあり、repo に置いていない（根拠：docs/repository-structure.md 決めごと）
- [ ] 同じ判定が2か所に現れていない（関数へ出して1か所から呼んでいる）（根拠：docs/repository-structure.md 決めごと）
- [ ] 各ファイルが責務分担表の「持たないもの」を持っていない（根拠：docs/repository-structure.md 責務分担）

## C章: 枠組みの決めごと（9件）

- [ ] 常駐が python3 標準ライブラリだけで動く（パッケージを追加していない）（根拠：docs/framework-rule.md 言語と依存）
- [ ] CLI と導入が sh で、bash 専用の書き方をしていない（根拠：docs/framework-rule.md 言語と依存）
- [ ] hook は失敗しても正常終了する（根拠：docs/framework-rule.md 他人のプロセスを止めない）
- [ ] 常駐は1周で例外が出ても落ちず、記録を残して次の周へ進む（根拠：docs/framework-rule.md 他人のプロセスを止めない）
- [ ] 秘密をファイルに持っていない（根拠：docs/framework-rule.md 外へ出すもの）
- [ ] 記録にプロンプトの中身を書いていない（根拠：docs/framework-rule.md 外へ出すもの）
- [ ] 画面を動かす判定を、実コードを読み込んで最前面アプリだけ差し替えるハーネスで確かめた（根拠：docs/framework-rule.md 確かめ方）
- [ ] `python3 -m py_compile` が通る（根拠：docs/framework-rule.md 確かめ方）
- [ ] 画面が動くふるまいは、机の上で1日動かしてから「できた」と言う（根拠：docs/framework-rule.md 確かめ方）

## D章: 画面を動かす作法（11件）

- [ ] 画面を動かすのは状態が大きく変わる瞬間だけで、同じ状態の中の変化では動かさない（根拠：docs/ux-policy.md 画面を動かしてよいか1）
- [ ] 連れ出すのは帰り先にいる人だけ（根拠：docs/ux-policy.md 画面を動かしてよいか2）
- [ ] 呼び戻すのは動画を見ている人だけ（根拠：docs/ux-policy.md 画面を動かしてよいか3）
- [ ] 見送ったときは理由を1行残している（根拠：docs/ux-policy.md 画面を動かしてよいか4）
- [ ] 見送った回の印を覚えて後で動かしていない（根拠：docs/ux-policy.md 画面を動かしてよいか5）
- [ ] 動く前に知らせている（根拠：docs/ux-policy.md 知らせ方1）
- [ ] 予告にやめ方が書かれている（根拠：docs/ux-policy.md 知らせ方2）
- [ ] やめたことを知らせている（根拠：docs/ux-policy.md 知らせ方3）
- [ ] 人がやめさせたことを受け身で書いていない（根拠：docs/ux-policy.md 知らせ方4）
- [ ] できなかったことを1本の通知で知らせている（根拠：docs/ux-policy.md 知らせ方5）
- [ ] 通知の文に内部の言葉（`focus` など）が混ざっていない（根拠：docs/ux-policy.md 知らせ方6）
