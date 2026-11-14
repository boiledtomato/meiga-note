"""
記事ページの読みやすさ・使いやすさを高める仕組み（build_site.py から使う）。
どれも JavaScript がなくても記事は普通に読めるように作り、JS は「あると便利」な部分だけを担う。

  - 目次      : h2 から自動生成。PC では本文の横に追従、スマホでは折りたたみ
  - チェックリスト: 本文の「- [ ] 〜」をチェックボックスに。状態はブラウザに保存、チケット用にコピー可
  - 用語ツールチップ: data/glossary.json の用語を、記事内の最初の1回だけ説明付きにする
  - マイ環境  : （Zscaler ブログ）クラウド・OS・使っている機能を登録すると、
               data-env の付いた行・項目が「関係あり」で強調され、関係あるものだけ表示もできる
  - 画像ビューア・見どころマーカー:（美術ブログ）作品画像を拡大表示し、本文の見どころと位置を結ぶ
"""

from __future__ import annotations

import html as _html
import json
import re

# ------------------------------------------------------------------ HTML の後処理

_SKIP_TAGS = {"a", "code", "pre", "h1", "h2", "h3", "h4", "svg", "script", "style", "figcaption", "th", "summary", "button", "label"}


def build_toc(body_html: str) -> str:
    items = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body_html, re.S)
    if len(items) < 3:
        return ""
    lis = "".join(f'<li><a href="#{i}">{re.sub(r"<[^>]+>", "", t)}</a></li>' for i, t in items)
    return (f'<nav class="toc" aria-label="目次"><details open><summary>目次</summary>'
            f'<ol>{lis}</ol></details></nav>')


def tasks(body_html: str) -> str:
    """「- [ ] 〜」「- [x] 〜」で始まるリスト項目をチェックボックスにする。"""
    def li(m: re.Match) -> str:
        checked = " checked" if m.group(1).lower() == "x" else ""
        return f'<li class="task"><label><input type="checkbox"{checked}> <span>{m.group(2)}</span></label></li>'
    out = re.sub(r"<li>\s*\[([ xX])\]\s*(.*?)</li>", li, body_html, flags=re.S)
    # チェックボックスを含む ul に印を付ける
    return re.sub(r"<ul>(\s*<li class=\"task\">)", r'<ul class="tasks">\1', out)


def glossary(body_html: str, terms: list[dict], self_slug: str = "") -> str:
    """用語集の用語を、本文の最初の出現1回だけツールチップ付きにする（見出し・リンク・図などは対象外）。"""
    if not terms:
        return body_html
    pending = []
    for t in terms:
        names = [t["term"]] + list(t.get("aliases", []))
        pending.append((t, sorted(names, key=len, reverse=True)))
    parts = re.split(r"(<[^>]+>)", body_html)
    stack: list[str] = []
    done: set[str] = set()
    for i, part in enumerate(parts):
        if part.startswith("<"):
            m = re.match(r"<(/?)([a-zA-Z0-9]+)", part)
            if m and not part.endswith("/>"):
                tag = m.group(2).lower()
                if m.group(1):
                    while stack and stack[-1] != tag:
                        stack.pop()
                    if stack:
                        stack.pop()
                elif tag not in ("br", "img", "input", "hr", "meta", "link", "circle", "rect", "line", "path"):
                    stack.append(tag)
            continue
        if not part.strip() or any(s in _SKIP_TAGS for s in stack):
            continue
        # この文字列の中で、まだ使っていない用語の最初の出現を探し、重ならないものだけ置き換える
        found = []
        for t, names in pending:
            if t["term"] in done:
                continue
            best = None
            for n in names:
                idx = part.find(n)
                if idx >= 0 and (best is None or idx < best[0]):
                    best = (idx, n)
            if best:
                found.append((best[0], best[1], t))
        found.sort(key=lambda x: (x[0], -len(x[1])))
        out, pos = [], 0
        for idx, n, t in found:
            if idx < pos or t["term"] in done:
                continue
            link = ""
            if t.get("link") and t["link"] != self_slug:
                link = f' data-link="{_html.escape(t["link"])}"'
            out.append(part[pos:idx])
            out.append(f'<span class="gl" tabindex="0" role="button" aria-label="{_html.escape(n)}：{_html.escape(t["def"])}"'
                       f' data-def="{_html.escape(t["def"])}"{link}>{n}</span>')
            pos = idx + len(n)
            done.add(t["term"])
        out.append(part[pos:])
        part = "".join(out)
        parts[i] = part
    return "".join(parts)


def enhance(body_html: str, *, terms: list[dict] | None = None, slug: str = "") -> tuple[str, str]:
    body_html = tasks(body_html)
    body_html = glossary(body_html, terms or [], slug)
    return body_html, build_toc(body_html)


# ------------------------------------------------------------------ CSS

CSS = """
.progress{position:fixed;top:0;left:0;height:3px;width:0;background:var(--accent);z-index:30;transition:width .1s linear}
.toc details{border:1px solid var(--line);border-radius:8px;background:var(--card);padding:8px 14px;margin:18px 0}
.toc summary{font-weight:700;font-size:.92rem}.toc ol{margin:.4em 0 .2em;padding-left:1.3em;font-size:.88rem;line-height:1.7}
.toc a{text-decoration:none;color:var(--fg)}.toc a.on{color:var(--accent);font-weight:700}
@media (min-width:1200px){.toc{position:fixed;top:96px;left:calc(50% + 410px);width:220px;max-height:calc(100vh - 140px);overflow:auto}
.toc details{margin:0}}
ul.tasks{list-style:none;padding-left:0}li.task{margin:.35em 0}li.task label{display:flex;gap:.55em;align-items:flex-start;cursor:pointer}
li.task input{margin-top:.45em;width:1.05em;height:1.05em;accent-color:var(--accent);flex:none}li.task input:checked+span{color:var(--muted);text-decoration:line-through}
.taskbar{display:flex;gap:10px;align-items:center;font-size:.85rem;color:var(--muted);margin:-.2em 0 1.2em}
.btn{font:inherit;font-size:.82rem;border:1px solid var(--accent);color:var(--accent);background:var(--card);border-radius:99px;padding:3px 12px;cursor:pointer}
.btn:hover{background:var(--accent);color:var(--card)}.btn[aria-pressed=true]{background:var(--accent);color:var(--card)}
.gl{border-bottom:1.5px dotted var(--accent);cursor:help;position:relative;outline:none}
.gltip{position:absolute;z-index:40;max-width:320px;background:var(--fg);color:var(--bg);font-size:.82rem;line-height:1.6;padding:10px 12px;border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.18)}
.gltip a{color:var(--bg);font-weight:700}
.envbar{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:8px;padding:10px 14px;margin:18px 0;font-size:.9rem}
.envbar .who{flex:1 1 220px}.envbar.hit{border-left-color:var(--warn)}
tr.env-hit td:first-child,li.env-hit{box-shadow:inset 4px 0 0 var(--accent)}tr.env-hit{background:color-mix(in srgb,var(--accent) 8%,transparent)}
li.env-hit{padding-left:8px}.env-badge{display:inline-block;font-size:.7rem;font-weight:700;color:var(--card);background:var(--accent);border-radius:99px;padding:0 7px;margin-right:6px;vertical-align:1px}
.env-miss{opacity:.45}.only-mine .env-miss{display:none}
.envdlg{border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--fg);max-width:560px;width:calc(100% - 32px);padding:18px 20px}
.envdlg::backdrop{background:rgba(0,0,0,.35)}.envdlg h2{margin:0 0 .3em;border:0;padding:0;font-size:1.1rem}
.envdlg fieldset{border:1px solid var(--line);border-radius:8px;margin:12px 0;padding:8px 12px}.envdlg legend{font-weight:700;font-size:.88rem;padding:0 4px}
.envdlg label{display:inline-flex;gap:5px;align-items:center;margin:3px 14px 3px 0;font-size:.88rem}.envdlg .row{display:flex;gap:10px;justify-content:flex-end;margin-top:10px}
.envbtn{margin-left:auto;font:inherit;font-size:.82rem;border:1px solid var(--accent);color:var(--accent);background:transparent;border-radius:99px;padding:2px 12px;cursor:pointer}
.zoomable{cursor:zoom-in}.lb{position:fixed;inset:0;z-index:50;background:rgba(10,10,10,.92);display:flex;flex-direction:column}
.lb .bar{display:flex;gap:10px;align-items:center;color:#eee;padding:10px 14px;font-size:.85rem}.lb .bar .t{flex:1}
.lb .bar button{font:inherit;font-size:.85rem;background:#333;color:#fff;border:1px solid #555;border-radius:6px;padding:4px 12px;cursor:pointer}
.lb .stage{flex:1;overflow:hidden;position:relative;touch-action:none;cursor:grab}.lb img{position:absolute;top:0;left:0;transform-origin:0 0;max-width:none;user-select:none}
.hot{position:relative;display:block}.hot img{display:block;width:100%}.hot .pt{position:absolute;transform:translate(-50%,-50%);width:28px;height:28px;border-radius:50%;
background:var(--accent);color:var(--card);font-weight:700;font-size:.85rem;border:2px solid var(--card);box-shadow:0 2px 6px rgba(0,0,0,.35);cursor:pointer;display:flex;align-items:center;justify-content:center;text-decoration:none}
.hot .pt.on{outline:3px solid var(--warn)}h3.flash{animation:flash 1.6s ease}
@keyframes flash{0%{background:color-mix(in srgb,var(--accent) 25%,transparent)}100%{background:transparent}}
.tl{position:relative;margin:24px 0;padding-left:28px;border-left:3px solid var(--line)}.tl li{list-style:none;margin:0 0 22px;position:relative}
.tl li::before{content:"";position:absolute;left:-37px;top:.45em;width:13px;height:13px;border-radius:50%;background:var(--accent);border:3px solid var(--bg)}
.tl .era{font-weight:700;color:var(--accent);font-size:.92rem}.tl .gap{color:var(--muted);font-size:.8rem;margin:-10px 0 18px}
.tl a{font-weight:700;text-decoration:none;color:var(--fg)}.tl p{margin:.2em 0 0;color:var(--muted);font-size:.88rem}

/* ---- 動き：一覧・ヒーロー・図・見出し ---- */
.wrap.wide{max-width:1100px}
.post-hero{margin:0 -16px 8px;padding:22px 16px 18px;background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 14%,var(--card)),var(--card) 70%);border-bottom:1px solid var(--line);border-radius:0 0 14px 14px}
.post-hero .kind{display:inline-block;font-size:.75rem;font-weight:700;letter-spacing:.04em;color:var(--card);background:var(--accent);border-radius:4px;padding:1px 8px;margin-right:8px}
.post-hero h1{margin:.35em 0 .3em}.post-hero .rt{color:var(--muted);font-size:.82rem}
.minibar{position:fixed;top:0;left:0;right:0;z-index:25;background:color-mix(in srgb,var(--card) 92%,transparent);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);
transform:translateY(-100%);transition:transform .25s ease;font-size:.86rem}.minibar.on{transform:none}
.minibar .wrap{display:flex;gap:12px;align-items:center;padding-top:8px;padding-bottom:8px}.minibar b{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rv{opacity:0;transform:translateY(14px);transition:opacity .6s ease,transform .6s ease}.rv.in{opacity:1;transform:none}
.fig.anim svg>*{opacity:0;transform:translateY(6px);transform-box:fill-box;transition:opacity .45s ease var(--d,0s),transform .45s ease var(--d,0s)}
.fig.anim.in svg>*{opacity:1;transform:none}.fig.anim svg>defs{opacity:1}
.fig.anim .la.draw{stroke-dasharray:1;stroke-dashoffset:1;transition:stroke-dashoffset .8s ease var(--d,0s),opacity .3s ease var(--d,0s)}.fig.anim.in .la.draw{stroke-dashoffset:0}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:26px 0 14px}
.fchip{font:inherit;font-size:.85rem;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:99px;padding:4px 14px;cursor:pointer;transition:all .2s}
.fchip span{color:var(--muted);font-size:.78rem;margin-left:4px}.fchip.on{background:var(--accent);border-color:var(--accent);color:var(--card)}.fchip.on span{color:var(--card)}
.fsearch{flex:1 1 180px;min-width:150px;font:inherit;font-size:.88rem;padding:6px 12px;border:1px solid var(--line);border-radius:99px;background:var(--card);color:var(--fg)}
.cards{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.card{transition:opacity .3s ease,transform .3s ease}.card.hide{display:none}.card.pop{animation:pop .35s ease}
@keyframes pop{from{opacity:0;transform:translateY(8px) scale(.98)}to{opacity:1;transform:none}}
.card a{display:flex;flex-direction:column;height:100%;text-decoration:none;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;
border-top:4px solid var(--c,var(--accent));transition:transform .2s ease,box-shadow .2s ease}
.card a:hover,.card a:focus-visible{transform:translateY(-4px);box-shadow:0 10px 24px rgba(0,0,0,.10)}
.card .thumb{width:100%;aspect-ratio:4/3;object-fit:cover;background:var(--code);transition:transform .5s ease}.card a:hover .thumb{transform:scale(1.05)}
.card .in{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;flex:1}.card .k{font-size:.72rem;font-weight:700;color:var(--c,var(--accent))}
.card h3{margin:0;font-size:.98rem;line-height:1.5}.card p{margin:0;font-size:.82rem;color:var(--muted);line-height:1.6;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card .m{margin-top:auto;font-size:.75rem;color:var(--muted)}.noresult{color:var(--muted);text-align:center;padding:30px 0}
.board{margin:26px 0 6px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.board h2{margin:0;border:0;padding:0;font-size:1.1rem}.board .sub{color:var(--muted);font-size:.82rem;margin:2px 0 12px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}@media (max-width:640px){.tiles{grid-template-columns:repeat(2,1fr)}}
.tile{display:block;text-decoration:none;color:var(--fg);border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--bg);transition:transform .2s,box-shadow .2s}
a.tile:hover{transform:translateY(-3px);box-shadow:0 8px 18px rgba(0,0,0,.08)}.tile .p{font-weight:700;font-size:.85rem}.tile b{display:block;font-size:2rem;line-height:1.2;color:var(--accent)}
.tile .u{font-size:.75rem;color:var(--muted)}.tile .st{display:inline-block;margin-top:6px;font-size:.72rem;border-radius:99px;padding:1px 8px;background:var(--code)}
.tile.done .st{background:var(--accent);color:var(--card)}.tile.none{opacity:.6}.tile.none b{color:var(--muted)}
.mine{margin:12px 0 0;padding:10px 12px;border-radius:10px;background:color-mix(in srgb,var(--accent) 10%,transparent);font-size:.88rem;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.mine b{font-size:1.3rem;color:var(--accent)}.incs{margin-top:12px}.incs h3{font-size:.9rem;margin:0 0 6px}.incs ul{list-style:none;padding:0;margin:0}
.incs li{display:flex;gap:8px;align-items:baseline;padding:6px 0;border-top:1px dashed var(--line);font-size:.86rem}.incs li a{color:var(--fg);text-decoration:none;flex:1}
.incs .cl{font-size:.7rem;border:1px solid var(--line);border-radius:4px;padding:0 6px;color:var(--muted);white-space:nowrap}.incs li.mine-hit .cl{border-color:var(--warn);color:var(--warn);font-weight:700}
.hero{position:relative;display:block;margin:20px 0 6px;border-radius:14px;overflow:hidden;aspect-ratio:16/8;background:#111;color:#fff;text-decoration:none}
.hero img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center 30%;animation:kb 18s ease-in-out infinite alternate}
@keyframes kb{from{transform:scale(1.02)}to{transform:scale(1.12) translate(-2%,-2%)}}
.hero .cap{position:absolute;left:0;right:0;bottom:0;padding:40px 18px 16px;background:linear-gradient(transparent,rgba(0,0,0,.78))}
.hero .cap small{opacity:.85;font-size:.78rem}.hero .cap b{display:block;font-size:1.25rem;line-height:1.45;margin-top:4px}
@media (max-width:640px){.hero{aspect-ratio:4/3}.hero .cap b{font-size:1.05rem}}
.strip{display:flex;gap:0;overflow-x:auto;scroll-snap-type:x mandatory;padding:14px 4px 6px;margin:8px 0 0;position:relative}
.strip a{flex:0 0 auto;scroll-snap-align:start;text-decoration:none;color:var(--fg);min-width:150px;max-width:170px;padding:24px 12px 4px;position:relative;font-size:.8rem;line-height:1.5;border-top:2px solid var(--line)}
.strip a::before{content:"";position:absolute;top:-8px;left:12px;width:12px;height:12px;border-radius:50%;background:var(--accent);border:2px solid var(--bg);transition:transform .2s}
.strip a:hover::before{transform:scale(1.5)}.strip .y{display:block;font-weight:700;color:var(--accent);font-size:.78rem}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}.rv,.fig.anim svg>*{opacity:1!important;transform:none!important}}
"""


# ------------------------------------------------------------------ JavaScript

def js(env_vocab: dict | None = None) -> str:
    return "const ENV_VOCAB=" + json.dumps(env_vocab or {}, ensure_ascii=False) + ";\n" + _JS


_JS = r"""
(() => {
  const S = {
    get(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } },
  };
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const art = $("article");

  /* 読み進み具合のバー */
  if (art) {
    const bar = document.createElement("div"); bar.className = "progress"; document.body.prepend(bar);
    const upd = () => { const r = art.getBoundingClientRect(); const h = r.height - innerHeight;
      bar.style.width = Math.max(0, Math.min(100, (-r.top / (h > 0 ? h : 1)) * 100)) + "%"; };
    addEventListener("scroll", upd, { passive: true }); upd();
  }

  /* 目次：いま読んでいる見出しを強調。狭い画面では最初は閉じておく */
  const toc = $(".toc");
  if (toc) {
    if (innerWidth < 1200) $("details", toc).open = false;
    const links = new Map($$("a", toc).map((a) => [decodeURIComponent(a.hash.slice(1)), a]));
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver((es) => es.forEach((en) => {
        if (!en.isIntersecting) return; $$("a.on", toc).forEach((a) => a.classList.remove("on"));
        const a = links.get(en.target.id); if (a) a.classList.add("on");
      }), { rootMargin: "0px 0px -75% 0px" });
      $$("article h2[id]").forEach((h) => io.observe(h));
    }
    toc.addEventListener("click", (ev) => { if (ev.target.closest("a") && innerWidth < 1200) $("details", toc).open = false; });
  }

  /* チェックリスト：状態を保存し、チケット用にコピーできる */
  $$("ul.tasks").forEach((ul, n) => {
    const key = "tasks:" + location.pathname + ":" + n, st = S.get(key) || {};
    const boxes = $$("input[type=checkbox]", ul);
    const bar = document.createElement("div"); bar.className = "taskbar";
    bar.innerHTML = '<span class="cnt"></span><button type="button" class="btn">チケット用にコピー</button>';
    ul.after(bar);
    const cnt = () => { $(".cnt", bar).textContent = boxes.filter((b) => b.checked).length + " / " + boxes.length + " 完了"; };
    boxes.forEach((b, i) => { if (i in st) b.checked = st[i]; b.addEventListener("change", () => { st[i] = b.checked; S.set(key, st); cnt(); }); });
    cnt();
    $("button", bar).addEventListener("click", async (ev) => {
      const lines = $$("li", ul).map((li) => "- [" + ($("input", li).checked ? "x" : " ") + "] " + li.textContent.trim().replace(/\s+/g, " "));
      const txt = ($("h1") || {}).textContent + "\n" + location.href + "\n\n" + lines.join("\n");
      const btn = ev.currentTarget, old = btn.textContent;
      try { await navigator.clipboard.writeText(txt); btn.textContent = "コピーしました"; }
      catch (e) { const ta = document.createElement("textarea"); ta.value = txt; document.body.append(ta); ta.select();
        try { document.execCommand("copy"); btn.textContent = "コピーしました"; } catch (e2) { btn.textContent = "コピーできませんでした"; } ta.remove(); }
      setTimeout(() => (btn.textContent = old), 1800);
    });
  });

  /* 用語ツールチップ（マウスでもタップでもキーボードでも開ける） */
  let tip = null;
  const closeTip = () => { if (tip) { tip.remove(); tip = null; } };
  const openTip = (el) => {
    closeTip(); tip = document.createElement("div"); tip.className = "gltip"; tip.setAttribute("role", "tooltip");
    tip.textContent = el.dataset.def;
    if (el.dataset.link) { const a = document.createElement("a"); a.href = el.dataset.link; a.textContent = " → 解説記事"; tip.append(a); }
    document.body.append(tip);
    const r = el.getBoundingClientRect(), w = Math.min(320, innerWidth - 24);
    tip.style.maxWidth = w + "px";
    const left = Math.max(12, Math.min(scrollX + r.left, scrollX + innerWidth - w - 12));
    tip.style.left = left + "px"; tip.style.top = scrollY + r.bottom + 8 + "px";
  };
  $$(".gl").forEach((el) => {
    el.addEventListener("click", (ev) => { ev.stopPropagation(); tip ? closeTip() : openTip(el); });
    el.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openTip(el); } if (ev.key === "Escape") closeTip(); });
    el.addEventListener("mouseenter", () => matchMedia("(hover:hover)").matches && openTip(el));
    el.addEventListener("mouseleave", () => matchMedia("(hover:hover)").matches && closeTip());
  });
  document.addEventListener("click", (ev) => { if (tip && !ev.target.closest(".gltip")) closeTip(); });

  /* マイ環境（Zscaler ブログ） */
  const groups = ENV_VOCAB.groups || [];
  if (groups.length) {
    const KEY = "my-env";
    let env = S.get(KEY) || {};
    const label = (id) => { for (const g of groups) for (const o of g.options) if (o.id === id) return o.label; return id; };
    const btn = document.createElement("button"); btn.type = "button"; btn.className = "envbtn";
    const nav = $("header.site nav"); if (nav) nav.append(btn);
    const sumText = () => { const all = groups.flatMap((g) => env[g.id] || []); return all.length ? "マイ環境：" + all.slice(0, 3).map(label).join("・") + (all.length > 3 ? " ほか" : "") : "マイ環境を設定"; };
    const dlg = document.createElement("dialog"); dlg.className = "envdlg";
    dlg.innerHTML = '<h2>マイ環境</h2><p class="meta">あなたの組織で使っているものを選ぶと、アップデート記事や障害記事で「関係ある項目」が強調されます。設定はこのブラウザの中だけに保存され、外部には送られません。</p>' +
      groups.map((g) => '<fieldset data-g="' + g.id + '"><legend>' + g.label + "</legend>" +
        g.options.map((o) => '<label><input type="checkbox" value="' + o.id + '"> ' + o.label + "</label>").join("") + "</fieldset>").join("") +
      '<div class="row"><button type="button" class="btn" data-a="clear">すべて外す</button><button type="button" class="btn" data-a="save" aria-pressed="true">保存</button></div>';
    document.body.append(dlg);
    const fill = () => $$("fieldset", dlg).forEach((fs) => $$("input", fs).forEach((i) => (i.checked = (env[fs.dataset.g] || []).includes(i.value))));
    btn.addEventListener("click", () => { fill(); dlg.showModal ? dlg.showModal() : dlg.setAttribute("open", ""); });
    dlg.addEventListener("click", (ev) => {
      const a = ev.target.dataset.a;
      if (a === "clear") $$("input", dlg).forEach((i) => (i.checked = false));
      if (a === "save") { env = {}; $$("fieldset", dlg).forEach((fs) => (env[fs.dataset.g] = $$("input:checked", fs).map((i) => i.value)));
        if (!S.set(KEY, env)) alert("このブラウザでは設定を保存できませんでした（このページを開いている間だけ有効です）。");
        dlg.close ? dlg.close() : dlg.removeAttribute("open"); apply(); }
      if (ev.target === dlg) dlg.close();
    });
    const groupOf = {}; groups.forEach((g) => g.options.forEach((o) => (groupOf[o.id] = g.id)));
    const relevant = (tags) => {   // 各グループで「タグがあれば、自分の環境のどれかと一致」していれば関係あり
      if (tags.includes("all")) return true;
      const by = {}; tags.forEach((t) => { const g = groupOf[t]; if (g) (by[g] = by[g] || []).push(t); });
      return Object.entries(by).every(([g, ts]) => (env[g] || []).length === 0 ? true : ts.some((t) => env[g].includes(t)));
    };
    const configured = () => groups.some((g) => (env[g.id] || []).length);
    const marks = $$("[data-env]").filter((m) => !m.classList.contains("envbar"));
    let bar = null;
    if (marks.length && art) {
      bar = document.createElement("div"); bar.className = "envbar";
      bar.innerHTML = '<span class="who"></span><button type="button" class="btn" data-x="only" aria-pressed="false">関係あるものだけ表示</button><button type="button" class="btn" data-x="set">マイ環境を変更</button>';
      const first = $("article > h2"); first ? first.before(bar) : art.prepend(bar);
      bar.addEventListener("click", (ev) => {
        const x = ev.target.dataset.x;
        if (x === "set") btn.click();
        if (x === "only") { const on = ev.target.getAttribute("aria-pressed") !== "true"; ev.target.setAttribute("aria-pressed", on); art.classList.toggle("only-mine", on); }
      });
    }
    const cloudBar = $(".envbar[data-env]");
    let apply = function () {
      btn.textContent = sumText();
      let hit = 0;
      marks.forEach((m) => {
        const row = m.closest("tr, li") || m; const tags = m.dataset.env.split(/\s+/).filter(Boolean);
        row.classList.remove("env-hit", "env-miss"); $$(".env-badge", row).forEach((b) => b.remove());
        if (!configured()) return;
        if (relevant(tags)) { row.classList.add("env-hit"); hit++; const b = document.createElement("span"); b.className = "env-badge"; b.textContent = "関係あり";
          (row.matches("tr") ? row.cells[0] : row).prepend(b); }
        else row.classList.add("env-miss");
      });
      if (bar) $(".who", bar).textContent = configured() ? "マイ環境に関係する項目：" + hit + " 件（全 " + marks.length + " 件）" : "マイ環境を設定すると、あなたに関係する項目が強調されます。";
      if (cloudBar) {
        const clouds = cloudBar.dataset.env.split(/\s+/), mine = env.cloud || [];
        const t = $(".who", cloudBar);
        if (!mine.length) { t.textContent = "対象クラウド：" + clouds.map(label).join("、") + "（マイ環境でクラウドを登録すると、自社が対象か判定できます）"; cloudBar.classList.remove("hit"); }
        else if (clouds.some((c) => mine.includes(c))) { t.textContent = "⚠ あなたのクラウド（" + mine.filter((c) => clouds.includes(c)).map(label).join("、") + "）が対象の障害です"; cloudBar.classList.add("hit"); }
        else { t.textContent = "あなたのクラウド（" + mine.map(label).join("、") + "）は対象外です。対象：" + clouds.map(label).join("、"); cloudBar.classList.remove("hit"); }
      }
    };
    if (cloudBar) cloudBar.addEventListener("click", (ev) => { if (ev.target.dataset.x === "set") btn.click(); });
    const idx = $("#env-index"), mine = $(".mine");
    const board = () => {
      if (!idx || !mine) return;
      const data = JSON.parse(idx.textContent); let total = 0, hit = 0;
      data.items.forEach((tags) => { total++; if (relevant(tags)) hit++; });
      $(".mtext", mine).innerHTML = configured()
        ? '今週の変更のうち、マイ環境に関係するもの <b data-n>' + hit + "</b> 件（全 " + total + " 件）"
        : "マイ環境（クラウド・OS・使っている機能）を登録すると、今週の変更のうち自社に関係する件数がここに出ます。";
      $$(".incs li").forEach((li) => li.classList.toggle("mine-hit", (li.dataset.clouds || "").split(" ").some((c) => (env.cloud || []).includes(c))));
    };
    if (mine) $("button", mine).addEventListener("click", () => btn.click());
    const apply0 = apply; apply = function () { apply0(); board(); };
    apply();
  }


  const calm = matchMedia("(prefers-reduced-motion:reduce)").matches;
  /* 図：画面に入ったら、要素を順番に表示し、強調の矢印を描く（因果や時系列を順に追えるように） */
  if (!calm && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => es.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } }), { threshold: 0.25 });
    $$(".fig").forEach((f) => {
      const kids = [...(f.querySelector("svg") || { children: [] }).children].filter((k) => k.tagName.toLowerCase() !== "defs");
      const step = Math.min(45, 1100 / Math.max(1, kids.length));
      kids.forEach((k, i) => { k.style.setProperty("--d", (i * step) / 1000 + "s"); if (k.matches(".la") && !k.getAttribute("stroke-dasharray")) { k.setAttribute("pathLength", "1"); k.classList.add("draw"); } });
      f.classList.add("anim"); io.observe(f);
    });
    const ro = new IntersectionObserver((es) => es.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("in"); ro.unobserve(en.target); } }), { rootMargin: "0px 0px -8% 0px" });
    $$("article .box, article table, ul.tasks, article figure:not(.fig), .board, .hero").forEach((el) => {
      if (el.getBoundingClientRect().top > innerHeight) { el.classList.add("rv"); ro.observe(el); }
    });
  }
  /* 数字のカウントアップ */
  $$("[data-count]").forEach((el) => {
    const to = +el.dataset.count; if (calm || !to) { el.textContent = to; return; }
    const t0 = performance.now(), dur = 900; const tick = (t) => { const k = Math.min(1, (t - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(tick); };
    el.textContent = 0; requestAnimationFrame(tick);
  });
  /* 記事を読み進めたら、上にタイトルの細いバーを出す */
  const h1 = $("article h1");
  if (h1) {
    const mb = document.createElement("div"); mb.className = "minibar"; mb.innerHTML = '<div class="wrap"><b></b><a href="#top">↑ 先頭へ</a></div>';
    $("b", mb).textContent = h1.textContent; document.body.append(mb);
    $("a", mb).addEventListener("click", (ev) => { ev.preventDefault(); scrollTo({ top: 0, behavior: calm ? "auto" : "smooth" }); });
    if ("IntersectionObserver" in window) new IntersectionObserver(([en]) => mb.classList.toggle("on", !en.isIntersecting && en.boundingClientRect.top < 0)).observe(h1);
  }
  /* 記事一覧：種類のフィルタと検索 */
  const cards = $$(".cards .card");
  if (cards.length) {
    let cat = "all", q = "";
    const nores = $(".noresult");
    const run = () => {
      let n = 0;
      cards.forEach((c) => { const ok = (cat === "all" || c.dataset.cat === cat) && (!q || c.dataset.text.includes(q));
        const was = !c.classList.contains("hide"); c.classList.toggle("hide", !ok); if (ok) { n++; if (!was && !calm) { c.classList.remove("pop"); void c.offsetWidth; c.classList.add("pop"); } } });
      if (nores) nores.hidden = n > 0;
    };
    $$(".fchip").forEach((b) => b.addEventListener("click", () => { $$(".fchip").forEach((x) => x.classList.toggle("on", x === b)); cat = b.dataset.f; run(); }));
    const s = $(".fsearch"); if (s) s.addEventListener("input", () => { q = s.value.trim().toLowerCase(); run(); });
  }

  /* 画像ビューア（美術ブログ）：クリックで高解像度画像を拡大・移動 */
  $$("img[data-full]").forEach((img) => {
    img.classList.add("zoomable"); img.tabIndex = 0; img.setAttribute("role", "button");
    img.setAttribute("aria-label", "画像を拡大して見る");
    const open = () => {
      const lb = document.createElement("div"); lb.className = "lb"; lb.setAttribute("role", "dialog"); lb.setAttribute("aria-label", "画像の拡大表示");
      lb.innerHTML = '<div class="bar"><span class="t">高解像度の画像を読み込み中…（ドラッグで移動、ホイール・ボタンで拡大縮小）</span><button data-z="out">－</button><button data-z="in">＋</button><button data-z="fit">全体</button><button data-z="close">閉じる</button></div><div class="stage"></div>';
      const stage = $(".stage", lb), big = new Image(); big.alt = img.alt; big.draggable = false; stage.append(big); document.body.append(lb);
      document.documentElement.style.overflow = "hidden";
      let s = 1, x = 0, y = 0;
      const draw = () => (big.style.transform = "translate(" + x + "px," + y + "px) scale(" + s + ")");
      const fit = () => { const W = stage.clientWidth, H = stage.clientHeight; s = Math.min(W / big.naturalWidth, H / big.naturalHeight); x = (W - big.naturalWidth * s) / 2; y = (H - big.naturalHeight * s) / 2; draw(); };
      const zoom = (f, cx = stage.clientWidth / 2, cy = stage.clientHeight / 2) => { const ns = Math.max(0.05, Math.min(8, s * f)); x = cx - (cx - x) * (ns / s); y = cy - (cy - y) * (ns / s); s = ns; draw(); };
      big.onload = () => { $(".t", lb).textContent = img.alt + "（ドラッグで移動、ホイール・ボタンで拡大縮小）"; fit(); };
      big.onerror = () => { big.src = img.src; };
      big.src = img.dataset.full;
      const close = () => { lb.remove(); document.documentElement.style.overflow = ""; removeEventListener("keydown", key); img.focus(); };
      const key = (ev) => { if (ev.key === "Escape") close(); if (ev.key === "+") zoom(1.25); if (ev.key === "-") zoom(0.8); };
      addEventListener("keydown", key);
      lb.addEventListener("click", (ev) => { const z = ev.target.dataset.z; if (z === "in") zoom(1.4); if (z === "out") zoom(1 / 1.4); if (z === "fit") fit(); if (z === "close") close(); });
      stage.addEventListener("wheel", (ev) => { ev.preventDefault(); const r = stage.getBoundingClientRect(); zoom(ev.deltaY < 0 ? 1.15 : 1 / 1.15, ev.clientX - r.left, ev.clientY - r.top); }, { passive: false });
      const pts = new Map(); let last = null;
      stage.addEventListener("pointerdown", (ev) => { stage.setPointerCapture(ev.pointerId); pts.set(ev.pointerId, [ev.clientX, ev.clientY]); });
      stage.addEventListener("pointermove", (ev) => {
        if (!pts.has(ev.pointerId)) return; const prev = pts.get(ev.pointerId); pts.set(ev.pointerId, [ev.clientX, ev.clientY]);
        if (pts.size === 1) { x += ev.clientX - prev[0]; y += ev.clientY - prev[1]; draw(); }
        else if (pts.size === 2) { const [a, b] = [...pts.values()]; const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
          if (last) { const r = stage.getBoundingClientRect(); zoom(d / last, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top); } last = d; }
      });
      const up = (ev) => { pts.delete(ev.pointerId); if (pts.size < 2) last = null; };
      stage.addEventListener("pointerup", up); stage.addEventListener("pointercancel", up);
      $("[data-z=close]", lb).focus();
    };
    img.addEventListener("click", open);
    img.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(); } });
  });

  /* 見どころマーカー：画像の番号を押すと本文の見どころへ、本文の見出しから画像の位置へ */
  $$(".hot .pt").forEach((pt) => {
    pt.addEventListener("click", (ev) => {
      ev.preventDefault(); const h = document.getElementById(pt.getAttribute("href").slice(1)); if (!h) return;
      h.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion:reduce)").matches ? "auto" : "smooth", block: "start" });
      h.classList.remove("flash"); void h.offsetWidth; h.classList.add("flash");
    });
  });
  $$("[data-point]").forEach((h) => {
    const pt = $('.hot .pt[href="#' + h.id + '"]'); if (!pt) return;
    const b = document.createElement("button"); b.type = "button"; b.className = "btn"; b.style.marginLeft = "8px"; b.textContent = "画像で見る";
    b.addEventListener("click", () => { $(".hot").scrollIntoView({ behavior: "smooth", block: "center" }); $$(".hot .pt").forEach((p) => p.classList.toggle("on", p === pt)); setTimeout(() => pt.classList.remove("on"), 2600); });
    h.append(b);
  });
})();
"""
