"""Download a tagged Pexels still pack into library/photos/."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "library" / "photos"
UA = "video-use-library/1.0 (local editor; +https://www.pexels.com/license/)"

# Public Pexels IDs. JPEG CDN works without an API key.
SEED = [
    ("1181675", "Laptop with code on screen", ["laptop", "code", "technology", "programming"]),
    ("1181244", "Hands typing on a laptop", ["laptop", "typing", "work", "office"]),
    ("574071", "Laptop on a wooden desk", ["laptop", "desk", "office"]),
    ("1181467", "Programmer at a computer", ["programming", "computer", "technology"]),
    ("3861969", "Circuit board close up", ["technology", "chip", "electronics"]),
    ("1181298", "Desktop computer workspace", ["computer", "office", "work"]),
    ("265087", "MacBook on a table", ["laptop", "apple", "work"]),
    ("3184291", "Team meeting around a table", ["meeting", "people", "office", "team"]),
    ("3184465", "Office conversation", ["office", "people", "talk"]),
    ("3184338", "Coworkers collaborating", ["team", "office", "people"]),
    ("3184418", "People talking indoors", ["people", "talk", "conversation"]),
    ("3184360", "Handshake in an office", ["handshake", "business", "people"]),
    ("3183197", "Team brainstorming", ["team", "ideas", "office"]),
    ("3183150", "City skyline", ["city", "skyline", "urban"]),
    ("374870", "City street at dusk", ["city", "street", "night"]),
    ("169647", "Urban buildings", ["city", "architecture"]),
    ("325185", "Abstract light streaks", ["abstract", "light", "motion"]),
    ("1103970", "Colorful abstract bokeh", ["abstract", "color"]),
    ("1029615", "Forest path", ["nature", "forest", "trees"]),
    ("414612", "Mountain landscape", ["nature", "mountain", "landscape"]),
    ("462118", "Green hills", ["nature", "hills"]),
    ("3756766", "Coffee and a laptop", ["coffee", "laptop", "work"]),
    ("851555", "Cup of coffee", ["coffee", "cafe"]),
    ("374016", "Writing in a notebook", ["writing", "notes", "paper"]),
    ("261662", "Notes and a pen", ["notes", "planning"]),
    ("1591062", "Stack of books", ["books", "education", "reading"]),
    ("256417", "Classroom desks", ["education", "school"]),
    ("607812", "Person using a smartphone", ["phone", "mobile", "people"]),
    ("1092644", "Hands holding a phone", ["phone", "mobile"]),
    ("1476321", "Camera on a tripod", ["camera", "video", "film"]),
    ("66134", "Video camera close up", ["camera", "video", "filming"]),
    ("4348401", "Studio lights", ["studio", "video", "production"]),
    ("2047905", "Headphones on a desk", ["headphones", "audio", "music"]),
    ("3945683", "Editing timeline on a screen", ["editing", "video", "timeline"]),
    ("733872", "Portrait of a person", ["people", "portrait", "face"]),
    ("415829", "Smiling person", ["people", "portrait", "smile"]),
]


def jpeg_url(photo_id: str) -> str:
    return (
        f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg"
        f"?auto=compress&cs=tinysrgb&w=1280"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    items = []
    for photo_id, title, tags in SEED:
        dest = OUT / f"pexels-{photo_id}.jpg"
        if not dest.exists():
            print("get", photo_id, title)
            req = urllib.request.Request(jpeg_url(photo_id), headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                if len(data) < 4000:
                    print("  skip tiny", photo_id)
                    continue
                dest.write_bytes(data)
            except Exception as exc:
                print("  fail", photo_id, exc)
                time.sleep(0.3)
                continue
            time.sleep(0.15)
        items.append({
            "id": photo_id,
            "title": title,
            "tags": tags,
            "rel": f"library/photos/pexels-{photo_id}.jpg",
            "source": "pexels",
            "license": "Pexels License — free to use, attribution not required",
        })
    catalog = {
        "source": "https://www.pexels.com/",
        "license": "https://www.pexels.com/license/",
        "count": len(items),
        "items": items,
    }
    (OUT / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print("saved", len(items), "photos")


if __name__ == "__main__":
    main()
