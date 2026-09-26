#!/usr/bin/env python3
"""README.md（物語の部分）を docs/index.html に変換する。外部ライブラリなし。
使い方: python3 scripts/build-site.py   （リポジトリのルートで実行）
README を直したら、これを走らせて index.html を作り直し、両方を commit する。"""
import html, re, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
OUT = os.path.join(ROOT, "docs", "index.html")
REPO = "https://github.com/tatsuro-ueda/recess"

def slug(text):
    t = re.sub(r"[*`\[\]()（）:：.,、。!?！？\"']", "", text).strip().lower()
    return re.sub(r"\s+", "-", t)

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    def link(m):
        text, url = m.group(1), m.group(2)
        if url.startswith("docs/") and ".md" in url:
            url = REPO + "/blob/main/" + url          # Markdown ページ（アンカー付きも）は GitHub 側で読む
        elif url.startswith("docs/"):
            url = url[len("docs/"):]                  # 画像などは同じフォルダ
        elif url == "LICENSE":
            url = REPO + "/blob/main/LICENSE"
        return f'<a href="{url}">{text}</a>'
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)
    return s

def convert(md):
    lines = md.splitlines()
    out, i = [], 0
    in_code = False; code = []
    para = []
    def flush_para():
        nonlocal para
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>"); para = []
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            flush_para()
            if not in_code:
                in_code = True; code = []
            else:
                in_code = False
                out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            i += 1; continue
        if in_code:
            code.append(ln); i += 1; continue
        if not ln.strip():
            flush_para(); i += 1; continue
        if ln.startswith("---"):
            flush_para(); out.append("<hr>"); i += 1; continue
        m = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if m:
            flush_para(); level = len(m.group(1)); text = m.group(2)
            out.append(f'<h{level} id="{slug(text)}">{inline(text)}</h{level}>'); i += 1; continue
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", ln)
        if m:
            flush_para(); alt, src = m.group(1), m.group(2)
            if src.startswith("docs/"): src = src[len("docs/"):]
            out.append(f'<figure><img src="{src}" alt="{html.escape(alt)}" loading="lazy"></figure>'); i += 1; continue
        if ln.startswith("|"):
            flush_para(); rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            body = [r for r in rows if not all(re.match(r"^:?-+:?$", c) for c in r)]
            head, rest = body[0], body[1:]
            t = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            for r in rest: t += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
            out.append(t + "</tbody></table>"); continue
        if re.match(r"^\s*[-*]\s+", ln):
            flush_para(); items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i])); i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>"); continue
        if re.match(r"^\s*\d+\.\s+", ln):
            flush_para(); items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i])); i += 1
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>"); continue
        if ln.startswith(">"):
            flush_para(); q = []
            while i < len(lines) and lines[i].startswith(">"):
                q.append(lines[i].lstrip("> ")); i += 1
            out.append("<blockquote>" + inline(" ".join(q)) + "</blockquote>"); continue
        para.append(ln.strip()); i += 1
    flush_para()
    return "\n".join(out)

CSS = """
  :root { --bg:#fbfaf7; --fg:#1f1d1a; --muted:#6b665e; --line:#dcd7cd; --accent:#0f5c8c; --code-bg:#f0ede6; }
  @media (prefers-color-scheme: dark) { :root { --bg:#17161a; --fg:#ece8e1; --muted:#a39d93; --line:#35333a; --accent:#7dbbe6; --code-bg:#232228; } }
  * { box-sizing: border-box; } html { -webkit-text-size-adjust: 100%; }
  body { margin:0; background:var(--bg); color:var(--fg); font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",sans-serif; font-size:17px; line-height:1.8; overflow-wrap:anywhere; }
  main { max-width:40rem; margin:0 auto; padding:32px 16px 64px; }
  h1 { font-size:1.9rem; line-height:1.3; margin:24px 0 8px; } h2 { font-size:1.25rem; margin:40px 0 8px; padding-top:8px; border-top:1px solid var(--line); }
  h3 { font-size:1.05rem; margin:24px 0 4px; }
  a { color:var(--accent); } code { background:var(--code-bg); padding:.1em .35em; border-radius:4px; font-size:.92em; }
  pre { background:var(--code-bg); padding:12px 14px; border-radius:8px; overflow-x:auto; line-height:1.5; } pre code { background:none; padding:0; }
  figure { margin:16px 0; } figure img { width:100%; height:auto; display:block; border:1px solid var(--line); border-radius:6px; }
  table { border-collapse:collapse; width:100%; margin:12px 0; font-size:.95em; } th, td { border:1px solid var(--line); padding:6px 8px; vertical-align:top; text-align:left; }
  blockquote { margin:12px 0; padding:4px 14px; border-left:3px solid var(--line); color:var(--muted); }
  hr { border:0; border-top:1px solid var(--line); margin:40px 0; }
  footer { max-width:40rem; margin:0 auto; padding:0 16px 48px; color:var(--muted); font-size:.9em; }
"""

md = open(README, encoding="utf-8").read()
body = convert(md)
# ページ内リンク（#…）は、見出しの id とハイフン無しで照合して付け替える
ids = re.findall(r'id="([^"]+)"', body)
def fix_anchor(m):
    target = m.group(1)
    if target in ids: return m.group(0)
    for i in ids:
        if i.replace("-", "") == target.replace("-", ""): return f'href="#{i}"'
    return m.group(0)
body = re.sub(r'href="#([^"]+)"', fix_anchor, body)
title = "Recess"
desc = "AI works, you take recess. Your video plays by itself while the agents work, and pauses to bring you back to the terminal when herdr calls."
page = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<meta name="description" content="{html.escape(desc)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:image" content="https://tatsuro-ueda.github.io/recess/manga-en-1.jpg">
<meta name="twitter:card" content="summary_large_image">
<style>{CSS}</style>
</head>
<body>
<main>
{body}
</main>
<footer>
<p>Generated from <a href="{REPO}/blob/main/README.md">README.md</a> by <code>scripts/build-site.py</code>.</p>
</footer>
</body>
</html>
"""
open(OUT, "w", encoding="utf-8").write(page)
print(f"wrote {OUT} ({len(page)} bytes)")
