#!/usr/bin/env python3
"""Duluan: tarik RSS media nasional + Google Trends, deteksi topik 'mulai naik',
lalu tulis docs/index.html. Hanya pakai library bawaan Python (tanpa pip install).

Pakai:
  python fetch_news.py              # sekali jalan
  python fetch_news.py --loop 120   # ulangi tiap 120 detik (untuk laptop)
"""
import re, sys, time, html, json, argparse, urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

WIB = timezone(timedelta(hours=7))

# Jika ada yang error/berubah alamatnya, script otomatis melewatinya. Edit/tambah sesuka hati.
FEEDS = {
    "ANTARA":        "https://www.antaranews.com/rss/politik.xml",
    "ANTARA Nasional": "https://www.antaranews.com/rss/terkini.xml",
    # detik memblokir server GitHub, jadi diambil lewat Google News (berita detik tetap masuk, berlabel detikNews).
    "GNews detik":   "https://news.google.com/rss/search?q=site:news.detik.com+when:6h&hl=id&gl=ID&ceid=ID:id",
    "CNN Indonesia": "https://www.cnnindonesia.com/nasional/rss",
    "Tempo":         "https://rss.tempo.co/nasional",
    "Liputan6":      "https://feed.liputan6.com/rss/news",
    "Republika":     "https://www.republika.co.id/rss/nasional",
    "SINDOnews":     "https://www.sindonews.com/feed",
    "Okezone":       "https://sindikasi.okezone.com/index.php/rss/1/RSS2.0",
    # Google News menggabungkan banyak media (termasuk Kompas, Tribun, Suara) dalam satu feed.
    "GNews Politik": "https://news.google.com/rss/search?q=politik+when:6h&hl=id&gl=ID&ceid=ID:id",
    "GNews Nasional": "https://news.google.com/rss/search?q=DPR+OR+Prabowo+OR+polisi+OR+Kejagung+when:6h&hl=id&gl=ID&ceid=ID:id",
}
TRENDS_URL = "https://trends.google.com/trending/rss?geo=ID"
OUT = Path(__file__).parent / "docs" / "index.html"
UA = {"User-Agent": "Mozilla/5.0 (Duluan; +personal use)"}

STOP = set("""yang dan di ke dari untuk dengan pada ini itu akan atas oleh juga dalam tak tidak ada
adalah sebagai karena kata soal usai jadi hingga bakal saat para serta atau bisa kini lagi
bagi anggota hari sudah belum telah agar dapat lebih tentang antara terkait ungkap beri minta
tegas sebut ini ini jelang kata ucap warga polisi""".split())

SPORT = re.compile(r"\bvs\b|live score|liga|\bfc\b|skor|klasemen|jadwal|susunan pemain|premier|champions|nba|\bufc\b|moto ?gp|\bf1\b", re.I)

def get(url, timeout=15):
    """Ambil URL (atau daftar URL cadangan). Tiap alamat dicoba 2 kali."""
    last = None
    for u in ([url] if isinstance(url, str) else url):
        for attempt in range(2):
            try:
                req = urllib.request.Request(u, headers=UA)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.read()
            except Exception as e:
                last = e
                time.sleep(2)
    raise last

def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()

def parse_feed(xml_bytes):
    """Kembalikan list (judul, link, datetime|None) dari RSS atau Atom."""
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        d = {c.tag.split("}")[-1]: c for c in it}
        title = strip(d["title"].text) if "title" in d else ""
        link = ""
        if "link" in d:
            link = (d["link"].text or d["link"].attrib.get("href", "")).strip()
        dt = None
        for k in ("pubDate", "published", "updated", "date"):
            if k in d and d[k].text:
                try:
                    dt = parsedate_to_datetime(d[k].text)
                except Exception:
                    try:
                        dt = datetime.fromisoformat(d[k].text.replace("Z", "+00:00"))
                    except Exception:
                        pass
                break
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if title:
            out.append((title, link, dt))
    return out

def keyphrases(title):
    """Pasangan kata (urutan bebas) dari judul, supaya judul beda susunan tetap cocok."""
    from itertools import combinations
    words = sorted({w for w in re.findall(r"[a-zA-Z0-9#]+", title.lower()) if w not in STOP and len(w) > 3})
    return {a + " " + b for a, b in combinations(words[:12], 2)}

def detect_rising(items, trend_terms, now, window_h=3):
    """items: list dict(source,title,link,time). Pasangan kata yang muncul di >=3 media dalam window_h jam."""
    cut = now - timedelta(hours=window_h)
    by_gram = defaultdict(lambda: {"sources": set(), "items": []})
    for it in items:
        if it["time"] and it["time"] >= cut:
            for g in keyphrases(it["title"]):
                by_gram[g]["sources"].add(it["source"])
                by_gram[g]["items"].append(it)
    cand = [(g, v) for g, v in by_gram.items() if len(v["sources"]) >= 3]
    cand.sort(key=lambda x: (-len(x[1]["sources"]), -len(x[1]["items"])))
    res, used = [], set()
    for g, v in cand:
        key = frozenset(id(i) for i in v["items"])
        if any(len(key & u) / len(key) > .6 for u in used):
            continue
        used.add(key)
        in_trends = any(all(w in t.lower() for w in g.split()) for t in trend_terms)
        res.append({"topic": g, "n_sources": len(v["sources"]),
                    "sources": sorted(v["sources"]),
                    "in_trends": in_trends,
                    "items": sorted(v["items"], key=lambda i: i["time"], reverse=True)[:3]})
        if len(res) >= 10:
            break
    return res

def ago(dt, now):
    if not dt: return ""
    m = int((now - dt).total_seconds() // 60)
    if m < 1: return "baru saja"
    if m < 60: return f"{m} mnt lalu"
    h = m // 60
    return f"{h} jam lalu" if h < 24 else f"{h//24} hr lalu"

def esc(s): return html.escape(s or "", quote=True)

PAGE = """<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="300">
<meta name="theme-color" content="#14143c"><title>Duluan</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Figtree:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{--navy:#14143c;--blue:#3a4bff;--coral:#ff4d5e;--sun:#ffd84a;--mint:#20d9a0;--paper:#f3f4ff;--card:#fff;--ink:#16163a;--mut:#6a6c8f;--line:#e2e4f7}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 Figtree,system-ui,sans-serif}
h1,h2,h3{font-family:"Bricolage Grotesque",Figtree,sans-serif;margin:0;letter-spacing:-.02em}
a{color:inherit;text-decoration:none}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid var(--sun);outline-offset:2px}
.hero{background:var(--navy);color:#fff;padding:26px 18px 34px;position:relative;overflow:hidden}
.hero:before{content:"";position:absolute;right:-90px;top:-90px;width:300px;height:300px;border-radius:50%;
 background:radial-gradient(circle,var(--blue) 0,rgba(58,75,255,0) 68%)}
.hero:after{content:"";position:absolute;left:-60px;bottom:-120px;width:260px;height:260px;border-radius:50%;
 background:radial-gradient(circle,rgba(255,77,94,.55) 0,rgba(255,77,94,0) 68%)}
.wrap{max-width:780px;margin:0 auto;position:relative;z-index:1}
.live{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:#c9cbff;background:rgba(255,255,255,.08);padding:5px 12px;border-radius:99px}
.dot{width:9px;height:9px;border-radius:50%;background:var(--mint);box-shadow:0 0 0 0 rgba(32,217,160,.7);animation:p 2s infinite}
@keyframes p{70%{box-shadow:0 0 0 10px rgba(32,217,160,0)}100%{box-shadow:0 0 0 0 rgba(32,217,160,0)}}
@media(prefers-reduced-motion:reduce){.dot{animation:none}}
h1{font-size:clamp(38px,9vw,60px);line-height:1;font-weight:800;margin:16px 0 8px}
.lead{color:#c9cbff;margin:0 0 18px;max-width:46ch}
.search{width:100%;border:0;border-radius:14px;padding:14px 16px;font:inherit;background:#fff;color:var(--ink)}
main{max-width:780px;margin:0 auto;padding:0 18px 40px;position:relative;z-index:2}
.sec{margin:26px 0 12px;display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.sec h2{font-size:22px;font-weight:800}.sec span{color:var(--mut);font-size:13px}
.rail{display:flex;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding:4px 18px 10px;margin:0 -18px;scrollbar-width:none}
.rail::-webkit-scrollbar{display:none}
.hot{flex:0 0 82%;max-width:340px;scroll-snap-align:start;border-radius:20px;padding:16px;color:#fff;position:relative;min-height:190px;display:flex;flex-direction:column}
.hot:nth-child(4n+1){background:linear-gradient(145deg,#ff4d5e,#ff8a4c)}
.hot:nth-child(4n+2){background:linear-gradient(145deg,#3a4bff,#7a5cff)}
.hot:nth-child(4n+3){background:linear-gradient(145deg,#0fb88a,#2fd6c1);color:#06302a}
.hot:nth-child(4n+4){background:linear-gradient(145deg,#ffb800,#ffd84a);color:#3a2a00}
.hot h3{font-size:24px;line-height:1.1;font-weight:800;text-transform:capitalize;margin:10px 0 6px}
.meter{display:flex;gap:4px}.meter i{width:16px;height:6px;border-radius:3px;background:currentColor;opacity:.25}.meter i.on{opacity:1}
.tag{font-size:12px;font-weight:700;background:rgba(0,0,0,.2);padding:3px 10px;border-radius:99px;align-self:flex-start;margin-top:auto}
.hot ul{list-style:none;margin:6px 0 10px;padding:0;font-size:14px;line-height:1.35}
.hot li{margin-bottom:4px}.hot small{opacity:.85}
.empty{background:var(--card);border:2px dashed var(--line);border-radius:18px;padding:20px;color:var(--mut)}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{border:0;border-radius:99px;padding:8px 14px;font:700 14px Figtree,system-ui,sans-serif;cursor:pointer;background:var(--card);color:var(--ink);box-shadow:inset 0 0 0 2px var(--line)}
.chip.t{color:#fff;box-shadow:none}.chip[aria-pressed=true]{background:var(--ink);color:#fff;box-shadow:none}
.list{background:var(--card);border-radius:20px;padding:6px 16px;box-shadow:0 8px 30px rgba(20,20,60,.07)}
.row{display:block;padding:14px 0;border-top:1px solid var(--line)}.row:first-child{border-top:0}
.row b{display:block;font-weight:700;line-height:1.35;margin-top:6px}
.src{display:inline-block;font-size:12px;font-weight:700;color:#fff;padding:2px 10px;border-radius:99px}
.when{color:var(--mut);font-size:12.5px;margin-left:8px}
.row:hover b{color:var(--blue)}
.foot{color:var(--mut);font-size:13px;margin-top:22px}
</style></head><body>
<header class="hero"><div class="wrap">
 <span class="live"><i class="dot"></i>Diperbarui __UPDATED__ WIB</span>
 <h1>Duluan</h1>
 <p class="lead">Kabar nasional yang lagi naik, dari __NSRC__ media. Tahu duluan, tulis duluan.</p>
 <input class="search" id="q" type="search" placeholder="Cari judul, misalnya: cawapres, DPR, MBG" aria-label="Cari berita">
</div></header>
<main>
 <div class="sec"><h2>Mulai naik</h2><span>muncul di 3+ media dalam 3 jam</span></div>
 <div class="rail">__RISING__</div>
 <div class="sec"><h2>Trending di Google</h2><span>Indonesia</span></div>
 <div class="chips">__TRENDS__</div>
 <div class="sec"><h2>Terbaru</h2><span id="cnt"></span></div>
 <div class="chips" id="filters" style="margin-bottom:12px"><button class="chip" aria-pressed="true" data-s="">Semua</button>__FILTERS__</div>
 <div class="list" id="list">__LATEST__</div>
 __ERR__
 <p class="foot">Ini sinyal otomatis, bukan prediksi pasti viral. Cek ke sumber sebelum menulis.</p>
</main>
<script>
var q=document.getElementById('q'),rows=[].slice.call(document.querySelectorAll('.row')),src='',cnt=document.getElementById('cnt');
function go(){var t=q.value.toLowerCase().trim(),n=0;rows.forEach(function(r){var ok=(!src||r.dataset.s===src)&&(!t||r.textContent.toLowerCase().indexOf(t)>-1);r.hidden=!ok;if(ok)n++});cnt.textContent=n+' berita'}
q.addEventListener('input',go);
document.getElementById('filters').addEventListener('click',function(e){var b=e.target.closest('.chip');if(!b)return;
 [].forEach.call(this.children,function(c){c.setAttribute('aria-pressed',c===b)});src=b.dataset.s;go()});
go();
</script></body></html>"""

def hue(name):
    return sum(ord(c) * (i + 3) for i, c in enumerate(name)) % 360

def render(items, rising, trends, errors, now):
    def src_chip(name):
        return f'<span class="src" style="background:hsl({hue(name)},62%,42%)">{esc(name)}</span>'
    def row(i):
        return (f'<a class="row" data-s="{esc(i["source"])}" href="{esc(i["link"])}" target="_blank" rel="noopener">'
                f'{src_chip(i["source"])}<span class="when">{ago(i["time"], now)}</span><b>{esc(i["title"])}</b></a>')
    hot = ""
    for r in rising:
        meter = "".join(f'<i class="on"></i>' if k < r["n_sources"] else "<i></i>" for k in range(8))
        tag = "sudah trending di Google" if r["in_trends"] else "belum trending, pantau"
        lis = "".join(f'<li><a href="{esc(i["link"])}" target="_blank" rel="noopener">{esc(i["title"])}</a>'
                      f'<br><small>{esc(i["source"])}</small></li>' for i in r["items"][:2])
        hot += (f'<article class="hot"><div class="meter" title="{r["n_sources"]} media">{meter}</div>'
                f'<h3>{esc(r["topic"])}</h3><ul>{lis}</ul><span class="tag">{r["n_sources"]} media · {tag}</span></article>')
    if not hot:
        hot = '<div class="empty">Belum ada topik yang muncul di 3 media atau lebih dalam 3 jam terakhir. Cek lagi sebentar.</div>'
    palette = ["#3a4bff", "#ff4d5e", "#0fb88a", "#8a4fff", "#ff8a1f"]
    t_html = "".join(f'<span class="chip t" style="background:{palette[k % 5]}">{esc(t)}</span>'
                     for k, t in enumerate(trends[:16])) or '<span class="empty">Trending belum tersedia.</span>'
    names = sorted({i["source"] for i in items})
    filters = "".join(f'<button class="chip" aria-pressed="false" data-s="{esc(n)}">{esc(n)}</button>' for n in names)
    latest = "".join(row(i) for i in items[:120])
    err = f'<p class="foot">Sumber yang gagal diambil: {esc(", ".join(errors))}.</p>' if errors else ""
    return (PAGE.replace("__UPDATED__", f"{now.astimezone(WIB):%d %b %H:%M}").replace("__NSRC__", str(len(names)))
            .replace("__RISING__", hot).replace("__TRENDS__", t_html).replace("__FILTERS__", filters)
            .replace("__LATEST__", latest).replace("__ERR__", err))

def run():
    now = datetime.now(timezone.utc)
    items, errors = [], []
    for name, url in FEEDS.items():
        try:
            for title, link, dt in parse_feed(get(url)):
                src = name
                if name.startswith("GNews") and " - " in title:   # judul Google News berakhiran " - NamaMedia"
                    title, src = title.rsplit(" - ", 1)
                items.append({"source": src, "title": title, "link": link, "time": dt})
        except Exception as e:
            errors.append(name)
            print(f"[lewati] {name}: {e}", file=sys.stderr)
    seen, uniq = set(), []
    for i in sorted(items, key=lambda i: i["time"] or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True):
        if i["title"] not in seen:
            seen.add(i["title"]); uniq.append(i)
    trends = []
    try:
        trends = [t for t, _, _ in parse_feed(get(TRENDS_URL)) if not SPORT.search(t)]
    except Exception as e:
        print(f"[lewati] Google Trends: {e}", file=sys.stderr)
    rising = detect_rising(uniq, trends, now)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(uniq, rising, trends, errors, now), encoding="utf-8")
    print(f"{now.astimezone(WIB):%H:%M} WIB: {len(uniq)} berita, {len(rising)} topik naik, {len(errors)} sumber gagal")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="ulangi tiap N detik")
    a = ap.parse_args()
    while True:
        run()
        if not a.loop: break
        time.sleep(a.loop)
