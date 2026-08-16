"""Download Mixkit royalty-free SFX into library/sfx/. No signup required."""

from __future__ import annotations

import json
import re
import time
import urllib.request
from html import unescape
from pathlib import Path

PAGES = [
    "https://mixkit.co/free-sound-effects/",
    "https://mixkit.co/free-sound-effects/whoosh/",
    "https://mixkit.co/free-sound-effects/swoosh/",
    "https://mixkit.co/free-sound-effects/cinematic/",
    "https://mixkit.co/free-sound-effects/transition/",
    "https://mixkit.co/free-sound-effects/intro/",
    "https://mixkit.co/free-sound-effects/applause/",
    "https://mixkit.co/free-sound-effects/impact/",
    "https://mixkit.co/free-sound-effects/notification/",
]

UA = "video-use-library/1.0 (local editor; +https://mixkit.co/license/)"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "library" / "sfx"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def scrape(url: str) -> list[dict]:
    html = fetch(url).decode("utf-8", "replace")
    items = []
    for m in re.finditer(
        r'data-audio-player-preview-url-value="(https://assets\.mixkit\.co/active_storage/sfx/(\d+)/\2-preview\.mp3)"',
        html,
    ):
        preview, sid = m.group(1), m.group(2)
        before = html[max(0, m.start() - 1200) : m.start()]
        title_m = re.findall(r"<h2[^>]*>([^<]+)</h2>", before)
        title = unescape(title_m[-1]).strip() if title_m else f"Mixkit {sid}"
        tags = re.findall(r"/free-sound-effects/([a-z0-9-]+)/", before)
        items.append({
            "id": sid,
            "title": title,
            "tags": sorted(set(tags))[:8],
            "url": preview,
            "source": "mixkit",
            "license": "Mixkit Sound Effects Free License — commercial use, attribution not required",
        })
    return items


def slug(title: str, sid: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"{s or 'sfx'}-{sid}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    for page in PAGES:
        print("scrape", page)
        try:
            for item in scrape(page):
                seen[item["id"]] = item
        except Exception as exc:
            print("  fail", exc)
        time.sleep(0.4)

    catalog = []
    for item in sorted(seen.values(), key=lambda x: x["title"].lower()):
        name = slug(item["title"], item["id"]) + ".mp3"
        dest = OUT / name
        if not dest.exists():
            print("get", item["title"])
            try:
                dest.write_bytes(fetch(item["url"]))
                time.sleep(0.15)
            except Exception as exc:
                print("  skip", exc)
                continue
        catalog.append({
            "id": item["id"],
            "title": item["title"],
            "tags": item["tags"],
            "file": str(dest),
            "rel": f"library/sfx/{name}",
            "source": "mixkit",
            "license": item["license"],
        })

    meta = {
        "source": "https://mixkit.co/free-sound-effects/",
        "license": "https://mixkit.co/license/#sfxFree",
        "count": len(catalog),
        "items": catalog,
    }
    (OUT / "catalog.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {len(catalog)} sounds to {OUT}")


if __name__ == "__main__":
    main()
