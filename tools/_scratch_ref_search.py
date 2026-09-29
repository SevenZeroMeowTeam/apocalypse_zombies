"""在 Wikimedia Commons 上找莫辛-纳甘 M91/30 的侧视图 / 线描图纸候选（只列清单，不下载）。"""
import json, urllib.parse, urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "mcmod-art-ref/1.0 (offline minecraft mod asset work)"}


def api(**params):
    params.setdefault("format", "json")
    params.setdefault("action", "query")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def search(term, limit=25):
    d = api(list="search", srsearch=term, srnamespace=6, srlimit=limit)
    return [x["title"] for x in d.get("query", {}).get("search", [])]


def cat(name, limit=100):
    d = api(list="categorymembers", cmtitle=name, cmlimit=limit, cmtype="file")
    return [x["title"] for x in d.get("query", {}).get("categorymembers", [])]


def info(titles):
    out = []
    for i in range(0, len(titles), 20):
        chunk = titles[i:i + 20]
        d = api(titles="|".join(chunk), prop="imageinfo", iiprop="url|size|mime")
        for p in d.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            out.append({"title": p.get("title"), "w": ii.get("width"), "h": ii.get("height"),
                        "mime": ii.get("mime"), "url": ii.get("url")})
    return out


terms = [
    'Mosin Nagant side view',
    'Mosin-Nagant M1891/30',
    'Mosin Nagant 1891 drawing',
    'Mosin Nagant blueprint',
    'Mosin Nagant Mosin 91/30 rifle',
]
cands = []
for t in terms:
    cands += search(t)
for c in ["Category:Mosin-Nagant", "Category:Mosin-Nagant M1891/30", "Category:Mosin rifles"]:
    try:
        cands += cat(c)
    except Exception as e:
        print("cat fail", c, e)

seen, titles = set(), []
for c in cands:
    if c not in seen:
        seen.add(c)
        titles.append(c)

rows = info(titles)
# 只要位图、横向（宽 > 高 = 侧视图通常如此）、分辨率够
rows = [r for r in rows if r.get("url") and r.get("mime", "").startswith("image/")
        and (r.get("w") or 0) >= 900]
rows.sort(key=lambda r: -(r.get("w") or 0))
print("=== %d 候选（>=900px 宽）===" % len(rows))
for r in rows[:40]:
    print("%5sx%-5s %-46s %s" % (r["w"], r["h"], r["title"][5:], r["url"]))