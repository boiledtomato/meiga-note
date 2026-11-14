#!/usr/bin/env python3
"""
content/posts/*.md から静的サイトを _site/ に生成する。
あわせて REPORT.md（記事数・コスト・売上のレポート）を更新する。

  python3 scripts/build_site.py                    # 全ブログをビルド
  python3 scripts/build_site.py --site art         # 美術ブログだけ
  python3 scripts/build_site.py --check            # フロントマター検証のみ（エラーなら終了コード1）
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import markdown
import yaml

import site_enhance

ROOT = Path(__file__).resolve().parent.parent
SITES = ("art",)
OUT_ROOT = ROOT / "_site"

# configure() でブログごとに設定される
SITE = BLOG = POSTS_DIR = OUT = None
CFG: dict = {}
BASE = BASE_PATH = ""

REQUIRED = ["title", "date", "summary", "topic_id", "sources", "learning", "quiz"]


def configure(site: str) -> None:
    global SITE, BLOG, POSTS_DIR, OUT, CFG, BASE, BASE_PATH
    SITE = site
    BLOG = ROOT
    POSTS_DIR = BLOG / "content" / "posts"
    OUT = OUT_ROOT
    CFG = json.loads((BLOG / "config.json").read_text(encoding="utf-8"))
    BASE = CFG["base_url"].rstrip("/")
    BASE_PATH = urllib.parse.urlparse(BASE).path.rstrip("/")  # 例: /zscaler-monitor/art
USD_JPY = 150  # レポート用の概算レート


# ------------------------------------------------------------------ load

def load_posts() -> tuple[list[dict], list[str]]:
    posts, errors = [], []
    seen_topics: dict[str, str] = {}
    for p in sorted(POSTS_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if not m:
            errors.append(f"{p.name}: フロントマターがありません")
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            errors.append(f"{p.name}: YAML エラー {e}")
            continue
        missing = [k for k in REQUIRED if not fm.get(k)]
        if missing:
            errors.append(f"{p.name}: 必須項目が不足 {missing}")
        nav_tags = [n["tag"] for n in CFG.get("nav", [])]
        if nav_tags and not (set(fm.get("tags") or []) & set(nav_tags)):
            errors.append(f"{p.name}: tags にナビ用タグ {nav_tags} のいずれかを含めてください")
        if fm.get("image") and not fm.get("image_credit"):
            errors.append(f"{p.name}: image には image_credit が必要です")
        for q in fm.get("quiz") or []:
            if not (isinstance(q, dict) and q.get("q") and q.get("a")):
                errors.append(f"{p.name}: quiz は q / a のペアで書いてください")
                break
        tid = str(fm.get("topic_id"))
        if tid in seen_topics:
            errors.append(f"{p.name}: topic_id {tid} が {seen_topics[tid]} と重複")
        seen_topics[tid] = p.name
        d = fm.get("date")
        fm["date"] = d if isinstance(d, date) else date.fromisoformat(str(d))
        fm["slug"] = p.stem
        fm["body_md"] = m.group(2)
        fm["tags"] = fm.get("tags") or []
        posts.append(fm)
    posts.sort(key=lambda x: (x["date"], x["slug"]), reverse=True)
    return posts, errors


def load_json(name: str, default):
    f = BLOG / "data" / name
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default


# ------------------------------------------------------------------ html parts

e = html.escape


def url(path: str) -> str:
    return f"{BASE_PATH}/{path.lstrip('/')}"


def css() -> str:
    t = CFG.get("theme", {})
    font = ('"Hiragino Mincho ProN","Noto Serif JP","Yu Mincho",serif' if t.get("font") == "serif"
            else '"Hiragino Sans","Noto Sans JP","Yu Gothic",system-ui,sans-serif')
    return (CSS.replace("__ACCENT__", t.get("accent", "#2f5d8a"))
               .replace("__ACCENT_DARK__", t.get("accent_dark", "#8ab4e0"))
               .replace("__FONT__", font) + site_enhance.CSS).strip()


CSS = """
:root{--warn:#b0413e;--bg:#fbfaf7;--fg:#1f2328;--muted:#5d646d;--line:#e3e0d8;--card:#fff;--accent:__ACCENT__;--code:#f2efe8}
@media (prefers-color-scheme:dark){:root{--warn:#ff8a7a;--bg:#16181c;--fg:#e6e6e6;--muted:#a2a8b0;--line:#2c3036;--card:#1d2025;--accent:__ACCENT_DARK__;--code:#24282e}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.85 __FONT__}
a{color:var(--accent);overflow-wrap:anywhere}img{max-width:100%;height:auto}
.wrap{max-width:780px;margin:0 auto;padding:0 16px}
header.site{border-bottom:1px solid var(--line);background:var(--card)}
header.site .wrap{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:baseline;padding-top:14px;padding-bottom:14px}
header.site .brand{font-weight:700;font-size:1.1rem;text-decoration:none;color:var(--fg)}
header.site nav a{margin-right:14px;font-size:.92rem;text-decoration:none}
main{padding:28px 0 48px}
h1{font-size:1.6rem;line-height:1.45;margin:.2em 0 .4em}h2{font-size:1.25rem;margin-top:2em;border-left:4px solid var(--accent);padding-left:10px}
h3{font-size:1.08rem;margin-top:1.6em}
.meta{color:var(--muted);font-size:.85rem}
.chip{display:inline-block;font-size:.75rem;padding:1px 8px;border-radius:99px;border:1px solid var(--line);margin-right:4px;color:var(--muted);text-decoration:none}
.chip.nav{color:var(--accent);border-color:var(--accent)}
.list{list-style:none;padding:0;margin:0}.list li{padding:16px 0;border-bottom:1px solid var(--line)}
.list a.t{font-weight:700;font-size:1.05rem;text-decoration:none;color:var(--fg)}.list p{margin:.3em 0 0;color:var(--muted);font-size:.92rem}
table{border-collapse:collapse;width:100%;display:block;overflow-x:auto;font-size:.92rem}th,td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}th{background:var(--code)}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:.9em}pre{background:var(--code);padding:12px;overflow-x:auto;border-radius:6px}pre code{padding:0}
blockquote{margin:1em 0;padding:.2em 1em;border-left:3px solid var(--line);color:var(--muted)}
.box{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 18px;margin:24px 0}
.box h2{margin-top:0;border:0;padding:0;font-size:1.05rem}
details{margin:.5em 0;padding:8px 12px;border:1px solid var(--line);border-radius:6px;background:var(--bg)}summary{cursor:pointer;font-weight:600}
figure{margin:0 0 20px}figcaption{font-size:.8rem;color:var(--muted)}
.pr{font-size:.78rem;color:var(--muted)}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.82rem;padding:20px 0 40px}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.kpi div{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}.kpi b{display:block;font-size:1.4rem}
"""


def layout(title: str, body: str, *, description: str = "", canonical: str = "", noindex: bool = False,
           og_image: str = "", json_ld: dict | None = None) -> str:
    desc = description or CFG["site_description"]
    full_title = title if title == CFG["site_title"] else f"{title} | {CFG['site_title']}"
    ads = CFG["monetization"].get("adsense_client")
    head_extra = []
    if ads:
        head_extra.append(f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={e(ads)}" crossorigin="anonymous"></script>')
    if noindex:
        head_extra.append('<meta name="robots" content="noindex">')
    if canonical:
        head_extra.append(f'<link rel="canonical" href="{e(canonical)}">')
        head_extra.append(f'<meta property="og:url" content="{e(canonical)}">')
    if og_image:
        head_extra.append(f'<meta property="og:image" content="{e(og_image)}">')
    if json_ld:
        head_extra.append(f'<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>')
    cats = "".join(f'<a href="{url("tag/" + urllib.parse.quote(n["tag"]) + "/")}">{e(n["label"])}</a>' for n in CFG.get("nav", []))
    return f"""<!doctype html>
<html lang="{CFG['language']}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title><meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(full_title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:type" content="website">
<link rel="alternate" type="application/rss+xml" title="{e(CFG['site_title'])}" href="{url('feed.xml')}">
<link rel="stylesheet" href="{url('style.css')}">
<script src="{url('assets/site.js')}" defer></script>
{chr(10).join(head_extra)}
</head><body>
<header class="site"><div class="wrap"><a class="brand" href="{url('')}">{e(CFG['site_title'])}</a>
<nav>{cats}<a href="{url('timeline/')}">年表</a><a href="{url('learn/')}">学習ノート</a><a href="{url('about/')}">このブログについて</a></nav></div></header>
<main><div class="wrap">{body}</div></main>
<footer><div class="wrap">{e(CFG['monetization']['pr_disclosure'])}<br>
{e(CFG['disclaimer'])}<br>
© {date.today().year} {e(CFG['author'])} · <a href="{url('about/')}">プライバシーポリシー</a> · <a href="{url('feed.xml')}">RSS</a></div></footer>
</body></html>"""


def chips(p: dict) -> str:
    nav_tags = {n["tag"] for n in CFG.get("nav", [])}
    out = ""
    for t in p["tags"][:5]:
        t = str(t)
        if t in nav_tags:
            out += f'<a class="chip nav" href="{url("tag/" + urllib.parse.quote(t) + "/")}">{e(t)}</a>'
        else:
            out += f'<span class="chip">{e(t)}</span>'
    return out


def post_list(posts: list[dict]) -> str:
    items = []
    for p in posts:
        items.append(f'<li><div class="meta">{p["date"].isoformat()} {chips(p)}</div>'
                     f'<a class="t" href="{url("posts/" + p["slug"] + "/")}">{e(p["title"])}</a>'
                     f'<p>{e(p["summary"])}</p></li>')
    return f'<ul class="list">{"".join(items)}</ul>' if items else "<p>まだ記事がありません。</p>"


def affiliate_box() -> str:
    mon = CFG["monetization"]
    tag = mon.get("amazon_associate_tag")
    links = mon.get("affiliates") or []
    if not tag or not links:
        return ""
    lis = "".join(
        f'<li><a href="https://www.amazon.co.jp/s?k={urllib.parse.quote(l["amazon_keyword"])}&tag={urllib.parse.quote(tag)}" '
        f'rel="sponsored noopener" target="_blank">{e(l["label"])}</a></li>' for l in links)
    return f'<div class="box"><h2>さらに学ぶための本</h2><ul>{lis}</ul><p class="pr">PR：上記はアフィリエイトリンクです。</p></div>'


LIST_RE = re.compile(r"^(\s*)([-*+] |\d+\. )")


def fix_lists(text: str) -> str:
    """段落の直後に空行なしで始まるリストを、リストとして扱われるよう空行を補う。"""
    out, fence = [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            fence = not fence
        prev = out[-1] if out else ""
        if (not fence and LIST_RE.match(line) and prev.strip() and not LIST_RE.match(prev)
                and not prev.lstrip().startswith(("|", "<", "#")) and not prev.startswith(" ")):
            out.append("")
        out.append(line)
    return "\n".join(out)


def render_md(text: str) -> str:
    return markdown.markdown(fix_lists(text), extensions=["tables", "fenced_code", "toc", "sane_lists"])


def mark_points(body_html: str) -> tuple[str, list[str]]:
    """「見どころ」の h2 の下にある h3 に point-1, point-2 … の id を付ける。"""
    m = re.search(r'<h2 id="[^"]*">見どころ[^<]*</h2>(.*?)(?=<h2 )', body_html, re.S)
    if not m or "<h3" not in m.group(1):
        # 「見どころ1：…」「見どころ2：…」のように h2 を並べた書き方
        ids, n = [], 0
        def rep2(mm):
            nonlocal n
            n += 1
            ids.append(f"point-{n}")
            return f'<h2 id="point-{n}" data-point>{mm.group(1)}'
        out = re.sub(r'<h2 id="[^"]*">(見どころ\s*[0-9０-９])', rep2, body_html)
        return out, ids
    sect, ids, n = m.group(1), [], 0
    def rep(mm):
        nonlocal n
        n += 1
        ids.append(f"point-{n}")
        return f'<h3 id="point-{n}" data-point>'
    sect2 = re.sub(r'<h3 id="[^"]*">', rep, sect)
    return body_html[:m.start(1)] + sect2 + body_html[m.end(1):], ids


def post_page(p: dict, prev_p: dict | None, next_p: dict | None) -> str:
    canonical = f"{BASE}/posts/{p['slug']}/"
    terms = [dict(t, link=url("posts/" + t["link"] + "/")) if t.get("link") else t for t in load_json("glossary.json", [])]
    body_html, point_ids = mark_points(render_md(p["body_md"]))
    body_html, toc = site_enhance.enhance(body_html, terms=terms, slug=url("posts/" + p["slug"] + "/"))
    fig = ""
    if p.get("image"):
        full = f' data-full="{e(p["image_full"])}"' if p.get("image_full") else ""
        pts = ""
        for i, pt in enumerate(p.get("points") or []):
            if i < len(point_ids):
                pts += (f'<a class="pt" href="#{point_ids[i]}" style="left:{float(pt["x"]) * 100:.1f}%;top:{float(pt["y"]) * 100:.1f}%"'
                        f' aria-label="見どころ{i + 1}へ">{i + 1}</a>')
        hint = "（画像をクリックすると高解像度で拡大できます" + ("。番号は本文の見どころの位置です）" if pts else "）") if full else ""
        fig = (f'<figure><span class="hot"><img src="{e(p["image"])}" alt="{e(p["title"])}" loading="lazy"{full}>{pts}</span>'
               f'<figcaption>{e(p["image_credit"])}{hint}</figcaption></figure>')
    learn = "".join(f"<li>{e(str(x))}</li>" for x in p["learning"])
    quiz = "".join(f"<details><summary>Q{i}. {e(q['q'])}</summary><p>{e(q['a'])}</p></details>"
                   for i, q in enumerate(p["quiz"], 1))
    srcs = "".join(f'<li><a href="{e(s)}" rel="noopener" target="_blank">{e(s)}</a></li>' for s in p["sources"])
    nav = []
    if next_p:
        nav.append(f'← <a href="{url("posts/" + next_p["slug"] + "/")}">{e(next_p["title"])}</a>')
    if prev_p:
        nav.append(f'<a href="{url("posts/" + prev_p["slug"] + "/")}">{e(prev_p["title"])}</a> →')
    body = f"""<article>
<div class="meta">{p['date'].isoformat()} {chips(p)}</div>
<h1>{e(p['title'])}</h1>
{fig}
<div class="box"><h2>この記事で学べること</h2><ul>{learn}</ul></div>
{toc}{body_html}
<div class="box"><h2>確認クイズ</h2>{quiz}</div>
{affiliate_box()}
<div class="box"><h2>参考・出典</h2><ul>{srcs}</ul></div>
</article>
<p class="meta">{'　'.join(nav)}</p>"""
    ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"],
          "datePublished": p["date"].isoformat(), "author": {"@type": "Person", "name": CFG["author"]},
          "description": p["summary"], "mainEntityOfPage": canonical}
    if p.get("image"):
        ld["image"] = p["image"]
    return layout(p["title"], body, description=p["summary"], canonical=canonical,
                  og_image=p.get("image", ""), json_ld=ld)


def fmt_gap(years: int) -> str:
    if years >= 10000:
        return f"約{round(years / 10000)}万年"
    if years >= 1000:
        return f"約{round(years / 100) * 100:,}年"
    return f"約{years}年"


def timeline_page(posts: list[dict]) -> str:
    items = sorted([p for p in posts if p.get("era") is not None], key=lambda p: float(p["era"]))
    rows, prev = [], None
    for p in items:
        era = int(float(p["era"]))
        if prev is not None and era - prev >= 300:
            rows.append(f'<div class="gap">― {fmt_gap(era - prev)}の隔たり ―</div>')
        label = p.get("era_label") or (f"前{-era}年ごろ" if era < 0 else f"{era}年ごろ")
        rows.append(f'<li><div class="era">{e(str(label))}</div><a href="{url("posts/" + p["slug"] + "/")}">{e(p["title"])}</a>'
                    f'<p>{e(p["summary"])}</p></li>')
        prev = era
    body = ("<h1>年表：時代を超えてたどる</h1><p>このブログで取り上げた作品やテーマを、時代の古い順に並べました。"
            "記事どうしの間にどれだけの時間が流れているかも示しています。</p>"
            f'<ul class="tl">{"".join(rows)}</ul>')
    return layout("年表", body, canonical=f"{BASE}/timeline/")


def learn_page(posts: list[dict]) -> str:
    parts = [f"<h1>学習ノート</h1><p>全{len(posts)}記事の学習ポイントと確認クイズをまとめた復習用ページです。</p>"]
    if True:
        for p in posts:
            pts = "".join(f"<li>{e(str(x))}</li>" for x in p["learning"])
            qs = "".join(f"<details><summary>{e(q['q'])}</summary><p>{e(q['a'])}</p></details>" for q in p["quiz"])
            parts.append(f'<h3><a href="{url("posts/" + p["slug"] + "/")}">{e(p["title"])}</a></h3>'
                         f'<div class="meta">{p["date"].isoformat()}</div><ul>{pts}</ul>{qs}')
    return layout("学習ノート", "".join(parts))


def about_page() -> str:
    intro = "".join(f"<p>{e(x)}</p>" for x in CFG.get("about", []))
    body = f"""<h1>このブログについて</h1>
{intro}
<p>内容の正確性には注意していますが、最終的な判断は一次情報（公式ドキュメント・所蔵館の情報）でご確認ください。</p>
<h2>プライバシーポリシー</h2>
<p>当ブログでは、第三者配信の広告サービス（Google AdSense）やアフィリエイトプログラム（Amazonアソシエイト等）を利用する場合があります。
これらの事業者は、ユーザーの興味に応じた広告を表示するために Cookie を使用することがあります。
Cookie を無効にする方法や Google の広告に関する詳細は
<a href="https://policies.google.com/technologies/ads?hl=ja">Google のポリシーと規約</a>をご覧ください。</p>
<p>当ブログは Amazon.co.jp を宣伝しリンクすることによってサイトが紹介料を獲得できる手段を提供することを目的に設定された
アフィリエイトプログラムである、Amazonアソシエイト・プログラムの参加者です（参加後に有効）。</p>
<h2>免責事項</h2>
<p>当ブログの情報を利用して生じた損害について、一切の責任を負いかねます。</p>"""
    return layout("このブログについて", body)


# ------------------------------------------------------------------ report

def finance(posts: list[dict]) -> dict:
    costs = load_json("costs.json", {"entries": []})["entries"]
    revenue = load_json("revenue.json", {"entries": []})["entries"]
    months: dict[str, dict] = defaultdict(lambda: {"posts": 0, "cost_jpy": 0.0, "revenue_jpy": 0.0})
    for p in posts:
        months[p["date"].strftime("%Y-%m")]["posts"] += 1
    for c in costs:
        jpy = c.get("jpy", c.get("usd", 0) * USD_JPY)
        months[str(c["date"])[:7]]["cost_jpy"] += jpy
    for r in revenue:
        months[r["month"]]["revenue_jpy"] += r.get("amount_jpy", 0)
    tot = {k: sum(m[k] for m in months.values()) for k in ("posts", "cost_jpy", "revenue_jpy")}
    by_source: dict[str, float] = defaultdict(float)
    for r in revenue:
        by_source[r.get("source", "不明")] += r.get("amount_jpy", 0)
    return {"months": dict(sorted(months.items(), reverse=True)), "total": tot, "by_source": dict(by_source)}


def write_report(posts: list[dict], fin: dict) -> None:
    t = fin["total"]
    lines = [f"# ブログ運用レポート：{CFG['site_title']}", "",
             f"_自動生成: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}（scripts/build_site.py）_", "",
             f"- 公開URL: {BASE}/",
             f"- 公開記事数: **{t['posts']}**",
             f"- 累計売上: **{t['revenue_jpy']:,.0f} 円**",
             f"- 累計コスト: **{t['cost_jpy']:,.0f} 円**（API・ドメイン等。サブスク内の実行は0円計上）",
             f"- 累計収支: **{t['revenue_jpy'] - t['cost_jpy']:,.0f} 円**", "",
             "## 月別", "", "| 月 | 記事数 | 売上(円) | コスト(円) | 収支(円) |", "|---|---:|---:|---:|---:|"]
    for m, v in fin["months"].items():
        lines.append(f"| {m} | {v['posts']} | {v['revenue_jpy']:,.0f} | {v['cost_jpy']:,.0f} | {v['revenue_jpy'] - v['cost_jpy']:,.0f} |")
    if fin["by_source"]:
        lines += ["", "## 収益源別", "", "| 収益源 | 累計(円) |", "|---|---:|"]
        lines += [f"| {k} | {v:,.0f} |" for k, v in fin["by_source"].items()]
    lines += ["", "## 最近の記事", ""]
    lines += [f"- {p['date']} {p['title']}" for p in posts[:10]]
    lines += ["", f"売上は `data/revenue.json` に月ごとに記録します（Claude に「11月のAdSenseは○円」と伝えれば追記されます）。", ""]
    (BLOG / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def dashboard_page(fin: dict) -> str:
    t = fin["total"]
    rows = "".join(f"<tr><td>{m}</td><td>{v['posts']}</td><td>{v['revenue_jpy']:,.0f}</td><td>{v['cost_jpy']:,.0f}</td>"
                   f"<td>{v['revenue_jpy'] - v['cost_jpy']:,.0f}</td></tr>" for m, v in fin["months"].items())
    body = f"""<h1>運用ダッシュボード</h1>
<div class="kpi"><div>記事数<b>{t['posts']}</b></div><div>累計売上<b>{t['revenue_jpy']:,.0f}円</b></div>
<div>累計コスト<b>{t['cost_jpy']:,.0f}円</b></div><div>収支<b>{t['revenue_jpy'] - t['cost_jpy']:,.0f}円</b></div></div>
<h2>月別</h2><table><tr><th>月</th><th>記事</th><th>売上</th><th>コスト</th><th>収支</th></tr>{rows}</table>"""
    return layout("運用ダッシュボード", body, noindex=True)


# ------------------------------------------------------------------ feeds

def feed_xml(posts: list[dict]) -> str:
    items = []
    for p in posts[:30]:
        link = f"{BASE}/posts/{p['slug']}/"
        pub = datetime.combine(p["date"], datetime.min.time(), tzinfo=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        items.append(f"<item><title>{e(p['title'])}</title><link>{link}</link><guid>{link}</guid>"
                     f"<pubDate>{pub}</pubDate><description>{e(p['summary'])}</description></item>")
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{e(CFG["site_title"])}</title>'
            f'<link>{BASE}/</link><description>{e(CFG["site_description"])}</description><language>ja</language>'
            f'{"".join(items)}</channel></rss>')


def sitemap_xml(posts: list[dict]) -> str:
    urls = [f"{BASE}/", f"{BASE}/learn/", f"{BASE}/about/"] + [f"{BASE}/tag/{urllib.parse.quote(n['tag'])}/" for n in CFG.get("nav", [])]
    entries = [f"<url><loc>{u}</loc></url>" for u in urls]
    entries += [f"<url><loc>{BASE}/posts/{p['slug']}/</loc><lastmod>{p['date'].isoformat()}</lastmod></url>" for p in posts]
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{"".join(entries)}</urlset>'


# ------------------------------------------------------------------ main

def write(rel: str, content: str) -> None:
    f = OUT / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")


def build(check: bool) -> int:
    posts, errors = load_posts()
    if errors:
        print("\n".join(f"ERROR [{SITE}]: " + x for x in errors), file=sys.stderr)
        return 1
    if check:
        print(f"OK [{SITE}]: {len(posts)} posts")
        return 0

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    write("style.css", css())
    write("assets/site.js", site_enhance.js({}))
    intro = f"<p>{e(CFG['site_description'])}</p>"
    write("index.html", layout(CFG["site_title"], intro + post_list(posts), canonical=f"{BASE}/"))
    for n in CFG.get("nav", []):
        ps = [p for p in posts if n["tag"] in map(str, p["tags"])]
        write(f"tag/{n['tag']}/index.html", layout(n["label"], f"<h1>{e(n['label'])}</h1>" + post_list(ps),
                                                   canonical=f"{BASE}/tag/{urllib.parse.quote(n['tag'])}/"))
    for i, p in enumerate(posts):
        prev_p = posts[i + 1] if i + 1 < len(posts) else None
        next_p = posts[i - 1] if i > 0 else None
        write(f"posts/{p['slug']}/index.html", post_page(p, prev_p, next_p))
    write("learn/index.html", learn_page(posts))
    write("timeline/index.html", timeline_page(posts))
    write("about/index.html", about_page())
    write("feed.xml", feed_xml(posts))
    write("sitemap.xml", sitemap_xml(posts))
    ads = CFG["monetization"].get("adsense_client")
    if ads:
        write("ads.txt", f"google.com, {ads.replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n")
    fin = finance(posts)
    if CFG.get("publish_dashboard"):
        write("dashboard/index.html", dashboard_page(fin))
    write_report(posts, fin)
    print(f"Built [{SITE}] {len(posts)} posts -> {OUT}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=SITES + ("all",), default="all")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    sites = SITES if a.site == "all" else (a.site,)
    rc = 0
    for site in sites:
        configure(site)
        rc |= build(a.check)
    if not a.check and not rc:
        (OUT_ROOT / ".nojekyll").write_text("", encoding="utf-8")
        (OUT_ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
