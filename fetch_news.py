#!/usr/bin/env python3
"""Fetch Bangladesh education headlines (Google News RSS) and write news.json.

Only headline, publisher name, link and time are stored (no article text).
If every feed fails, the existing news.json is left untouched.
"""
import json, re, sys, time, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

OUT = "news.json"
MAX_ITEMS = 12
MAX_AGE_DAYS = 5

QUERIES = [
    # (search text, hl, gl, ceid)
    ('(এইচএসসি OR এসএসসি OR "শিক্ষা মন্ত্রণালয়" OR "শিক্ষা বোর্ড" OR "ভর্তি পরীক্ষা" OR "বিশ্ববিদ্যালয়" OR "শিক্ষা বাংলাদেশ") when:3d', "bn", "BD", "BD:bn"),
    ('Bangladesh education (HSC OR SSC OR "university admission" OR "education ministry") when:3d', "en-BD", "BD", "BD:en"),
]

def feed_url(q, hl, gl, ceid):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": hl, "gl": gl, "ceid": ceid})

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ISONH-news-bot/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def parse_rss(xml_bytes):
    items = []
    root = ET.fromstring(xml_bytes)
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate")
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)].strip()
        elif " - " in title and not source:
            title, source = title.rsplit(" - ", 1)
        if not title or not link.startswith(("http://", "https://")):
            continue
        try:
            dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
        except Exception:
            continue
        items.append({"title": re.sub(r"\s+", " ", title), "source": source.strip(), "url": link, "published": dt.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return items

def build(all_items, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    seen, out = set(), []
    for it in sorted(all_items, key=lambda x: x["published"], reverse=True):
        if datetime.strptime(it["published"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) < cutoff:
            continue
        key = re.sub(r"\W+", "", it["title"].lower())[:60]
        if key in seen:
            continue
        seen.add(key); out.append(it)
        if len(out) >= MAX_ITEMS:
            break
    return {"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "items": out}

def main():
    collected = []
    for q, hl, gl, ceid in QUERIES:
        try:
            collected += parse_rss(fetch(feed_url(q, hl, gl, ceid)))
        except Exception as e:
            print("feed failed:", hl, e, file=sys.stderr)
        time.sleep(1)
    data = build(collected)
    if not data["items"]:
        print("no items fetched; keeping existing", OUT)
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote", len(data["items"]), "items")
    return 0

if __name__ == "__main__":
    sys.exit(main())
