#!/usr/bin/env python3
"""
美術ブログの記事の「材料」を集めるスクリプト。

  python3 scripts/blog_sources.py today                    # 今日の記事タイプを決め、材料一式を出力
  python3 scripts/blog_sources.py today --date 2026-11-10
  python3 scripts/blog_sources.py artwork                  # Met 美術館のパブリックドメイン作品を1点
  python3 scripts/blog_sources.py topic                    # 未執筆のテーマを1つ
  python3 scripts/blog_sources.py used                     # 既に使った topic_id 一覧

出力は Markdown のブリーフ（人間/Claude がそのまま読める形式）。外部ライブラリは PyYAML のみ使用。
"""

from __future__ import annotations

import argparse
import json
import random
import re
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = "art"


def site_dir(site: str) -> Path:
    return ROOT


def site_config(site: str) -> dict:
    return json.loads((site_dir(site) / "config.json").read_text(encoding="utf-8"))


def site_topics(site: str) -> list[dict]:
    return json.loads((site_dir(site) / "data" / "topics.json").read_text(encoding="utf-8"))

MET_API = "https://collectionapi.metmuseum.org/public/collection/v1"
MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1.1/search"
ART_QUERIES = [
    "painting", "portrait", "landscape", "sculpture", "ukiyo-e", "woodblock print",
    "Egypt", "Greek", "Roman", "Renaissance", "Impressionism", "still life",
    "illuminated manuscript", "screen", "ceramic", "Hokusai", "Hiroshige",
    "Rembrandt", "Vermeer", "Monet", "Degas", "icon", "armor", "tapestry",
]


# ------------------------------------------------------------------ helpers

def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    for ca in ("/root/.ccr/ca-bundle.crt",):
        if Path(ca).exists():
            ctx.load_verify_locations(ca)
    return ctx


def http_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "personal-blog-builder/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        return json.loads(r.read().decode("utf-8"))


def read_front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def used_topic_ids(site: str) -> set[str]:
    ids = set()
    for p in (site_dir(site) / "content" / "posts").glob("*.md"):
        tid = read_front_matter(p).get("topic_id")
        if tid:
            ids.add(str(tid))
    return ids


# ------------------------------------------------------------------ art

def pick_artwork(used: set[str], tries: int = 12) -> dict:
    for _ in range(tries):
        q = random.choice(ART_QUERIES)
        base = {"q": q, "isHighlight": "true", "hasImages": "true"}
        first = http_json(f"{MET_SEARCH}?{urllib.parse.urlencode({**base, 'limit': 1})}")
        total = int(first.get("total") or 0)
        if not total:
            continue
        offset = random.randrange(0, min(total, 1000))
        res = http_json(f"{MET_SEARCH}?{urllib.parse.urlencode({**base, 'limit': 20, 'offset': offset})}")
        for oid in random.sample(res.get("objectIDs") or [], k=len(res.get("objectIDs") or [])):
            if f"met-{oid}" in used:
                continue
            obj = http_json(f"{MET_API}/objects/{oid}")
            if obj.get("isPublicDomain") and obj.get("primaryImage"):
                return obj
    raise RuntimeError("条件に合う作品が見つかりませんでした（再実行してください）")


def artwork_brief(obj: dict) -> str:
    fields = [
        ("objectID", "ID"), ("title", "作品名"), ("artistDisplayName", "作者"),
        ("artistDisplayBio", "作者情報"), ("objectDate", "制作年"), ("culture", "文化圏"),
        ("period", "時代"), ("medium", "技法・素材"), ("dimensions", "寸法"),
        ("classification", "分類"), ("department", "部門"), ("creditLine", "クレジット"),
        ("objectURL", "所蔵館ページ"), ("primaryImage", "画像(大)"), ("primaryImageSmall", "画像(小)"),
    ]
    lines = ["## 作品データ（The Met Collection API / Public Domain）\n"]
    for key, label in fields:
        if obj.get(key):
            lines.append(f"- {label}: {obj[key]}")
    tags = [t.get("term") for t in (obj.get("tags") or []) if t.get("term")]
    if tags:
        lines.append(f"- タグ: {', '.join(tags)}")
    lines.append(f"\n推奨フロントマター: topic_id: met-{obj['objectID']} / image: {obj.get('primaryImageSmall') or obj.get('primaryImage')}"
                 f" / image_full: {obj.get('primaryImage')}"
                 " / image_credit: \"The Metropolitan Museum of Art, Public Domain (CC0)\""
                 f" / era: {obj.get('objectBeginDate')}（制作年の数値。紀元前はマイナス）/ era_label / points（見どころ3点の画像上の位置）")
    return "\n".join(lines)


# ------------------------------------------------------------------ topics

def next_topic(site: str, used: set[str]) -> dict | None:
    for t in site_topics(site):
        if t["id"] not in used:
            return t
    return None


def topic_brief(site: str, used: set[str]) -> str:
    t = next_topic(site, used)
    if not t:
        return (f"## テーマ在庫切れ\n\ndata/topics.json に新しいテーマを"
                "5件ほど追加してから（重複しないこと）、その1件目で書くこと。")
    return f"## 今回のテーマ\n\n- topic_id: {t['id']}\n- 仮タイトル: {t['title']}"


# ------------------------------------------------------------------ main

def _head(site: str, d: date, kind: str, n: int | None = None) -> list[str]:
    title = f"# 記事ブリーフ（{site} ブログ）{d.isoformat()}" + (f" — 記事{n}" if n else "")
    return [title, "", f"- 記事タイプ: **{kind}**",
            f"- 保存先: content/posts/{d.isoformat()}-<topic_id>.md",
            "- 執筆ルール: WRITING_RULES.md と WRITING_GUIDE.md を必ず読むこと", ""]


def build_today(site: str, d: date) -> str:
    kind = site_config(site)["schedule"].get(str(d.weekday()))
    if not kind:
        return f"# {site} ブログ {d.isoformat()}\n\n今日は休みの日です。何もしないで終了してください。"
    used = used_topic_ids(site)
    head = _head(site, d, kind)
    if kind == "art-topic":
        body = topic_brief(site, used)
    elif kind == "art-artwork":
        body = artwork_brief(pick_artwork(used))
    else:
        raise SystemExit(f"unknown kind: {kind}")
    return "\n".join(head) + "\n" + body


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=SITE, help="互換用（無視される）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("today"); t.add_argument("--date")
    sub.add_parser("artwork")
    sub.add_parser("topic")
    sub.add_parser("used")
    a = ap.parse_args()

    today = datetime.now(timezone(timedelta(hours=9))).date()  # 日本時間
    if a.cmd == "today":
        print(build_today(SITE, date.fromisoformat(a.date) if a.date else today))
    elif a.cmd == "artwork":
        print(artwork_brief(pick_artwork(used_topic_ids(SITE))))
    elif a.cmd == "topic":
        print(topic_brief(SITE, used_topic_ids(SITE)))
    elif a.cmd == "used":
        print("\n".join(sorted(used_topic_ids(SITE))))


if __name__ == "__main__":
    sys.exit(main())
