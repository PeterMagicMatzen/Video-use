import json
import re
import urllib.request
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pages = [
    "https://mixkit.co/free-sound-effects/",
    "https://mixkit.co/free-sound-effects/whoosh/",
    "https://mixkit.co/free-sound-effects/cinematic/",
    "https://mixkit.co/free-sound-effects/applause/",
    "https://mixkit.co/free-sound-effects/intro/",
    "https://mixkit.co/free-sound-effects/transition/",
    "https://mixkit.co/free-sound-effects/impact/",
]
pairs = {}
for url in pages:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    # cards: heading then later preview id
    blocks = re.split(r'<article|class="item-grid__item', html)
    for block in blocks:
        ids = re.findall(r"active_storage/sfx/(\d+)/", block)
        titles = [unescape(t).strip() for t in re.findall(r"<h2[^>]*>([^<]+)</h2>", block)]
        if ids and titles:
            pairs[ids[0]] = titles[0]
    # ordered zip fallback
    titles = [unescape(t).strip() for t in re.findall(r"<h2[^>]*>([^<]+)</h2>", html)]
    ids = re.findall(r'data-audio-player-preview-url-value="https://assets.mixkit.co/active_storage/sfx/(\d+)/', html)
    if len(titles) == len(ids):
        for sid, title in zip(ids, titles):
            pairs.setdefault(sid, title)
    print(url, "ids", len(ids), "h2", len(titles), "pairs", len(pairs))

cat_path = ROOT / "library" / "sfx" / "catalog.json"
data = json.loads(cat_path.read_text(encoding="utf-8"))
fixed = 0
for item in data["items"]:
    title = pairs.get(str(item["id"]))
    if title and not title.lower().startswith("free "):
        item["title"] = title
        fixed += 1
cat_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("retitled", fixed)
print([i["title"] for i in data["items"][:12]])
